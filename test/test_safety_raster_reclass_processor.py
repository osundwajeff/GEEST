# -*- coding: utf-8 -*-
"""Unit tests for SafetyRasterWorkflow classification table logic.

The table-building methods (_build_noaa_table, _build_reclassification_table,
_build_reclass_table_from_breaks) are pure numpy logic with no QGIS calls at
runtime.  We test them by replicating the logic as standalone helper functions
(identical to the workflow implementation) that can run without a QGIS
application context.

Run with:
    pytest test/test_safety_raster_reclass_processor.py -v
"""

import unittest

import numpy as np

from geest.core.grid_column_utils import _value_matches_range
from geest.core.jenks import jenks_natural_breaks

# ---------------------------------------------------------------------------
# Replicate the table-building methods as standalone functions.
# These are a direct copy of the logic in SafetyRasterWorkflow, allowing
# the tests to run without instantiating the QGIS-dependent class.
# ---------------------------------------------------------------------------


def _build_noaa_table(max_val: float) -> list:
    """Mirrors SafetyRasterWorkflow._build_noaa_table."""
    _ = max_val
    reclass_table = [
        "-inf",
        "0.5",
        "1",
        "0.5",
        "1",
        "2",
        "1",
        "5",
        "3",
        "5",
        "50",
        "4",
        "50",
        "inf",
        "5",
    ]
    return list(map(str, reclass_table))


def _build_reclass_table_from_breaks(breaks) -> list:
    """Mirrors SafetyRasterWorkflow._build_reclass_table_from_breaks."""
    reclass_table = ["-inf", str(breaks[0]), "0"]
    for i in range(len(breaks) - 1):
        reclass_table.extend([str(breaks[i]), str(breaks[i + 1]), str(i + 1)])
    return reclass_table


def _build_reclassification_table(attributes: dict, max_val: float, median: float, valid_data) -> list:
    """Mirrors SafetyRasterWorkflow._build_reclassification_table."""
    classification_mode = attributes.get("ntl_classification_mode", "jenks")
    if classification_mode == "noaa":
        return _build_noaa_table(max_val)
    breaks = jenks_natural_breaks(valid_data, n_classes=6)
    return _build_reclass_table_from_breaks(breaks)


def _assign_classes(values, table) -> list:
    """Assign each value to a class using the workflow's range semantics."""
    parsed = []
    for i in range(0, len(table), 3):
        lower, upper, score = table[i], table[i + 1], table[i + 2]
        lower = float("-inf") if isinstance(lower, str) and "inf" in lower else float(lower)
        upper = float("inf") if isinstance(upper, str) and "inf" in upper else float(upper)
        parsed.append((lower, upper, float(score)))

    classes = []
    for value in values:
        mapped = None
        for lower, upper, score in parsed:
            if _value_matches_range(float(value), lower, upper, 0):
                mapped = score
                break
        classes.append(mapped)
    return classes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildNoaaTable(unittest.TestCase):
    """Tests for the NOAA threshold table builder."""

    def test_length(self):
        """NOAA table must have exactly 15 elements: [min, max, cls] × 5."""
        self.assertEqual(len(_build_noaa_table(100.0)), 15)

    def test_class_scores(self):
        """Five classes with scores 1, 2, 3, 4, 5 in order."""
        t = _build_noaa_table(50.0)
        scores = [int(t[i]) for i in range(2, 15, 3)]
        self.assertEqual(scores, [1, 2, 3, 4, 5])

    def test_thresholds(self):
        """The fixed NOAA boundaries must be 0.5, 1, 5, 50."""
        t = _build_noaa_table(99.0)
        self.assertEqual(t[1], "0.5")
        self.assertEqual(t[4], "1")
        self.assertEqual(t[7], "5")
        self.assertEqual(t[10], "50")

    def test_table_uses_infinite_bounds(self):
        """NOAA table should cover all values with -inf and inf bounds."""
        t = _build_noaa_table(99.0)
        self.assertEqual(t[0], "-inf")
        self.assertEqual(t[13], "inf")

    def test_all_strings(self):
        """All entries must be strings (QGIS reclassifybytable requirement)."""
        for entry in _build_noaa_table(42.0):
            self.assertIsInstance(entry, str)

    def test_zero_maps_to_score_one(self):
        """Value 0 must map to score 1 (no/faint light), not be left unmapped."""
        t = _build_noaa_table(99.0)
        classes = _assign_classes([0.0], t)
        self.assertEqual(classes[0], 1.0)

    def test_threshold_boundary_assignment(self):
        """Values at thresholds map to the correct NOAA scores."""
        t = _build_noaa_table(99.0)
        classes = _assign_classes([0.25, 0.75, 2.0, 25.0, 75.0], t)
        self.assertEqual(classes, [1.0, 2.0, 3.0, 4.0, 5.0])


