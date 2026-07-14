# -*- coding: utf-8 -*-
"""🩺 GeoPackage self-healing utilities.

This module detects and repairs, in place, the corruption classes that GeoE3
has encountered in its working GeoPackages:

1. **Stale WAL journals** — uncheckpointed ``-wal``/``-shm`` files left behind
   by writer connections. Healed with ``PRAGMA wal_checkpoint(TRUNCATE)``.
2. **Duplicate schema objects** — e.g. ``malformed database schema
   (rtree_chunks_geom_delete) - trigger "rtree_chunks_geom_delete" already
   exists``. Caused by two write connections racing to create the same RTree
   spatial index (a whole ``sqlite_master`` btree leaf page can be duplicated).
   SQLite refuses to even parse the schema, so no SQL-level repair is
   possible. Healed by byte-level renaming of the duplicate entries (same
   length, so no page layout changes) until the schema parses, then removing
   the renamed duplicates.
3. **Structural btree damage** — e.g. out-of-order rowids in the schema
   btree. Healed by rebuilding the database with ``VACUUM INTO`` and
   atomically swapping the rebuilt file into place (the corrupt original is
   kept alongside as a ``.corrupt-<timestamp>.bak`` file).

Only pure Python stdlib is used (``sqlite3`` + file I/O) so the module can be
tested outside QGIS. Large files are never read fully into memory: duplicate
detection streams the file in chunks and repairs write only the handful of
bytes being renamed.

All healing is serialised through a module-level lock so concurrent callers
(workflow threads, UI tasks) cannot patch the same file simultaneously.
"""

from __future__ import annotations

import datetime
import os
import re
import shutil
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

# Serialise all healing attempts within this process.
_HEAL_LOCK = threading.Lock()

# Serialise every WAL checkpoint within this process: two connections
# restarting/truncating a checkpoint on the same file at once is a needless
# contention (and historically corruption) surface.
WAL_CHECKPOINT_LOCK = threading.Lock()

# Matches the object kind and name out of SQLite's duplicate-schema error:
# 'malformed database schema (x) - trigger "x" already exists'
_DUPLICATE_SCHEMA_RE = re.compile(r'\b(table|index|view|trigger)\s+"?([\w.]+)"?\s+already exists')

# Safety valve for the rename loop (a duplicated schema page rarely holds
# more than a handful of entries).
_MAX_DUPLICATE_RENAMES = 100

_SQLITE_TIMEOUT_S = 30.0

# Streaming scan chunk size (bytes). 8 MiB keeps memory flat on huge files.
_SCAN_CHUNK_SIZE = 8 * 1024 * 1024

# Error fragments that genuinely indicate corruption. Anything else coming
# out of a failed check (locked, busy, permission denied, ...) means the
# database could not be ASSESSED — repairing on such a signal could damage a
# healthy database that is merely in use by another connection.
_CORRUPTION_MARKERS = (
    "malformed",
    "already exists",
    "not a database",
    "database disk image",
)


def _is_corruption_signal(status: str) -> bool:
    """True when a check result reports real corruption (not lock/IO noise)."""
    lowered = status.lower()
    if not lowered.startswith("failed ("):
        return True  # an actual quick_check/integrity_check problem row
    return any(marker in lowered for marker in _CORRUPTION_MARKERS)


LogCallable = Callable[[str], None]


@dataclass
class HealReport:
    """Outcome of a :func:`heal_geopackage` run."""

    path: str
    healthy: bool = False
    was_corrupt: bool = False
    actions: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """One-line human readable summary of the heal attempt."""
        state = "healthy" if self.healthy else "UNHEALTHY"
        if not self.was_corrupt:
            return f"{os.path.basename(self.path)}: {state} (no repair needed)"
        parts = [f"{os.path.basename(self.path)}: {state} after repair"]
        if self.actions:
            parts.append("actions: " + "; ".join(self.actions))
        if self.errors:
            parts.append("errors: " + "; ".join(self.errors))
        return " | ".join(parts)


def _connect(path: str) -> sqlite3.Connection:
    return sqlite3.connect(path, timeout=_SQLITE_TIMEOUT_S)


