# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Reverse-engineered Software Requirements Specification under `srs/`
  (branded Word + PDF deliverables, 18 UML diagrams as SVG, one-shot
  `srs/build.sh` pipeline writing directly into the Kartoza Word template).
- SRS build toolchain in the dev shell (plantuml, python-docx, pillow,
  libreoffice, Lato).
- GeoPackage corruption causal analysis
  (`docs/gpkg-corruption-causal-analysis.md`).
- SRS chapter 8 "Shipped model catalogue", generated from
  `geest/resources/model.json` at build time
  (`srs/scripts/gen_model_catalogue.py`): a page per dimension and per
  factor, every indicator with its defaults, brand-styled WBS tree diagrams
  per dimension, and an indicator × processor capability matrix rendered as
  SVG/PNG.
- QGIS launcher scripts now symlink the working-tree plugin into the GEOE3
  profile's `python/plugins` folder before launching
  (`scripts/ensure_plugin_link.sh`).
- Launcher scripts pin QGIS to a light palette even when the desktop is in
  dark mode (`scripts/qgis_light_theme_startup.py` via `PYQGIS_STARTUP`;
  Qt 6.8+ colour-scheme override with a light-Fusion-palette fallback).
- GeoPackage write-path hardening (causal analysis §5, all four items):
  chunk tiles now go through the single unified writer connection, every
  WAL checkpoint in the process is serialised behind one lock, all layers
  (including `chunks`) are pre-created before worker threads start, and
  map refreshes are deferred while the writer is active.

### Changed

- The flake now sources QGIS from nixpkgs: `qgis` 4.x (latest) and
  `qgis-ltr` 3.44.x; the geospatial-nix and qgis-source inputs were removed
  and `flake.lock` updated accordingly. nixpkgs is pinned to the last
  revision with binary-cached QGIS builds.
- Dev shell Qt tooling moved from Qt 5 to Qt 6 (`kdePackages.*`) to match
  QGIS 4.x — nixpkgs rejects mixed Qt shells; each QGIS variant now gets the
  matching PyQt WebEngine binding (PyQt6 for 4.x, PyQt5 for LTR).
- The dev shell recreates `.venv` automatically when the nix python
  interpreter changes (a stale venv made pip write into the read-only
  store).

### Fixed

- SRS PDF conversion silently substituted DejaVu for the brand fonts and
  dropped bold: `srs/build.sh` now provisions Lato and JetBrains Mono via a
  throwaway fontconfig so PlantUML and LibreOffice embed the correct faces.
- GeoPackage self-healing hardening: locked/busy check results are now
  classified as "could not assess" instead of corruption, so the healer can
  never rebuild-and-swap a healthy database that is merely held by an active
  writer (regression tests added).
- QGIS 4 / PyQt6 crash in the open-project panel: `event.Resize` instance
  enum access replaced with `QEvent.Type.Resize` (works on PyQt5 too).
- QGIS 4 / PyQt6 plugin-load failures: all remaining unscoped Qt enum
  accesses (`QTreeView.InternalMove`/`NoEditTriggers`,
  `QFileDialog.ExistingFile`/`AcceptSave`, `QDockWidget.DockWidget*`,
  `QScrollArea.NoFrame`, `QAbstractScrollArea.AdjustToContents`,
  `QAbstractSpinBox.UpDownArrows`) replaced with their scoped forms — every
  Qt attribute reference in the package is now mechanically verified against
  both PyQt5 and PyQt6 by a new regression test
  (`test/test_qt_enum_compliance.py`), so this bug class is caught by the
  suite instead of at plugin load.
- QGIS 4 / PyQt6 crash when resizing data-source widgets: three widgets
  read `PM_DefaultFrameWidth` off a style *instance* — replaced with
  `QStyle.PixelMetric.PM_DefaultFrameWidth`, and the enum compliance test
  now also bans instance enum-member access (`style().PM_*`, `event.X`).
- Active Transport skipped as "unconfigured" although a layer was set: the
  polyline workflow now accepts the layer under any of its sibling mode
  keys (`osm_transport_polyline_per_cell_*`, `road_network_layer_path`),
  so switching analysis mode no longer orphans a configured layer; the
  decline log lists exactly which data-source keys are present. A new
  end-to-end suite (`test/test_workflow_job_e2e.py`) runs a real indicator
  through the production queue → job → factory → workflow chain on both
  QGIS images, covering the run path unit tests missed.
- Crash when running an indicator with no data source configured: six
  workflow `__init__` methods did `return False` on missing/invalid
  sources, which Python rejects with `TypeError: __init__() should return
  None`. They now raise `WorkflowNotConfiguredError`; the queue manager
  skips the job with a log entry and the tree panel shows a message-bar
  hint naming the unconfigured indicator. An AST regression test
  (`test/test_workflow_init_hygiene.py`) bans value-returns in workflow
  `__init__` methods.
- Plugin reloads no longer stack duplicate dock widgets: `unload()`
  reparents the dock before the queued deletion, and `initGui()` sweeps
  stale `GeoE3DockWidget` instances left by a crashed previous load.
- QGIS 4 / PyQt6 plugin-load failure: the dock area persisted in QSettings
  is an int, which PyQt6 no longer auto-converts to `Qt.DockWidgetArea` —
  now normalised through `_to_dock_widget_area()` (invalid values fall back
  to the right dock) at every `addDockWidget` call, and the enum-vs-int
  dock-area comparison that silently broke tabifying is fixed. A new test
  (`test/test_geoe3_dock_construction.py`) builds the complete dock — all
  panels — on both PyQt5 and PyQt6 images so constructor-time porting
  regressions fail the suite instead of plugin load.

## [2.1.0] - 2026-07-13

### Added

- GeoPackage self-healing module (`geest.core.gpkg_doctor`) that detects and
  repairs, in place, the corruption classes seen in the field: stale WAL
  journals, duplicated schema objects (`trigger ... already exists` /
  malformed database schema errors caused by historic write races), and
  structural btree damage (repaired via a rebuild, keeping the corrupt
  original as a `.corrupt-<timestamp>.bak` file).
- Automatic GeoPackage health checks (run in a background task so the UI
  never blocks): on project open, after every workflow run completes, and at
  the end of study area creation.
- Self-heal-and-retry in workflow CRS resolution, so an analysis run against
  a corrupted study area GeoPackage repairs it and continues instead of
  failing with "Could not determine CRS for study area".
- Unit tests for the self-healing module (`test/test_gpkg_doctor.py`).

### Fixed

- Root cause of study area GeoPackage corruption: `SQLITE_USE_OGR_VFS=YES`
  was set process-wide during study area creation. The OGR VSI file layer
  does not implement SQLite file locking, so concurrent write connections
  could interleave page writes unprotected, producing duplicated
  `sqlite_master` pages ("trigger rtree_..._delete already exists"). The
  option is now forced off.

## [2.0.4] - earlier

- See git history for changes prior to the introduction of this changelog.