class TestBuildReclassificationTable(unittest.TestCase):
    """Tests for _build_reclassification_table dispatching and output."""

    # --- NOAA mode ---

    def test_noaa_mode_returns_15_elements(self):
        attrs = {"ntl_classification_mode": "noaa"}
        data = np.array([0.0, 0.0, 0.0, 5.0, 10.0, 20.0], dtype=np.float32)
        t = _build_reclassification_table(attrs, 20.0, 0.0, data)
        self.assertEqual(len(t), 15)

    def test_noaa_mode_scores(self):
        attrs = {"ntl_classification_mode": "noaa"}
        data = np.array([0.0, 1.0, 2.0], dtype=np.float32)
        t = _build_reclassification_table(attrs, 2.0, 1.0, data)
        scores = [int(t[i]) for i in range(2, 15, 3)]
        self.assertEqual(scores, [1, 2, 3, 4, 5])

    # --- dynamic min-max ("jenks") mode ---

    def test_jenks_mode_returns_18_elements(self):
        """6 classes × 3 values each = 18 elements."""
        attrs = {"ntl_classification_mode": "jenks"}
        rng = np.random.default_rng(42)
        data = rng.uniform(0.1, 100.0, size=500).astype(np.float32)
        t = _build_reclassification_table(attrs, float(data.max()), float(np.median(data)), data)
        self.assertEqual(len(t), 18)

    def test_jenks_mode_all_strings(self):
        attrs = {"ntl_classification_mode": "jenks"}
        rng = np.random.default_rng(0)
        data = rng.uniform(0.1, 80.0, size=200).astype(np.float32)
        t = _build_reclassification_table(attrs, float(data.max()), float(np.median(data)), data)
        for entry in t:
            self.assertIsInstance(entry, str)

    def test_jenks_first_class_starts_at_minus_inf(self):
        """The first class must extend from -inf so no values are left unmapped."""
        attrs = {"ntl_classification_mode": "jenks"}
        rng = np.random.default_rng(1)
        data = rng.uniform(0.1, 50.0, size=300).astype(np.float32)
        t = _build_reclassification_table(attrs, float(data.max()), float(np.median(data)), data)
        self.assertEqual(t[0], "-inf")

    def test_jenks_last_break_is_data_max(self):
        """The final boundary must be the data maximum so the full range is covered."""
        attrs = {"ntl_classification_mode": "jenks"}
        rng = np.random.default_rng(3)
        data = rng.uniform(0.1, 14440.0, size=300).astype(np.float32)
        t = _build_reclassification_table(attrs, float(data.max()), float(np.median(data)), data)
        self.assertAlmostEqual(float(t[16]), float(data.max()), places=3)

    def test_jenks_class_numbers_ascending(self):
        """Class scores in the table must be 0, 1, 2, 3, 4, 5 in order."""
        attrs = {"ntl_classification_mode": "jenks"}
        rng = np.random.default_rng(7)
        data = rng.uniform(0.0, 100.0, size=400).astype(np.float32)
        t = _build_reclassification_table(attrs, float(data.max()), float(np.median(data)), data)
        scores = [int(t[i]) for i in range(2, 18, 3)]
        self.assertEqual(scores, [0, 1, 2, 3, 4, 5])

    def test_skewed_data_has_no_missing_values(self):
        """Every value must map to a class - no missing/unmapped cells."""
        rng = np.random.default_rng(7)
        data = np.clip(rng.lognormal(mean=5.1, sigma=0.9, size=3000), 96, 14440)
        t = _build_reclassification_table({}, 0.0, 0.0, data)
        classes = _assign_classes(data, t)
        self.assertEqual(sum(1 for c in classes if c is None), 0, "values left unmapped")

    def test_min_maps_to_class_zero_max_to_five(self):
        """The data minimum maps to class 0 and the maximum to class 5."""
        rng = np.random.default_rng(5)
        data = np.clip(rng.lognormal(mean=5.1, sigma=0.9, size=3000), 96, 14440)
        t = _build_reclassification_table({}, 0.0, 0.0, data)
        classes = _assign_classes(data, t)
        self.assertEqual(classes[int(np.argmin(data))], 0.0)
        self.assertEqual(classes[int(np.argmax(data))], 5.0)

    def test_zero_value_maps_to_class_zero(self):
        """NTL value 0 (no light) must map to class 0, not be left unmapped."""
        data = np.array([0.0, 0.0, 1.0, 5.0, 10.0, 100.0, 1000.0, 10000.0, 14000.0, 14440.0])
        t = _build_reclassification_table({}, 0.0, 0.0, data)
        classes = _assign_classes(data, t)
        self.assertEqual(classes[0], 0.0)
        self.assertEqual(classes[1], 0.0)
        self.assertEqual(sum(1 for c in classes if c is None), 0)

    def test_skewed_data_classes_are_balanced(self):
        """Equal-count (quantile) breaks must give a roughly balanced distribution."""
        rng = np.random.default_rng(11)
        data = np.clip(rng.lognormal(mean=5.1, sigma=0.9, size=3000), 96, 14440)
        t = _build_reclassification_table({}, 0.0, 0.0, data)
        classes = _assign_classes(data, t)
        counts = [sum(1 for c in classes if c == score) for score in range(6)]
        self.assertLess(max(counts), len(data) * 0.45, f"class counts too skewed: {counts}")
        self.assertGreaterEqual(min(counts), 1, f"an empty class: {counts}")

    def test_constant_data_has_no_missing_values(self):
        """Degenerate all-equal data must still map every value (to class 0)."""
        data = np.full(50, 5.0)
        t = _build_reclassification_table({}, 0.0, 0.0, data)
        classes = _assign_classes(data, t)
        self.assertEqual(sum(1 for c in classes if c is None), 0)
        self.assertEqual(set(classes), {0.0})

    # --- backward compat / default ---

    def test_missing_attribute_defaults_to_dynamic(self):
        """No ntl_classification_mode in attributes → 6-class dynamic (18-element table)."""
        attrs = {}  # simulate old saved model without the key
        rng = np.random.default_rng(99)
        data = rng.uniform(0.1, 75.0, size=250).astype(np.float32)
        t = _build_reclassification_table(attrs, float(data.max()), float(np.median(data)), data)
        self.assertEqual(len(t), 18)
        self.assertEqual(t[0], "-inf")


if __name__ == "__main__":
    unittest.main()
