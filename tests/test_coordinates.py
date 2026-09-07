import numpy as np

from bart_spine_ui.core.coordinates import lps_to_ras, ras_to_lps


def test_lps_ras_roundtrip():
    lps = np.array([12.0, -24.0, 31.5])
    ras = lps_to_ras(lps)

    assert np.allclose(ras, [-12.0, 24.0, 31.5])
    assert np.allclose(ras_to_lps(ras), lps)


def test_coordinate_validation():
    try:
        lps_to_ras([1, 2])
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for a non-3D point")
