"""Coordinate, artifact, snapshot, and lifecycle checks for Settings CAD export."""

import json
import os
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
import SimpleITK as sitk
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from vtk.util.numpy_support import vtk_to_numpy

from bart_spine_ui.exporting.geometry import (
    implant_surfaces,
    screw_transform,
    vertebra_surfaces,
)
from bart_spine_ui.imaging.conversion import sitk_to_vtk
from bart_spine_ui.planning.models import ScrewPlan
from bart_spine_ui.segmentation.models import SegmentationVolume
from bart_spine_ui.ui.cad_export_dialog import CadExportDialog
from bart_spine_ui.ui.procedure_shell import ProcedureShell


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def page(tmp_path):
    labels = np.zeros((32, 36, 40), dtype=np.uint16)
    labels[5:22, 5:24, 4:17] = 13
    labels[7:25, 6:25, 23:36] = 14
    image = sitk.GetImageFromArray(labels)
    image.SetSpacing((0.7, 1.1, 1.3))
    image.SetOrigin((10.0, 20.0, -100.0))
    segmentation = SegmentationVolume(image, sitk_to_vtk(image), {13: "L1", 14: "L2"}, tmp_path)
    plan = ScrewPlan(
        "L1",
        "left",
        (17.0, 26.0, -84.0),
        (0.0, 1.0, 0.0),
        (17.0, 38.0, -84.0),
        20,
        6,
        4,
        12,
        (0, 0, 1),
    )
    return SimpleNamespace(
        current_segmentation=segmentation,
        _running=False,
        plans={("L1", "left"): plan},
        accepted={("L1", "left")},
        case_region="L1–L2",
    )


def wait_until(app, predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(30)
    assert predicate(), "Export did not finish before the test deadline"


def test_gaussian_surface_remains_separate_in_patient_coordinates(page):
    surfaces = list(
        vertebra_surfaces(page.current_segmentation.vtk_image, page.current_segmentation.labels)
    )
    assert [name for name, *_ in surfaces] == ["L1", "L2"]
    first = surfaces[0][2]
    second = surfaces[1][2]
    assert first.GetBounds()[1] < second.GetBounds()[0]
    assert first.GetBounds()[4] < -70
    # Smoothed rounded corners must produce subvoxel coordinates rather than
    # only the mask's half-voxel marching-cubes steps.
    points = vtk_to_numpy(first.GetPoints().GetData())
    voxel_x = (points[:, 0] - 10) / 0.7
    assert np.mean(np.abs(voxel_x * 2 - np.round(voxel_x * 2)) > 0.01) > 0.1


def test_screw_alignment_and_vertical_axis_fallback(page):
    plan = page.plans[("L1", "left")].to_dict()
    matrix = screw_transform(plan)
    np.testing.assert_allclose(matrix @ [0, 0, 0, 1], [17, 26, -84, 1])
    np.testing.assert_allclose(matrix @ [0, 0, 12, 1], [17, 38, -84, 1])
    plan["direction_lps"] = [0, 0, 1]
    plan["endpoint_lps_mm"] = [17, 26, -72]
    vertical = screw_transform(plan)
    np.testing.assert_allclose(vertical[:3, :3].T @ vertical[:3, :3], np.eye(3))
    implants = list(implant_surfaces([plan]))
    assert [name for name, *_ in implants] == ["Screw_L1_left", "Head_L1_left"]
    plan["endpoint_lps_mm"] = [0, 0, 0]
    with pytest.raises(ValueError, match="endpoint"):
        screw_transform(plan)


def test_export_action_is_inside_settings(app):
    shell = ProcedureShell()
    emitted = []
    shell.cad_export_requested.connect(lambda: emitted.append(True))
    assert shell.settings_button.menu() is shell.settings_menu
    assert shell.export_cad_action in shell.settings_menu.actions()
    shell.export_cad_action.trigger()
    assert emitted == [True]
    shell.close()


def test_settings_export_publishes_snapshot_and_verified_separate_solids(app, page, tmp_path):
    pytest.importorskip("OCP")
    trimesh = pytest.importorskip("trimesh")
    dialog = CadExportDialog(page)
    output = tmp_path / "export"
    dialog._begin_export(output)
    try:
        assert dialog._busy
        assert not dialog.save_button.isEnabled()
        assert not output.exists()  # No partially written final model.
        # Editing or switching plans after clicking Export cannot alter this job.
        page.plans.clear()
        wait_until(app, lambda: not dialog._busy)
        assert output.is_dir(), dialog.status.text()
        report = json.loads((output / "geometry_report.json").read_text())
        assert report["assembly_validation"]["round_trip_solid_count"] == 4
        assert report["assembly_validation"]["all_solids_valid"]
        assert {p["name"] for p in report["parts"]} == {
            "L1",
            "L2",
            "Screw_L1_left",
            "Head_L1_left",
        }
        saved = json.loads((output / "source_planning.json").read_text())
        assert saved["plans"][0]["status"] == "accepted"
        assert saved["plans"][0]["entry_point_lps_mm"] == [17, 26, -84]
        scene = trimesh.load(output / "spine_screws_assembly.glb", force="scene")
        assert len(scene.geometry) == 4
        assert not list(tmp_path.glob(".spine-cad-*"))
    finally:
        dialog.stop_export()
        dialog.close()


def test_cancel_and_existing_destination_leave_no_partial_exports(app, page, tmp_path):
    dialog = CadExportDialog(page)
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("unchanged")
    dialog._begin_export(existing)
    assert not dialog._busy
    assert sentinel.read_text() == "unchanged"
    output = tmp_path / "cancelled"
    dialog._begin_export(output)
    dialog._cancel_export()
    wait_until(app, lambda: not dialog._busy)
    assert not output.exists()
    assert not list(tmp_path.glob(".spine-cad-*"))
    assert "cancelled" in dialog.status.text()
    dialog.close()


def test_missing_backend_recovers_controls(app, page, tmp_path, monkeypatch):
    monkeypatch.setenv("BART_CAD_PYTHON", str(tmp_path / "missing-python"))
    dialog = CadExportDialog(page)
    dialog._begin_export(tmp_path / "failed")
    wait_until(app, lambda: not dialog._busy)
    assert dialog.save_button.isEnabled()
    assert "failed" in dialog.status.text()
    assert not list(tmp_path.glob(".spine-cad-*"))
    dialog.close()
