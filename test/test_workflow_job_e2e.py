# -*- coding: utf-8 -*-
"""End-to-end 'run a model' test through the production execution path.

The unit suite exercises processors directly, but every QGIS 4 field crash
lived in the layer above: WorkflowQueueManager.add_workflow constructing a
WorkflowJob, the WorkflowFactory dispatching on analysis_mode, and the
workflow __init__ reading the item's data-source attributes. This test
drives that exact chain — a configured indicator runs to completion and an
unconfigured one is declined gracefully — on both the PyQt5 and PyQt6
images.
"""

import os
import unittest

from qgis.PyQt.QtCore import QSettings
from utilities_for_testing import get_qgis_app, prepare_fixtures

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()

from geest.core import JsonTreeItem  # noqa: E402
from geest.core.workflow_queue_manager import WorkflowQueueManager  # noqa: E402


def make_indicator(attributes):
    """Build a minimal analysis→dimension→factor→indicator chain."""
    analysis = JsonTreeItem({"id": "analysis_1"}, role="analysis", parent=None)
    dimension = JsonTreeItem({"id": "dimension_1"}, role="dimension", parent=analysis)
    factor = JsonTreeItem({"id": "factor_1"}, role="factor", parent=dimension)
    data = ["E2E indicator", "Configured", 1.0, attributes]
    return JsonTreeItem(data, role="indicator", parent=factor)


class TestWorkflowJobEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_data_directory = prepare_fixtures()
        cls.working_directory = os.path.join(cls.test_data_directory, "wee_score")
        # WorkflowJob does not pass a working directory — production
        # workflows read it from QSettings, so the test does the same.
        QSettings().setValue("last_working_directory", cls.working_directory)

    def test_configured_indicator_runs_through_queue(self):
        """A configured indicator executes end-to-end via the job queue."""
        points = os.path.join(os.path.dirname(__file__), "test_data", "points", "points.shp")
        item = make_indicator(
            {
                "analysis_mode": "use_point_per_cell",
                "id": "e2e_points_per_cell",
                "description": "E2E point per cell",
                "result": "Not Run",
                "default_factor_weighting": 1.0,
                "factor_weighting": 1.0,
                "point_per_cell_shapefile": points,
            }
        )
        manager = WorkflowQueueManager(pool_size=1)
        job = manager.add_workflow(item, cell_size_m=1000.0, analysis_scale="local")
        self.assertIsNotNone(job, "configured indicator must be accepted by the queue")

        manager.start_processing_in_foreground()

        result = item.attribute("result", "")
        error = item.attribute("error", "")
        self.assertIn(
            "Completed",
            result,
            msg=f"workflow did not complete: result={result!r} error={error!r}",
        )
        result_file = item.attribute("result_file", "")
        self.assertTrue(result_file, "completed workflow must record a result_file")
        self.assertTrue(os.path.exists(result_file), f"missing output: {result_file}")

    def test_mode_switch_does_not_orphan_configured_layer(self):
        """A polyline indicator configured through the OSM transport mode
        keys must still be accepted when analysis_mode is the plain
        polyline mode (Active Transport supports both modes)."""
        polylines = os.path.join(os.path.dirname(__file__), "test_data", "polylines", "polylines.shp")
        item = make_indicator(
            {
                "analysis_mode": "use_polyline_per_cell",
                "id": "e2e_mode_switch",
                "description": "E2E mode-switch fallback",
                "result": "Not Run",
                "osm_transport_polyline_per_cell_layer_source": polylines,
            }
        )
        manager = WorkflowQueueManager(pool_size=1)
        job = manager.add_workflow(item, cell_size_m=1000.0, analysis_scale="local")
        self.assertIsNotNone(job, "layer configured under the sibling mode key must be accepted")

    def test_unconfigured_indicator_is_declined_not_crashed(self):
        """An indicator without a data source is skipped, not a TypeError."""
        item = make_indicator(
            {
                "analysis_mode": "use_polyline_per_cell",
                "id": "e2e_unconfigured",
                "description": "E2E unconfigured indicator",
                "result": "Not Run",
            }
        )
        manager = WorkflowQueueManager(pool_size=1)
        job = manager.add_workflow(item, cell_size_m=1000.0, analysis_scale="local")
        self.assertIsNone(job, "unconfigured indicator must be declined by the queue")


if __name__ == "__main__":
    unittest.main()
