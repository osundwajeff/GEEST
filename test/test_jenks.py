# -*- coding: utf-8 -*-
"""
Unit tests for the dynamic min-max (equal-count quantile) classification module.
"""

import unittest

import numpy as np

from geest.core.grid_column_utils import _value_matches_range
from geest.core.jenks import (
    calculate_goodness_of_variance_fit,
    jenks_natural_breaks,
)


def build_reclass_table(breaks) -> list:
    """Mirror SafetyRasterWorkflow._build_reclass_table_from_breaks."""
    reclass_table = ["-inf", str(breaks[0]), "0"]
    for i in range(len(breaks) - 1):
        reclass_table.extend([str(breaks[i]), str(breaks[i + 1]), str(i + 1)])
    return reclass_table


def assign_classes(data, breaks) -> list:
    """Assign each value to a class using the workflow's range semantics."""
    table = build_reclass_table(breaks)
    parsed = []
    for i in range(0, len(table), 3):
        lower, upper, score = table[i], table[i + 1], table[i + 2]
        lower = float("-inf") if isinstance(lower, str) and "inf" in lower else float(lower)
        upper = float("inf") if isinstance(upper, str) and "inf" in upper else float(upper)
        parsed.append((lower, upper, float(score)))

    classes = []
    for value in data:
        mapped = None
        for lower, upper, score in parsed:
            if _value_matches_range(float(value), lower, upper, 0):
                mapped = score
                break
        classes.append(mapped)
    return classes


