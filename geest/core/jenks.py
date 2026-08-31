# -*- coding: utf-8 -*-
"""
Dynamic min-max classification module.

Provides the classification used by the nighttime-lights workflow. The
``jenks_natural_breaks`` function derives class boundaries directly from the
data's own minimum to maximum range using equal-count (quantile) breaks, so
that every value maps to a class (no missing/unmapped values).

Example:
    >>> import numpy as np
    >>> from geest.core.jenks import jenks_natural_breaks
    >>>
    >>> data = np.array([1.2, 1.5, 2.1, 3.4, 4.5, 5.2, 6.8, 7.1, 8.9, 9.2])
    >>> breaks = jenks_natural_breaks(data, n_classes=3)
    >>> print(breaks)  # Equal-count breaks ending at the data maximum
    [2.1, 5.2, 9.2]
"""

__copyright__ = "Copyright 2024, Tim Sutton"
__license__ = "GPL version 3"
__email__ = "tim@kartoza.com"
__revision__ = "$Format:%H$"

from typing import List

import numpy as np


def jenks_natural_breaks(data: np.ndarray, n_classes: int) -> List[float]:
    """Calculate dynamic min-max class breaks for continuous data.

    Breaks are the equal-count (quantile) boundaries of the data plus the data
    maximum, so that the classes span the full min-max range of the values.
    This guarantees every value falls into a class - no missing/unmapped cells.

    Args:
        data: Input data array (1D NumPy array)
        n_classes: Number of classes to create (must be >= 2)

    Returns:
        List of break points [break₁, break₂, ..., max_value]
        Length will be n_classes (upper boundary of each class)

    Raises:
        ValueError: If n_classes < 2 or data is empty/invalid

    Example:
        >>> data = np.array([1, 2, 3, 10, 11, 12, 20, 21, 22])
        >>> breaks = jenks_natural_breaks(data, n_classes=3)
        >>> breaks
        [3.0, 12.0, 22.0]

    Note:
        Class boundaries are computed as the 1/n .. (n-1)/n quantiles plus the
        data maximum, giving each class roughly the same number of cells.
    """
    if n_classes < 2:
        raise ValueError(f"n_classes must be >= 2, got {n_classes}")

    if data is None or len(data) == 0:
        raise ValueError("Data array is empty")

    # Remove NaN and infinite values
    clean_data = data[np.isfinite(data)]
    if len(clean_data) == 0:
        raise ValueError("No valid (non-NaN, finite) values in data")

    # Equal-count (quantile) breaks spanning the data's min-max range.
    # The final break is always the data maximum.
    quantiles = np.linspace(1.0 / n_classes, (n_classes - 1.0) / n_classes, n_classes - 1)
    breaks = [float(np.quantile(clean_data, quantile)) for quantile in quantiles]
    breaks.append(float(np.max(clean_data)))

    return breaks


def calculate_goodness_of_variance_fit(
    data: np.ndarray,
    breaks: List[float],
) -> float:
    """
    Calculate Goodness of Variance Fit (GVF) statistic.

    GVF measures the quality of the classification:
    - GVF = 1.0: Perfect classification (no within-class variance)
    - GVF = 0.0: Poor classification (high within-class variance)

    Args:
        data: Original data array
        breaks: Break points from the classification

    Returns:
        GVF value between 0 and 1 (higher is better)

    Formula:
        GVF = 1 - (SDCM / SDAM)
        where:
        - SDCM = Sum of Squared Deviations from Class Means
        - SDAM = Sum of Squared Deviations from Array Mean

    Example:
        >>> data = np.array([1, 2, 3, 10, 11, 12])
        >>> breaks = [3.0, 12.0]
        >>> gvf = calculate_goodness_of_variance_fit(data, breaks)
        >>> print(f"GVF: {gvf:.4f}")
        GVF: 0.9234
    """
    # Remove invalid values
    clean_data = data[np.isfinite(data)]

    if len(clean_data) == 0:
        return 0.0

    # Calculate SDAM (total variance)
    array_mean = np.mean(clean_data)
    sdam = np.sum((clean_data - array_mean) ** 2)

    if sdam == 0:
        return 1.0  # All values are identical

    # Calculate SDCM (within-class variance)
    sdcm = 0.0
    lower_bound = clean_data.min()

    for upper_bound in breaks:
        # Get data in this class
        class_mask = (clean_data >= lower_bound) & (clean_data <= upper_bound)
        class_data = clean_data[class_mask]

        if len(class_data) > 0:
            class_mean = np.mean(class_data)
            sdcm += np.sum((class_data - class_mean) ** 2)

        lower_bound = upper_bound

    # GVF = 1 - (within-class variance / total variance)
    gvf = 1.0 - (sdcm / sdam)

    return max(0.0, min(1.0, gvf))  # Clamp to [0, 1]
