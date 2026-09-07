from collections.abc import Sequence

import numpy as np


def lps_to_ras(point: Sequence[float]) -> np.ndarray:
    """Convert a 3D patient point from DICOM/ITK LPS to RAS."""
    p = np.asarray(point, dtype=float)
    if p.shape != (3,):
        raise ValueError("point must contain exactly 3 values")
    return np.array([-p[0], -p[1], p[2]], dtype=float)


def ras_to_lps(point: Sequence[float]) -> np.ndarray:
    """Convert a 3D patient point from RAS to DICOM/ITK LPS."""
    # This transform is its own inverse.
    return lps_to_ras(point)
