# -*- coding: utf-8 -*-
import os
import unittest

from qgis.core import (
    QgsFeedback,
    QgsProcessingContext,
)
from utilities_for_testing import prepare_fixtures

from geest.core import JsonTreeItem
from geest.core.workflows import MultiBufferDistancesNativeWorkflow


class TestMultiBufferDistancesNativeWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up shared resources for the test suite."""

        cls.test_data_directory = prepare_fixtures()
        cls.working_directory = os.path.join(cls.test_data_directory, "wee_score")

        cls.context = QgsProcessingContext()
        cls.feedback = QgsFeedback()

    def setUp(self):
        self.study_area_gpkg_path = (f"{self.working_directory}/study_area/study_area.gpkg",)
        self.road_network_layer_path = os.path.join(
            os.path.dirname(__file__),
            "test_data",
            "network_analysis",
            "network_layer.shp",
        )
        self.points_layer_path = os.path.join(
            os.path.dirname(__file__),
            "test_data",
            "network_analysis",
            "points.shp",
        )

        self.analysis_item = JsonTreeItem({"id": "analysis_1"}, role="analysis", parent=None)
        self.dimension_item = JsonTreeItem({"id": "dimension_1"}, role="dimension", parent=self.analysis_item)
        self.factor_item = JsonTreeItem({"id": "factor_1"}, role="factor", parent=self.dimension_item)
        self.test_data = [
            "Test Item TestMultiBufferDistancesNativeWorkflow",
            "Configured",
            1.0,
            {  # attributes dictionary
                "analysis_mode": "use_multibuffer_point",
                "default_factor_weighting": 1.0,
                "default_dimension_weighting": 1.0,
                "default_analysis_weighting": 1.0,
                "description": "Multibuffer Native Test",
                "factor_weighting": 1.0,
                "dimension_weighting": 1.0,
                "analysis_weighting": 1.0,
                "id": "street_crossings",
                "result": "Not Run",
                "multi_buffer_travel_distances": "1000,2000,3000",
                "multi_buffer_point_shapefile": self.points_layer_path,
                "multi_buffer_travel_mode": "Walking",
                "multi_buffer_travel_units": "Distance",
                "road_network_layer_path": self.road_network_layer_path,
            },
        ]
        self.indicator_item = JsonTreeItem(
            self.test_data,
            role="indicator",
            parent=self.factor_item,
        )

    def test_run(self):
        """Test creating a running the workflow."""

        # Assign the top-level item
        self.working_directory = self.working_directory
        self.workflow = MultiBufferDistancesNativeWorkflow(
            item=self.indicator_item,
            cell_size_m=10.0,
            analysis_scale="local",
            feedback=self.feedback,
            context=self.context,
            working_directory=self.working_directory,
        )
        self.workflow.execute()

    def test_run_no_isochrones_uses_zero_score_fallback(self):
        """No isochrones (e.g. no points reachable from the road network)
        should produce a neutral 0-scored raster rather than an error.

        Regression test for issue #381.
        """
        workflow = MultiBufferDistancesNativeWorkflow(
            item=self.indicator_item,
            cell_size_m=10.0,
            analysis_scale="local",
            feedback=self.feedback,
            context=self.context,
            working_directory=self.working_directory,
        )
        # Simulate network analysis completing without producing isochrones
        workflow.create_isochrones = lambda **kwargs: None
        result = workflow.execute()
        self.assertTrue(result)
        self.assertEqual(
            self.indicator_item.attribute("result"),
            f"{workflow.workflow_name} Workflow Completed",
        )
        result_file = self.indicator_item.attribute("result_file")
        self.assertTrue(result_file)
        self.assertTrue(os.path.exists(result_file))


if __name__ == "__main__":
    unittest.main()
