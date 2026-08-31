# -*- coding: utf-8 -*-
"""Unit tests for PopulationVectorProcessingTask.

Tests the S2S vector demographics processing pipeline for Regional analysis.
"""

import os
import unittest

from qgis.core import QgsProcessingContext, QgsProject
from utilities_for_testing import prepare_fixtures

from geest.core.algorithms import PopulationVectorProcessingTask


class TestPopulationVectorProcessingTask(unittest.TestCase):
    """Test suite for PopulationVectorProcessingTask."""

    def setUp(self):
        """Set up the environment for the test."""
        self.context = QgsProcessingContext()
        self.project = QgsProject.instance()
        self.context.setProject(self.project)

        self.test_data_directory = prepare_fixtures()
        self.output_directory = os.path.join(self.test_data_directory, "output")

        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)

        self.gpkg_path = os.path.join(self.test_data_directory, "study_area", "study_area.gpkg")
        self.s2s_output_path = os.path.join(self.test_data_directory, "s2s_demographics.gpkg")
        self.s2s_field = "sum_pop_2024"

    @unittest.skip("Requires S2S demographics test data with H3 grid")
    def test_population_vector_processing(self):
        """Test the full population vector processing pipeline."""
        task = PopulationVectorProcessingTask(
            s2s_output_path=self.s2s_output_path,
            s2s_field=self.s2s_field,
            study_area_gpkg_path=self.gpkg_path,
            working_directory=self.output_directory,
            cell_size_m=1000,
            force_clear=True,
        )

        result = task.run()
        self.assertTrue(result, "Task did not complete successfully.")

        output_dir = os.path.join(self.output_directory, "population")
        output_files = os.listdir(output_dir)

        self.assertTrue(
            any(f.startswith("reclassified_") for f in output_files),
            "Reclassified rasters not created.",
        )
        self.assertTrue(
            "reclassified_population.vrt" in output_files,
            "Reclassified VRT not created.",
        )
        self.assertTrue(
            "reclassified_population.qml" in output_files,
            "Reclassified QML not created.",
        )

    @unittest.skip("Requires S2S demographics test data with H3 grid")
    def test_population_vector_processing_with_missing_s2s(self):
        """Test that processing fails gracefully when S2S data is missing."""
        task = PopulationVectorProcessingTask(
            s2s_output_path="/nonexistent/path.gpkg",
            s2s_field=self.s2s_field,
            study_area_gpkg_path=self.gpkg_path,
            working_directory=self.output_directory,
            cell_size_m=1000,
            force_clear=True,
        )

        result = task.run()
        self.assertFalse(result, "Task should fail when S2S data is missing.")


if __name__ == "__main__":
    unittest.main()
