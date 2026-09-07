from enum import Enum


class CoordinateConvention(str, Enum):
    """Patient coordinate convention used by a data object or API boundary."""

    LPS = "LPS"
    RAS = "RAS"


class SliceOrientation(str, Enum):
    AXIAL = "axial"
    CORONAL = "coronal"
    SAGITTAL = "sagittal"