def schema_error(path: str) -> Optional[str]:
    """Return the schema parse error for the database, or None if it parses."""
    try:
        connection = _connect(path)
        try:
            connection.execute("SELECT count(*) FROM sqlite_master")
            return None
        finally:
            connection.close()
    except sqlite3.Error as error:
        return str(error)


def quick_check(path: str) -> str:
    """Run ``PRAGMA quick_check`` and return 'ok' or the first problem found."""
    try:
        connection = _connect(path)
        try:
            row = connection.execute("PRAGMA quick_check(1)").fetchone()
            return str(row[0]) if row else "unknown"
        finally:
            connection.close()
    except sqlite3.Error as error:
        return f"failed ({error})"


def integrity_problems(path: str) -> List[str]:
    """Run a full ``PRAGMA integrity_check`` and return the problem list.

    Returns an empty list when the database is fully intact.
    """
    try:
        connection = _connect(path)
        try:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
        finally:
            connection.close()
    except sqlite3.Error as error:
        return [f"failed ({error})"]
    problems = [str(row[0]) for row in rows]
    if problems == ["ok"]:
        return []
    return problems


def checkpoint_wal(path: str) -> bool:
    """Checkpoint and truncate any WAL journal. Safe on unparseable schemas."""
    try:
        with WAL_CHECKPOINT_LOCK:
            connection = _connect(path)
            try:
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                return True
            finally:
                connection.close()
    except sqlite3.Error:
        return False


