# -*- coding: utf-8 -*-
"""Unit tests for S2S demographics source detection in the analysis dialog.

These tests exercise the pure helper methods that decide whether the selected
population layer is the S2S demographics layer or a raster, without requiring a
QGIS application context.
"""

import os
import unittest

from geest.gui.dialogs.analysis_aggregation_dialog import AnalysisAggregationDialog


class TestLayerSourcePath(unittest.TestCase):
    """Tests for the layer source path normalization helpers."""

    def test_from_string_gpkg_with_sublayer_uri(self):
        """GPKG URI with sublayer spec normalizes to the bare file path."""
        uri = "/data/out/study_area/s2s_demographics.gpkg|layername=s2s_demographics"
        result = AnalysisAggregationDialog._layer_source_path_from_string(uri)
        self.assertEqual(result, "/data/out/study_area/s2s_demographics.gpkg")

    def test_from_string_plain_path(self):
        """A plain path without sublayer spec is unchanged."""
        path = "/data/out/population.tif"
        result = AnalysisAggregationDialog._layer_source_path_from_string(path)
        self.assertEqual(result, "/data/out/population.tif")

    def test_from_string_empty(self):
        """Empty input normalizes to the current working directory (abs of '')."""
        result = AnalysisAggregationDialog._layer_source_path_from_string("")
        self.assertEqual(result, os.path.abspath(os.getcwd()))

    def test_from_string_relative_path(self):
        """Relative paths are converted to absolute normalized forms."""
        result = AnalysisAggregationDialog._layer_source_path_from_string("./study_area/s2s_demographics.gpkg")
        self.assertTrue(result.endswith(os.path.join("study_area", "s2s_demographics.gpkg")))

    def test_s2s_paths_match_ignoring_sublayer(self):
        """The S2S output path and its layer URI compare equal after normalization."""
        s2s_path = "/data/out/study_area/s2s_demographics.gpkg"
        layer_uri = s2s_path + "|layername=s2s_demographics"
        self.assertEqual(
            AnalysisAggregationDialog._layer_source_path_from_string(s2s_path),
            AnalysisAggregationDialog._layer_source_path_from_string(layer_uri),
        )

    def test_different_files_do_not_match(self):
        """A raster file source does not match the S2S demographics path."""
        s2s_path = "/data/out/study_area/s2s_demographics.gpkg"
        raster_source = "/data/out/population/worldpop.tif"
        self.assertNotEqual(
            AnalysisAggregationDialog._layer_source_path_from_string(s2s_path),
            AnalysisAggregationDialog._layer_source_path_from_string(raster_source),
        )


if __name__ == "__main__":
    unittest.main()