class TestJenksNaturalBreaks(unittest.TestCase):
    """Test suite for jenks_natural_breaks (dynamic min-max classifier)."""

    def test_basic_classification(self):
        """Test basic classification with simple data."""
        data = np.array([1, 2, 3, 10, 11, 12, 20, 21, 22])
        breaks = jenks_natural_breaks(data, n_classes=3)

        self.assertEqual(len(breaks), 3)
        self.assertTrue(breaks[0] <= breaks[1] <= breaks[2])
        self.assertEqual(breaks[-1], float(np.max(data)))

    def test_low_light_scenario(self):
        """Test classification with very low nighttime lights values."""
        data = np.array([0.0, 0.001, 0.002, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04])
        breaks = jenks_natural_breaks(data, n_classes=5)

        self.assertEqual(len(breaks), 5)
        self.assertTrue(all(0 <= b <= 0.04 for b in breaks))
        np.testing.assert_allclose(breaks[-1], 0.04, rtol=1e-6)

    def test_skewed_distribution_no_missing_values(self):
        """Every value must map to a class - no missing/unmapped cells."""
        rng = np.random.default_rng(42)
        low_values = rng.exponential(scale=0.5, size=900)
        high_values = rng.uniform(5, 10, size=100)
        data = np.concatenate([low_values, high_values])

        breaks = jenks_natural_breaks(data, n_classes=6)
        classes = assign_classes(data, breaks)

        self.assertEqual(len(breaks), 6)
        self.assertTrue(breaks[0] < breaks[-1])
        self.assertEqual(sum(1 for c in classes if c is None), 0, "values left unmapped")

    def test_last_break_is_data_max(self):
        """The final boundary must always be the data maximum."""
        rng = np.random.default_rng(11)
        data = np.clip(rng.lognormal(mean=5.1, sigma=0.9, size=3000), 96, 14440)
        breaks = jenks_natural_breaks(data, n_classes=6)
        self.assertEqual(breaks[-1], float(np.max(data)))

    def test_min_maps_to_class_zero_max_to_five(self):
        """The data minimum maps to class 0 and maximum to class 5."""
        rng = np.random.default_rng(5)
        data = np.clip(rng.lognormal(mean=5.1, sigma=0.9, size=3000), 96, 14440)
        breaks = jenks_natural_breaks(data, n_classes=6)
        classes = assign_classes(data, breaks)
        self.assertEqual(classes[int(np.argmin(data))], 0.0)
        self.assertEqual(classes[int(np.argmax(data))], 5.0)

    def test_zero_value_maps_to_class_zero(self):
        """NTL value 0 (no light) must map to class 0, not be left unmapped."""
        data = np.array([0.0, 0.0, 1.0, 5.0, 10.0, 100.0, 1000.0, 10000.0, 14000.0, 14440.0])
        breaks = jenks_natural_breaks(data, n_classes=6)
        classes = assign_classes(data, breaks)
        self.assertEqual(classes[0], 0.0)
        self.assertEqual(classes[1], 0.0)
        self.assertEqual(sum(1 for c in classes if c is None), 0)

    def test_uniform_distribution_evenly_spaced(self):
        """For uniform data, breaks should be roughly evenly spaced."""
        data = np.linspace(0, 100, 1000)
        breaks = jenks_natural_breaks(data, n_classes=4)

        self.assertEqual(len(breaks), 4)
        diffs = np.diff(breaks)
        self.assertTrue(np.std(diffs) < np.mean(diffs) * 0.5)

    def test_identical_values_no_missing(self):
        """All-identical data must still return n_classes breaks (all equal)."""
        data = np.array([5.0] * 100)
        breaks = jenks_natural_breaks(data, n_classes=3)

        self.assertEqual(len(breaks), 3)
        self.assertTrue(all(b == 5.0 for b in breaks))
        classes = assign_classes(data, breaks)
        self.assertEqual(sum(1 for c in classes if c is None), 0)
        self.assertEqual(set(classes), {0.0})

    def test_few_unique_values_no_missing(self):
        """Data with few unique values must still classify without errors."""
        data = np.array([1, 1, 1, 2, 2, 2])  # Only 2 unique values
        breaks = jenks_natural_breaks(data, n_classes=5)

        self.assertEqual(len(breaks), 5)
        classes = assign_classes(data, breaks)
        self.assertEqual(sum(1 for c in classes if c is None), 0)

    def test_two_classes_minimum(self):
        """Test that minimum 2 classes are required."""
        data = np.array([1, 2, 3, 4, 5])

        with self.assertRaises(ValueError) as context:
            jenks_natural_breaks(data, n_classes=1)
        self.assertIn("n_classes must be >= 2", str(context.exception))

    def test_empty_data(self):
        """Test error handling for empty data."""
        data = np.array([])

        with self.assertRaises(ValueError) as context:
            jenks_natural_breaks(data, n_classes=3)
        self.assertIn("Data array is empty", str(context.exception))

    def test_nan_handling(self):
        """Test that NaN values are properly filtered."""
        data = np.array([1, 2, np.nan, 3, 4, np.nan, 5, 6, 7, 8, 9, 10])
        breaks = jenks_natural_breaks(data, n_classes=3)

        self.assertEqual(len(breaks), 3)
        self.assertFalse(np.any(np.isnan(breaks)))

    def test_inf_handling(self):
        """Test that infinite values are properly filtered."""
        data = np.array([1, 2, 3, np.inf, 4, 5, -np.inf, 6, 7, 8, 9, 10])
        breaks = jenks_natural_breaks(data, n_classes=3)

        self.assertEqual(len(breaks), 3)
        self.assertFalse(np.any(np.isinf(breaks)))

    def test_large_dataset(self):
        """Test with a large dataset."""
        rng = np.random.default_rng(999)
        data = rng.uniform(0, 100, size=100000)

        breaks = jenks_natural_breaks(data, n_classes=5)

        self.assertEqual(len(breaks), 5)
        self.assertTrue(breaks[0] < breaks[-1])

    def test_breaks_monotonic_increasing(self):
        """Test that breaks are always monotonically increasing."""
        rng = np.random.default_rng(456)
        data = rng.exponential(scale=2, size=1000)

        for n_classes in range(2, 8):
            breaks = jenks_natural_breaks(data, n_classes=n_classes)
            self.assertTrue(all(breaks[i] <= breaks[i + 1] for i in range(len(breaks) - 1)))

    def test_deterministic_results(self):
        """Test that same data produces same breaks (deterministic)."""
        data = np.array([1.5, 2.3, 3.1, 4.8, 5.2, 6.9, 7.4, 8.1, 9.7])

        breaks1 = jenks_natural_breaks(data, n_classes=3)
        breaks2 = jenks_natural_breaks(data, n_classes=3)

        np.testing.assert_array_almost_equal(breaks1, breaks2)

    def test_float32_data(self):
        """Test with float32 data (common for raster data)."""
        data = np.array([1.5, 2.3, 3.1, 4.8, 5.2], dtype=np.float32)
        breaks = jenks_natural_breaks(data, n_classes=2)

        self.assertEqual(len(breaks), 2)
        self.assertIsInstance(breaks, list)

    def test_integer_data(self):
        """Test with integer data."""
        data = np.array([1, 2, 3, 10, 11, 12, 20, 21, 22], dtype=np.int32)
        breaks = jenks_natural_breaks(data, n_classes=3)

        self.assertEqual(len(breaks), 3)
        self.assertEqual(breaks[-1], 22.0)


