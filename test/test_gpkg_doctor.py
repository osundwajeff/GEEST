# -*- coding: utf-8 -*-
import os
import shutil
import sqlite3
import tempfile
import unittest

from geest.core.gpkg_doctor import (
    HealReport,
    checkpoint_wal,
    heal_geopackage,
    integrity_problems,
    quick_check,
    schema_error,
)


def make_test_db(path):
    """Create a small database mimicking a GeoPackage layer with rtree triggers."""
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE chunks (fid INTEGER PRIMARY KEY, geom BLOB, idx INTEGER)")
    connection.execute(
        'CREATE TRIGGER "rtree_chunks_geom_delete" AFTER DELETE ON "chunks" '
        'WHEN old."geom" NOT NULL BEGIN SELECT 1; END'
    )
    connection.execute('CREATE TRIGGER "rtree_chunks_geom_insert" AFTER INSERT ON "chunks" ' "BEGIN SELECT 1; END")
    connection.executemany(
        "INSERT INTO chunks (geom, idx) VALUES (?, ?)",
        [(b"\x00" * 32, i) for i in range(50)],
    )
    connection.commit()
    connection.close()


def duplicate_trigger_row(path, trigger_name):
    """Fabricate the duplicate-schema-object corruption GeoE3 has seen in the
    wild (two write connections racing to create the same rtree trigger)."""
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA writable_schema=ON")
    connection.execute(
        "INSERT INTO sqlite_master (type, name, tbl_name, rootpage, sql) "
        "SELECT type, name, tbl_name, rootpage, sql FROM sqlite_master WHERE name = ?",
        (trigger_name,),
    )
    connection.commit()
    connection.execute("PRAGMA writable_schema=OFF")
    connection.close()


class TestGpkgDoctor(unittest.TestCase):

    def setUp(self):
        self.work_dir = tempfile.mkdtemp(prefix="gpkg_doctor_test_")
        self.db_path = os.path.join(self.work_dir, "study_area.gpkg")
        make_test_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.work_dir, ignore_errors=True)
        return super().tearDown()

    def test_healthy_file_is_untouched(self):
        report = heal_geopackage(self.db_path)
        self.assertTrue(report.healthy)
        self.assertFalse(report.was_corrupt)
        self.assertEqual(report.actions, [])

    def test_quick_check_reports_ok(self):
        self.assertEqual(quick_check(self.db_path), "ok")

    def test_missing_file(self):
        report = heal_geopackage(os.path.join(self.work_dir, "nope.gpkg"))
        self.assertFalse(report.healthy)
        self.assertIn("file does not exist", report.errors)

    def test_duplicate_trigger_detected(self):
        duplicate_trigger_row(self.db_path, "rtree_chunks_geom_delete")
        error = schema_error(self.db_path)
        self.assertIsNotNone(error)
        self.assertIn("already exists", error or "")
        self.assertIn("failed", quick_check(self.db_path))

    def test_heal_duplicate_trigger_in_place(self):
        duplicate_trigger_row(self.db_path, "rtree_chunks_geom_delete")
        size_before = os.path.getsize(self.db_path)

        messages = []
        report = heal_geopackage(self.db_path, log=messages.append)

        self.assertTrue(report.healthy, msg=report.summary())
        self.assertTrue(report.was_corrupt)
        self.assertIsNone(schema_error(self.db_path))
        self.assertEqual(quick_check(self.db_path), "ok")
        self.assertEqual(integrity_problems(self.db_path), [])
        # In-place heal: no rebuild backup should have been created.
        backups = [f for f in os.listdir(self.work_dir) if ".corrupt-" in f]
        self.assertEqual(backups, [])
        # Same-length byte renames must not change the file size.
        self.assertEqual(os.path.getsize(self.db_path), size_before)
        self.assertTrue(messages)

        connection = sqlite3.connect(self.db_path)
        triggers = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")]
        connection.close()
        # Exactly one copy of each original trigger, no renamed leftovers.
        self.assertEqual(sorted(triggers), ["rtree_chunks_geom_delete", "rtree_chunks_geom_insert"])
        # Data intact.
        connection = sqlite3.connect(self.db_path)
        count = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
        connection.close()
        self.assertEqual(count, 50)

    def test_heal_multiple_duplicate_triggers(self):
        duplicate_trigger_row(self.db_path, "rtree_chunks_geom_delete")
        duplicate_trigger_row(self.db_path, "rtree_chunks_geom_insert")

        report = heal_geopackage(self.db_path)

        self.assertTrue(report.healthy, msg=report.summary())
        connection = sqlite3.connect(self.db_path)
        triggers = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")]
        connection.close()
        self.assertEqual(sorted(triggers), ["rtree_chunks_geom_delete", "rtree_chunks_geom_insert"])

    def test_stale_wal_is_checkpointed(self):
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("INSERT INTO chunks (geom, idx) VALUES (x'00', 99)")
        connection.commit()
        connection.close()
        self.assertTrue(checkpoint_wal(self.db_path))
        wal = self.db_path + "-wal"
        self.assertTrue(not os.path.exists(wal) or os.path.getsize(wal) == 0)

    def test_locked_database_is_left_untouched(self):
        """A healthy database held by an exclusive writer must never be
        'repaired' — locked/busy means could-not-assess, not corrupt."""
        from geest.core import gpkg_doctor

        writer = sqlite3.connect(self.db_path)
        writer.execute("BEGIN EXCLUSIVE")
        writer.execute("INSERT INTO chunks (geom, idx) VALUES (?, ?)", (b"\x01" * 32, 999))
        size_before = os.path.getsize(self.db_path)
        original_timeout = gpkg_doctor._SQLITE_TIMEOUT_S
        gpkg_doctor._SQLITE_TIMEOUT_S = 0.1
        try:
            report = heal_geopackage(self.db_path)
        finally:
            gpkg_doctor._SQLITE_TIMEOUT_S = original_timeout
            writer.rollback()
            writer.close()
        self.assertFalse(report.healthy)
        self.assertFalse(report.was_corrupt)
        self.assertEqual(report.actions, [])
        self.assertTrue(any("could not assess" in e for e in report.errors))
        # untouched: same size, no backup or rebuild artefacts
        self.assertEqual(os.path.getsize(self.db_path), size_before)
        self.assertEqual([f for f in os.listdir(self.work_dir) if ".bak" in f or ".rebuild" in f], [])
        self.assertEqual(quick_check(self.db_path), "ok")

    def test_corruption_signal_classifier(self):
        from geest.core.gpkg_doctor import _is_corruption_signal

        self.assertTrue(_is_corruption_signal("failed (malformed database schema)"))
        self.assertTrue(_is_corruption_signal("failed (database disk image is malformed)"))
        self.assertTrue(_is_corruption_signal('failed (trigger "x" already exists)'))
        self.assertTrue(_is_corruption_signal("row 3 missing from index idx_foo"))
        self.assertFalse(_is_corruption_signal("failed (database is locked)"))
        self.assertFalse(_is_corruption_signal("failed (unable to open database file)"))

    def test_heal_report_summary_readable(self):
        report = HealReport(path=self.db_path, healthy=True)
        self.assertIn("no repair needed", report.summary())


if __name__ == "__main__":
    unittest.main()
