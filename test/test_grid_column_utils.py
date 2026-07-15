# -*- coding: utf-8 -*-
"""Tests for key-based grid column write utilities."""

import os
import shutil
import tempfile
import unittest

from osgeo import ogr

from geest.core.grid_column_utils import write_joined_values_to_grid


class TestWriteJoinedValuesToGrid(unittest.TestCase):
    """Validate direct key join writes from external GPKG into study_area_grid."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_grid_join_")
        self.main_gpkg = os.path.join(self.temp_dir, "study_area.gpkg")
        self.source_gpkg = os.path.join(self.temp_dir, "s2s.gpkg")

        self._create_study_area_grid()
        self._create_source_layer()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_study_area_grid(self):
        driver = ogr.GetDriverByName("GPKG")
        dataset = driver.CreateDataSource(self.main_gpkg)
        layer = dataset.CreateLayer("study_area_grid", geom_type=ogr.wkbPolygon)
        layer.CreateField(ogr.FieldDefn("h3_index", ogr.OFTString))
        layer.CreateField(ogr.FieldDefn("area_name", ogr.OFTString))

        layer_defn = layer.GetLayerDefn()
        for hex_id, area_name in [
            ("h3_a", "Area 1"),
            ("h3_b", "Area 1"),
            ("h3_c", "Area 2"),
        ]:
            feature = ogr.Feature(layer_defn)
            feature.SetField("h3_index", hex_id)
            feature.SetField("area_name", area_name)
            layer.CreateFeature(feature)

        dataset = None

    def _create_source_layer(self):
        driver = ogr.GetDriverByName("GPKG")
        dataset = driver.CreateDataSource(self.source_gpkg)
        layer = dataset.CreateLayer("s2s_nighttime_lights", geom_type=ogr.wkbPoint)
        layer.CreateField(ogr.FieldDefn("hex_id", ogr.OFTString))
        layer.CreateField(ogr.FieldDefn("sum_viirs_ntl_2024", ogr.OFTReal))

        layer_defn = layer.GetLayerDefn()
        for hex_id, value in [
            ("h3_a", 10.5),
            ("h3_b", 20.5),
            ("h3_extra", 999.0),
        ]:
            feature = ogr.Feature(layer_defn)
            feature.SetField("hex_id", hex_id)
            feature.SetField("sum_viirs_ntl_2024", value)
            layer.CreateFeature(feature)

        dataset = None

    def _read_grid_values(self, column_name):
        dataset = ogr.Open(self.main_gpkg, 0)
        layer = dataset.GetLayerByName("study_area_grid")
        values = {}
        for feature in layer:
            values[feature.GetField("h3_index")] = feature.GetField(column_name)
        dataset = None
        return values

    def test_write_joined_values_to_grid_updates_matching_rows(self):
        updated_count = write_joined_values_to_grid(
            gpkg_path=self.main_gpkg,
            column_name="nighttime_lights",
            source_gpkg=self.source_gpkg,
            source_layer="s2s_nighttime_lights",
            source_key_field="hex_id",
            target_key_field="h3_index",
            source_value_field="sum_viirs_ntl_2024",
        )

        self.assertEqual(updated_count, 2)
        values = self._read_grid_values("nighttime_lights")
        self.assertAlmostEqual(values["h3_a"], 10.5)
        self.assertAlmostEqual(values["h3_b"], 20.5)
        self.assertIsNone(values["h3_c"])

    def test_write_joined_values_to_grid_respects_area_filter(self):
        updated_count = write_joined_values_to_grid(
            gpkg_path=self.main_gpkg,
            column_name="nighttime_lights",
            source_gpkg=self.source_gpkg,
            source_layer="s2s_nighttime_lights",
            source_key_field="hex_id",
            target_key_field="h3_index",
            source_value_field="sum_viirs_ntl_2024",
            area_name="Area 1",
        )

        self.assertEqual(updated_count, 2)
        values = self._read_grid_values("nighttime_lights")
        self.assertAlmostEqual(values["h3_a"], 10.5)
        self.assertAlmostEqual(values["h3_b"], 20.5)
        self.assertIsNone(values["h3_c"])


if __name__ == "__main__":
    unittest.main()


class TestWriteBufferValuesToGrid(unittest.TestCase):
    """Buffer-to-grid scoring must survive invalid geometries and CRS drift.

    Field regression: scored isochrone hulls (frequently self-intersecting)
    produced 'Found 0 grid cells with intersecting buffers' on strict GEOS
    builds, writing 0 into every cell while the run reported success.
    """

    ORIGIN_X = 700000.0
    ORIGIN_Y = 1516000.0
    CELL = 1000.0

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_grid_buffer_")
        self.main_gpkg = os.path.join(self.temp_dir, "study_area.gpkg")
        driver = ogr.GetDriverByName("GPKG")
        dataset = driver.CreateDataSource(self.main_gpkg)
        from osgeo import osr

        srs = osr.SpatialReference()
        srs.ImportFromEPSG(32620)
        layer = dataset.CreateLayer("study_area_grid", srs, geom_type=ogr.wkbPolygon)
        layer.CreateField(ogr.FieldDefn("area_name", ogr.OFTString))
        layer_defn = layer.GetLayerDefn()
        for row in range(2):
            for col in range(2):
                x0 = self.ORIGIN_X + col * self.CELL
                y0 = self.ORIGIN_Y + row * self.CELL
                ring = ogr.Geometry(ogr.wkbLinearRing)
                for px, py in [
                    (x0, y0),
                    (x0 + self.CELL, y0),
                    (x0 + self.CELL, y0 + self.CELL),
                    (x0, y0 + self.CELL),
                    (x0, y0),
                ]:
                    ring.AddPoint(px, py)
                polygon = ogr.Geometry(ogr.wkbPolygon)
                polygon.AddGeometry(ring)
                feature = ogr.Feature(layer_defn)
                feature.SetField("area_name", "test_area")
                feature.SetGeometry(polygon)
                layer.CreateFeature(feature)
        dataset = None

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _scored_cells(self, column):
        dataset = ogr.Open(self.main_gpkg, 0)
        layer = dataset.GetLayerByName("study_area_grid")
        values = [feature.GetField(column) for feature in layer]
        dataset = None
        return values

    def _buffer_layer(self, wkt, crs="EPSG:32620"):
        from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer

        layer = QgsVectorLayer(f"Polygon?crs={crs}&field=value:integer", "buffers", "memory")
        feature = QgsFeature(layer.fields())
        feature.setAttribute("value", 5)
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        layer.dataProvider().addFeature(feature)
        layer.updateExtents()
        return layer

    def test_invalid_bowtie_buffer_is_repaired_and_scores_cells(self):
        from geest.core.grid_column_utils import write_buffer_values_to_grid

        x0, y0 = self.ORIGIN_X, self.ORIGIN_Y
        x1, y1 = x0 + 2 * self.CELL, y0 + 2 * self.CELL
        # Self-intersecting hourglass spanning the whole grid
        bowtie = f"POLYGON(({x0} {y0}, {x1} {y1}, {x1} {y0}, {x0} {y1}, {x0} {y0}))"
        layer = self._buffer_layer(bowtie)
        self.assertFalse(next(layer.getFeatures()).geometry().isGeosValid(), "fixture must be invalid")

        updated = write_buffer_values_to_grid(self.main_gpkg, "bowtie_col", layer)
        self.assertGreater(updated, 0, "invalid buffer geometry must be repaired, not silently score nothing")
        self.assertIn(5.0, self._scored_cells("bowtie_col"))

    def test_mismatched_crs_buffer_is_reprojected(self):
        from qgis.core import (
            QgsCoordinateReferenceSystem,
            QgsCoordinateTransform,
            QgsGeometry,
            QgsProject,
            QgsRectangle,
        )

        from geest.core.grid_column_utils import write_buffer_values_to_grid

        rect = QgsRectangle(self.ORIGIN_X, self.ORIGIN_Y, self.ORIGIN_X + 2 * self.CELL, self.ORIGIN_Y + 2 * self.CELL)
        transform = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:32620"),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsProject.instance(),
        )
        rect4326 = transform.transformBoundingBox(rect)
        wkt = QgsGeometry.fromRect(rect4326).asWkt()
        layer = self._buffer_layer(wkt, crs="EPSG:4326")

        updated = write_buffer_values_to_grid(self.main_gpkg, "crs_col", layer)
        self.assertGreater(updated, 0, "a 4326 buffer over a 32620 grid must be reprojected, not score nothing")
        self.assertIn(5.0, self._scored_cells("crs_col"))
