# GeoPackage Corruption — Causal Analysis

**Date:** 2026-07-13
**Subject:** Recurring corruption of `study_area.gpkg` ("malformed database
schema (rtree_chunks_geom_delete) - trigger already exists")
**Status:** Root cause identified and fixed in v2.1.0; self-healing safety
net added; further hardening recommendations below.

## 1. Observed damage (forensics on a corrupted field file)

The corrupted DRC `study_area.gpkg` (2026-07-09) showed:

- Two byte-identical copies of the same `sqlite_master` btree **leaf page**,
  containing duplicate rows (including identical rowids, e.g. rowid 130 in
  both copies) for four schema objects: `rtree_chunks_geom_delete`,
  `trigger_insert_feature_count_chunks`,
  `trigger_delete_feature_count_chunks`, and
  `rtree_study_area_grid_geom_insert`.
- `PRAGMA integrity_check` (after schema repair): `Tree 1 page 1 cell 9:
  Rowid 133 out of order` — the schema btree's interior page pointed at both
  the current and a stale image of the same leaf.
- All **data** tables were intact; only the schema btree was damaged.

This is not a SQL-level bug (nothing executed `CREATE TRIGGER` twice — SQLite
would have rejected it). A whole *page image* was duplicated inside the
btree, which can only happen when two writers modify the database file /
WAL without mutual exclusion — precisely what SQLite's file locking exists
to prevent. So the causal question becomes: **why was SQLite's locking not
protecting the file?**

## 2. Root cause

`StudyAreaProcessingTask._set_sqlite_write_safety_options()` set, for the
duration of study area creation:

```python
gdal.SetConfigOption("SQLITE_USE_OGR_VFS", "YES")   # ← the culprit
```

`SQLITE_USE_OGR_VFS=YES` routes all SQLite I/O through GDAL's VSI virtual
file system. **GDAL's SQLite VFS implements the locking primitives
(`xLock`/`xUnlock`/shared-memory locks) as no-ops.** The GDAL documentation
notes the option is incompatible with file locking. Consequences:

1. Every SQLite lock acquisition in the whole QGIS process silently
   succeeded without locking anything (`gdal.SetConfigOption` is
   process-wide, so the QGIS OGR provider's own connections were affected
   too, not just the plugin's).
2. WAL mode makes this worse, not better: WAL correctness *depends* on the
   shared-memory lock table in the `-shm` file. With no-op locks, two
   connections can both believe they own the WAL write lock, and a
   checkpoint can run concurrently with a writer — copying stale page
   images from the WAL over pages another connection just rewrote. That is
   the exact mechanism that produces a duplicated btree leaf.
3. The corrupted objects (triggers for `chunks` and `study_area_grid`) are
   exactly the layers written during study area creation — the only phase
   in which the option was active.

The irony: the function is named "write **safety** options". The WAL +
`synchronous=NORMAL` parts are genuinely safer; the VFS option disabled the
one mechanism that makes multiple connections safe at all.

**Fix (v2.1.0):** `SQLITE_USE_OGR_VFS` is now forced to `NO`
(`study_area_processing_task.py`, `_set_sqlite_write_safety_options`).

## 3. Why corruption needed more than one connection

Disabling locking is only fatal if writers actually overlap. A code audit
found these concurrent write paths to `study_area.gpkg` during study area
creation (ordered by likelihood of being the trigger):

| # | Writer A | Writer B | Notes |
|---|----------|----------|-------|
| 1 | `UnifiedWriterThread` persistent connection (`study_area_processing_task.py:353`), running in its own QThread | `GridChunkerTask.write_chunks_to_gpkg()` transient connection (`grid_chunker_task.py:169–186`) | B is wrapped in `self.gpkg_lock`, but the writer thread does not take that lock, so the mutex does not serialise the pair. GDAL defers RTree/trigger DDL to dataset close — both connections can emit schema writes when they flush/close. Matches the duplicated `chunks` triggers exactly. |
| 2 | `UnifiedWriterThread` | `add_model_columns_to_grid` → `_checkpoint_wal()` (`grid_column_utils.py:81`), main thread | Concurrent `PRAGMA wal_checkpoint(TRUNCATE)` while the writer drains its final batch. |
| 3 | `UnifiedWriterThread` | QGIS main-thread OGR provider connections opened by `add_bboxes_to_map()` on every progress tick (~0.5 s, `create_project_panel.py:649,1023`) | Mostly readers, but provider reloads can force reopen/metadata writes. |
| 4 | Duplicate `CREATE_LAYER` ops within one writer batch (`study_area_processing_task.py:656–690`) | — | Single-connection, low risk. |

With functional locking (the fix), these overlaps degrade to
`database is locked` / `SQLITE_BUSY` — contention, not corruption — and the
code already has retry logic for that. **That is why removing the VFS
option prevents the corruption class outright rather than just making it
rarer.**

A historic secondary issue (fixed earlier, commit `95770efd`) was stale
uncheckpointed WAL journals causing invalid-CRS reads; that was a symptom
of the same multi-connection design but is not a corruption mechanism.

## 4. Defence in depth added (v2.1.0)

Because file corruption can still arrive from outside this code path
(crashes mid-checkpoint, power loss, network filesystems, other tools), a
self-healing layer was added (`geest/core/gpkg_doctor.py`):

- `PRAGMA quick_check` health checks on project open, after every workflow
  run, and at the end of study area creation (in a background `QgsTask`).
- In-place repair of stale WAL journals and duplicate schema objects
  (byte-level same-length renames — no file copy, safe for very large
  GeoPackages — followed by removal of the renamed rows).
- Structural btree damage is repaired by a `VACUUM INTO` rebuild with an
  atomic swap; the corrupt original is preserved as
  `*.corrupt-<timestamp>.bak`.
- Workflow CRS resolution self-heals and retries instead of aborting the
  analysis.

Verified against the real corrupted DRC file: fully healed, all 78,059 grid
cells and 104 chunks intact.

## 5. Further hardening (implemented post-2.1.0)

None of these were required to prevent the observed corruption (the root
cause is fixed), but they reduce lock contention and shrink the
multi-writer surface. All four are now implemented:

1. **True single-writer** ✅ — chunk tiles are queued through the
   `UnifiedWriterThread` (`GpkgOperation.write_geometry` to the `chunks`
   layer) instead of `GridChunkerTask` opening a second write connection;
   the lock/retry dance around chunk metadata writes is gone.
   `GridChunkerTask.write_chunks_to_gpkg()` remains for standalone use only.
2. **Serialised checkpoints** ✅ — every `PRAGMA wal_checkpoint` in the
   process (unified writer shutdown, grid column utils, features-per-cell,
   opportunities mask, the gpkg doctor itself) goes through
   `gpkg_doctor.WAL_CHECKPOINT_LOCK` via `checkpoint_dataset()` /
   `checkpoint_wal()`.
3. **Complete layer pre-creation** ✅ — `_prepare_study_area_layers()` now
   also pre-creates `chunks` (with its rtree triggers), so no schema DDL
   runs while the unified writer holds its persistent connection.
   (`ghsl_settlements` is written by `gdal.VectorTranslate` *before* any
   worker thread starts, so its DDL was never concurrent.)
4. **Deferred UI layer refresh** ✅ — while the study area task runs, map
   reloads are rate-limited to one per 5 s (was one per 0.5 s), and a
   final refresh fires on task completion.