def checkpoint_dataset(ds) -> None:
    """Checkpoint an open OGR/GDAL dataset's WAL, serialised process-wide.

    Duck-typed (anything exposing ``ExecuteSQL``) so this module stays
    stdlib-only. Failures are swallowed: closing the dataset still flushes,
    a missed checkpoint is only a performance concern.
    """
    if ds is None:
        return
    with WAL_CHECKPOINT_LOCK:
        try:
            ds.ExecuteSQL("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:  # nosec B110 — non-fatal; the close will still flush
            pass


def _iter_pattern_offsets(path: str, patterns: List[bytes]) -> List[Tuple[int, bytes]]:
    """Stream the file finding byte offsets of any of the given patterns."""
    if not patterns:
        return []
    overlap = max(len(p) for p in patterns) - 1
    hits: List[Tuple[int, bytes]] = []
    with open(path, "rb") as handle:
        base = 0
        tail = b""
        while True:
            chunk = handle.read(_SCAN_CHUNK_SIZE)
            if not chunk:
                break
            window = tail + chunk
            window_base = base - len(tail)
            for pattern in patterns:
                start = 0
                while True:
                    idx = window.find(pattern, start)
                    if idx == -1:
                        break
                    offset = window_base + idx
                    # The overlap region is seen twice; keep one copy.
                    if (offset, pattern) not in hits:
                        hits.append((offset, pattern))
                    start = idx + 1
            tail = window[-overlap:] if overlap else b""
            base += len(chunk)
    hits.sort()
    return hits


def _replacement_name(name: str, taken: set) -> str:
    """Generate a unique replacement of *identical byte length* for a name."""
    for counter in range(1, 1000):
        suffix = f"_dup{counter:03d}"
        if len(name) > len(suffix):
            candidate = name[: len(name) - len(suffix)] + suffix
        else:
            digits = str(counter)
            candidate = name[: len(name) - len(digits)] + digits
        if candidate != name and candidate not in taken:
            return candidate
    raise RuntimeError(f"could not generate replacement name for {name}")


def _rename_last_duplicate(path: str, kind: str, name: str, taken: set) -> Optional[str]:
    """Rename the last on-disk copy of a duplicated schema object.

    Patches, in place and with a same-length name, both the ``name`` column
    and the name inside the ``CREATE ...`` statement of the *last* duplicate
    ``sqlite_master`` record so the schema becomes parseable again.

    Returns the new name, or None if the duplicate could not be located.
    """
    kind_upper = kind.upper().encode()
    kind_lower = kind.lower().encode()
    name_bytes = name.encode()
    patterns = [
        b"CREATE " + kind_upper + b' "' + name_bytes + b'"',
        b"CREATE " + kind_upper + b" '" + name_bytes + b"'",
        b"CREATE " + kind_upper + b" " + name_bytes + b" ",
        b"CREATE " + kind_upper + b" " + name_bytes + b"(",
    ]
    if kind_lower == b"table":
        patterns.append(b'CREATE VIRTUAL TABLE "' + name_bytes + b'"')
        patterns.append(b"CREATE VIRTUAL TABLE " + name_bytes + b" ")

    hits = _iter_pattern_offsets(path, patterns)
    if len(hits) < 2:
        return None

    target_offset, target_pattern = hits[-1]
    new_name = _replacement_name(name, taken)
    new_bytes = new_name.encode()

    with open(path, "r+b") as handle:
        # 1) Rename inside the CREATE statement text.
        name_in_pattern = target_pattern.find(name_bytes)
        handle.seek(target_offset + name_in_pattern)
        handle.write(new_bytes)

        # 2) Rename the record's name column. sqlite_master record values are
        #    stored contiguously (type, name, tbl_name, sql), so the name is
        #    the kind string immediately followed by the object name, shortly
        #    before the CREATE text.
        window_start = max(0, target_offset - 600)
        handle.seek(window_start)
        window = handle.read(target_offset - window_start)
        field_idx = window.rfind(kind_lower + name_bytes)
        if field_idx == -1:
            # Revert the CREATE patch — we could not find the record header.
            handle.seek(target_offset + name_in_pattern)
            handle.write(name_bytes)
            handle.flush()
            os.fsync(handle.fileno())
            return None
        handle.seek(window_start + field_idx + len(kind_lower))
        handle.write(new_bytes)
        handle.flush()
        os.fsync(handle.fileno())
    return new_name


def _delete_schema_rows(path: str, names: List[str]) -> bool:
    """Remove sqlite_master rows by name via writable_schema.

    Used when the schema btree itself is structurally sound. Deleting the row
    directly (rather than DROP) never touches data pages, so it is safe even
    when a duplicate table entry shares its root page with the original.
    """
    try:
        connection = _connect(path)
        try:
            connection.execute("PRAGMA writable_schema=ON")
            placeholders = ",".join("?" for _ in names)
            connection.execute(
                f"DELETE FROM sqlite_master WHERE name IN ({placeholders})",  # nosec B608
                names,
            )
            connection.commit()
            connection.execute("PRAGMA writable_schema=OFF")
            return True
        finally:
            connection.close()
    except sqlite3.Error:
        return False


def _drop_schema_objects(path: str, names: List[str]) -> bool:
    """DROP renamed duplicate objects properly.

    Only safe after a VACUUM rebuild, where every schema entry owns its own
    independent root page.
    """
    try:
        connection = _connect(path)
        try:
            for name in names:
                row = connection.execute("SELECT type FROM sqlite_master WHERE name = ?", (name,)).fetchone()
                if not row:
                    continue
                kind = row[0]
                if kind not in ("table", "index", "view", "trigger"):
                    continue
                connection.execute(f'DROP {kind.upper()} IF EXISTS "{name}"')
            connection.commit()
            return True
        finally:
            connection.close()
    except sqlite3.Error:
        return False


def _vacuum_rebuild(path: str, report: HealReport) -> bool:
    """Rebuild the database with VACUUM INTO and swap it into place.

    The corrupt original (plus any WAL/SHM journals) is renamed to a
    ``.corrupt-<timestamp>.bak`` file rather than deleted.
    """
    size = os.path.getsize(path)
    free = shutil.disk_usage(os.path.dirname(path) or ".").free
    if free < size * 1.2:
        report.errors.append(f"not enough free disk space to rebuild ({free} bytes free, need ~{int(size * 1.2)})")
        return False

    rebuilt = path + ".rebuild.tmp"
    if os.path.exists(rebuilt):
        os.remove(rebuilt)
    try:
        connection = _connect(path)
        try:
            connection.execute("VACUUM INTO ?", (rebuilt,))
        finally:
            connection.close()
    except sqlite3.Error as error:
        report.errors.append(f"VACUUM INTO failed: {error}")
        if os.path.exists(rebuilt):
            os.remove(rebuilt)
        return False

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{path}.corrupt-{timestamp}.bak"
    os.rename(path, backup)
    for journal_suffix in ("-wal", "-shm"):
        journal = path + journal_suffix
        if os.path.exists(journal):
            os.rename(journal, backup + journal_suffix)
    os.rename(rebuilt, path)
    report.actions.append(f"rebuilt database (corrupt original kept as {os.path.basename(backup)})")
    return True


def heal_geopackage(path: str, log: Optional[LogCallable] = None) -> HealReport:
    """Check a GeoPackage and repair it in place if corrupted.

    Args:
        path: Path to the GeoPackage.
        log: Optional callable receiving progress messages.

    Returns:
        A HealReport describing what (if anything) was done.
    """
    report = HealReport(path=path)
    emit = log or (lambda message: None)

    if not os.path.exists(path):
        report.errors.append("file does not exist")
        return report

    with _HEAL_LOCK:
        status = quick_check(path)
        if status == "ok":
            report.healthy = True
            return report

        if not _is_corruption_signal(status):
            # Locked/busy/unreadable — the database could not be assessed.
            # Never repair on an ambiguous signal: it may be a healthy file
            # held by an active writer.
            report.errors.append(f"could not assess database health ({status}); leaving file untouched")
            emit(f"GeoPackage health could not be assessed ({status}); no repair attempted")
            return report

        report.was_corrupt = True
        emit(f"GeoPackage corruption detected in {path}: {status}")
        report.actions.append(f"quick_check: {status}")

        # 1) Stale WAL journals are the cheapest fix — checkpoint first.
        if checkpoint_wal(path):
            report.actions.append("checkpointed WAL journal")
        if quick_check(path) == "ok":
            report.healthy = True
            emit("Healed by WAL checkpoint")
            return report

        # 2) Duplicate schema objects: rename byte-level until schema parses.
        renamed: List[str] = []
        taken: set = set()
        for _ in range(_MAX_DUPLICATE_RENAMES):
            error = schema_error(path)
            if error is None:
                break
            match = _DUPLICATE_SCHEMA_RE.search(error)
            if not match:
                report.errors.append(f"unrecognised schema error: {error}")
                emit(f"Cannot self-heal, unrecognised schema error: {error}")
                return report
            kind, duplicate_name = match.group(1), match.group(2)
            new_name = _rename_last_duplicate(path, kind, duplicate_name, taken)
            if new_name is None:
                report.errors.append(f"could not locate duplicate {kind} {duplicate_name} on disk")
                emit(f"Cannot self-heal, duplicate {kind} {duplicate_name} not found on disk")
                return report
            taken.add(new_name)
            renamed.append(new_name)
            report.actions.append(f"renamed duplicate {kind} {duplicate_name} -> {new_name}")
            emit(f"Renamed duplicate {kind} {duplicate_name} -> {new_name}")

        if schema_error(path) is not None:
            report.errors.append("schema still unparseable after duplicate renames")
            return report

        # 3) Decide between in-place row removal and a full rebuild.
        problems = integrity_problems(path)
        if problems and not any(_is_corruption_signal(problem) for problem in problems):
            # integrity_check itself failed (locked/busy) — do not rebuild on
            # an ambiguous signal.
            report.errors.append(f"could not run integrity check ({problems[0]}); rebuild skipped")
            return report
        if not problems:
            if renamed:
                if _delete_schema_rows(path, renamed):
                    report.actions.append(f"removed {len(renamed)} duplicate schema row(s) in place")
                else:
                    report.errors.append("failed to remove duplicate schema rows")
                    return report
        else:
            report.actions.append(f"integrity_check reported {len(problems)} problem(s); rebuilding database")
            emit(f"Structural damage found ({problems[0]}...); rebuilding {os.path.basename(path)}")
            if not _vacuum_rebuild(path, report):
                return report
            if renamed:
                if _drop_schema_objects(path, renamed):
                    report.actions.append(f"dropped {len(renamed)} duplicate schema object(s) after rebuild")
                else:
                    report.errors.append("failed to drop duplicate schema objects after rebuild")

        status = quick_check(path)
        report.healthy = status == "ok"
        if report.healthy:
            emit(f"GeoPackage healed successfully: {path}")
        else:
            report.errors.append(f"still unhealthy after repair: {status}")
            emit(f"GeoPackage could NOT be fully healed: {status}")
    return report


def ensure_healthy_geopackage(path: str, log: Optional[LogCallable] = None) -> HealReport:
    """Convenience wrapper: quick health check with self-heal on failure."""
    return heal_geopackage(path, log=log)