class TestGoodnessOfVarianceFit(unittest.TestCase):
    """Test suite for calculate_goodness_of_variance_fit function."""

    def test_perfect_classification(self):
        """Test GVF with well-separated classes."""
        data = np.array([1, 1, 1, 10, 10, 10, 100, 100, 100])
        breaks = jenks_natural_breaks(data, n_classes=3)

        gvf = calculate_goodness_of_variance_fit(data, breaks)

        self.assertTrue(0.0 <= gvf <= 1.0)
        self.assertTrue(gvf > 0.2)

    def test_gvf_range(self):
        """Test that GVF is always between 0 and 1."""
        rng = np.random.default_rng(789)
        data = rng.uniform(0, 100, size=1000)

        for n_classes in range(2, 6):
            breaks = jenks_natural_breaks(data, n_classes=n_classes)
            gvf = calculate_goodness_of_variance_fit(data, breaks)

            self.assertTrue(0.0 <= gvf <= 1.0)

    def test_gvf_with_identical_values(self):
        """Test GVF when all values are identical."""
        data = np.array([5.0] * 100)
        breaks = [5.0]

        gvf = calculate_goodness_of_variance_fit(data, breaks)

        np.testing.assert_allclose(gvf, 1.0)

    def test_gvf_with_nan_values(self):
        """Test GVF filtering of NaN values."""
        data = np.array([1, 2, np.nan, 3, 10, 11, np.nan, 12])
        breaks = [3, 12]

        gvf = calculate_goodness_of_variance_fit(data, breaks)

        self.assertTrue(0.0 <= gvf <= 1.0)
        self.assertFalse(np.isnan(gvf))

    def test_gvf_empty_data(self):
        """Test GVF with empty valid data."""
        data = np.array([np.nan, np.nan, np.inf])
        breaks = [1, 2, 3]

        gvf = calculate_goodness_of_variance_fit(data, breaks)

        self.assertEqual(gvf, 0.0)

    def test_gvf_increases_with_classes(self):
        """Test that GVF generally increases with more classes."""
        rng = np.random.default_rng(321)
        data = rng.exponential(scale=5, size=1000)

        gvf_values = []
        for n_classes in range(2, 8):
            breaks = jenks_natural_breaks(data, n_classes=n_classes)
            gvf = calculate_goodness_of_variance_fit(data, breaks)
            gvf_values.append(gvf)

        self.assertTrue(
            all(
                gvf_values[i] <= gvf_values[i + 1] + 0.01  # Allow small floating point variations
                for i in range(len(gvf_values) - 1)
            )
        )


if __name__ == "__main__":
    unittest.main()
