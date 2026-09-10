import numpy as np
import pytest

from bart_spine_ui.assets.model.src.bart_spine_implant_models import (
    SUPPORTED_DIAMETERS_MM,
    SUPPORTED_LENGTHS_MM,
    local_to_world_matrix,
    make_screw_actor,
    make_tulip_actor,
    screw_asset_path,
    tulip_asset_path,
)


def test_every_selectable_implant_asset_exists():
    for diameter in SUPPORTED_DIAMETERS_MM:
        for length in SUPPORTED_LENGTHS_MM:
            assert screw_asset_path(diameter, length).is_file()
    assert tulip_asset_path().is_file()


def test_screw_mesh_size_placement_and_cache():
    origin = (40, -12, 8)
    direction = np.array((1, -2, 3), dtype=float)
    direction /= np.linalg.norm(direction)
    first = make_screw_actor(6.5, 40, origin, direction)
    second = make_screw_actor(6.5, 40, (0, 0, 0), (0, 0, 1))
    mesh = first.GetMapper().GetInput()
    assert mesh.GetNumberOfPolys() > 100
    assert mesh is second.GetMapper().GetInput()
    assert mesh.GetBounds()[4:] == pytest.approx((0, 40), abs=0.01)
    matrix = first.GetUserMatrix()
    assert matrix.MultiplyPoint((0, 0, 0, 1))[:3] == pytest.approx(origin)
    assert matrix.MultiplyPoint((0, 0, 40, 1))[:3] == pytest.approx(
        np.array(origin) + direction * 40
    )
    assert second.GetUserMatrix().MultiplyPoint((0, 0, 0, 1))[:3] == (0, 0, 0)


def test_tulip_mesh_and_slot_rotation():
    actor = make_tulip_actor((0, 0, 0), (0, 0, 1), (0, 1, 0))
    mesh = actor.GetMapper().GetInput()
    assert mesh.GetNumberOfPolys() > 100
    assert mesh.GetBounds()[4:] == pytest.approx((-15, 0), abs=0.01)
    assert actor.GetUserMatrix().MultiplyPoint((1, 0, 0, 0))[:3] == pytest.approx((0, 1, 0))
    # A parallel rod tangent must still produce a valid orthonormal frame.
    matrix = local_to_world_matrix((1, 2, 3), (0, 0, 1), (0, 0, 1))
    rotation = np.array([[matrix.GetElement(i, j) for j in range(3)] for i in range(3)])
    assert rotation.T @ rotation == pytest.approx(np.eye(3))
    assert np.linalg.det(rotation) == pytest.approx(1)
