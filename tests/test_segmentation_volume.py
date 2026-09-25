import numpy as np
import pytest
import SimpleITK as sitk
import vtk

from bart_spine_ui.imaging.conversion import sitk_to_vtk
from bart_spine_ui.imaging.models import MedicalVolume
from bart_spine_ui.segmentation import THORACIC_LUMBAR_ROIS, TotalSegmentatorService
from bart_spine_ui.visualization.segmentation_colors import (
    MEDICAL_SEGMENTATION_COLORS,
    VERTEBRA_LABEL_COUNT,
    create_segmentation_lookup_table,
)
from bart_spine_ui.visualization.volume3d import (
    create_smoothed_segmentation_surface,
    reset_camera_to_posterior,
)


def _reference_volume(tmp_path):
    image = sitk.Image((4, 4, 3), sitk.sitkInt16)
    image.SetSpacing((0.7, 0.8, 1.2))
    image.SetOrigin((-30.0, 12.0, 4.5))
    image.SetDirection((0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0))
    return MedicalVolume(
        name="test CT",
        sitk_image=image,
        vtk_image=sitk_to_vtk(image),
        source_path=tmp_path / "ct.nii.gz",
    )


def test_load_masks_builds_label_map_on_exact_ct_grid(tmp_path):
    reference = _reference_volume(tmp_path)
    output_dir = tmp_path / "segmentation"
    output_dir.mkdir()

    for label, roi in enumerate(THORACIC_LUMBAR_ROIS, start=1):
        array = np.zeros((3, 4, 4), dtype=np.uint8)
        array.flat[label - 1] = 1
        mask = sitk.GetImageFromArray(array)
        mask.CopyInformation(reference.sitk_image)
        sitk.WriteImage(mask, str(output_dir / f"{roi}.nii.gz"))

    progress = []
    segmentation = TotalSegmentatorService().load_from_directory(
        output_dir,
        reference,
        progress_callback=lambda value, text: progress.append((value, text)),
    )

    assert segmentation.sitk_image.GetSize() == reference.sitk_image.GetSize()
    assert segmentation.sitk_image.GetSpacing() == reference.sitk_image.GetSpacing()
    assert segmentation.sitk_image.GetOrigin() == reference.sitk_image.GetOrigin()
    assert segmentation.sitk_image.GetDirection() == reference.sitk_image.GetDirection()
    assert set(np.unique(sitk.GetArrayFromImage(segmentation.sitk_image))) == set(range(18))
    assert segmentation.vtk_image.GetDimensions() == reference.vtk_image.GetDimensions()
    assert segmentation.labels[1] == "T1"
    assert segmentation.labels[17] == "L5"
    assert progress[-1] == (100, "Segmentation masks loaded")
    assert [value for value, _ in progress] == sorted(value for value, _ in progress)

    surfaces = vtk.vtkDiscreteMarchingCubes()
    surfaces.SetInputData(segmentation.vtk_image)
    surfaces.GenerateValues(17, 1, 17)
    surfaces.Update()
    assert surfaces.GetOutput().GetNumberOfCells() > 0


def test_load_masks_rejects_incomplete_result(tmp_path):
    with pytest.raises(RuntimeError, match="17 vertebra masks are missing"):
        TotalSegmentatorService().load_from_directory(tmp_path, _reference_volume(tmp_path))


def test_segmentation_lookup_table_uses_fixed_muted_palette():
    table = create_segmentation_lookup_table(opacity=0.35)

    assert len(MEDICAL_SEGMENTATION_COLORS) == VERTEBRA_LABEL_COUNT
    assert table.GetTableValue(0)[3] == pytest.approx(0.0)
    assert table.GetTableValue(1) == pytest.approx(
        tuple(channel / 255 for channel in MEDICAL_SEGMENTATION_COLORS[0]) + (0.35,),
        abs=0.002,
    )
    assert len({table.GetTableValue(label)[:3] for label in range(1, 18)}) == 17


def test_smoothed_segmentation_surface_preserves_labels_and_rounds_edges():
    array = np.zeros((24, 24, 24), dtype=np.uint8)
    array[5:12, 6:13, 7:14] = 1
    array[13:20, 6:13, 7:14] = 2

    surface = create_smoothed_segmentation_surface(
        sitk_to_vtk(sitk.GetImageFromArray(array))
    )

    assert surface.GetNumberOfCells() > 0
    scalars = surface.GetPointData().GetScalars()
    assert scalars.GetName() == "VertebraLabel"
    assert scalars.GetRange() == (1.0, 2.0)
    points = np.array(
        [surface.GetPoint(index) for index in range(surface.GetNumberOfPoints())]
    )
    assert np.any(np.abs(points * 2.0 - np.round(points * 2.0)) > 0.01)


def test_camera_is_reset_to_posterior_lps_view():
    cube = vtk.vtkCubeSource()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(cube.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    renderer = vtk.vtkRenderer()
    renderer.AddActor(actor)

    reset_camera_to_posterior(renderer)

    camera = renderer.GetActiveCamera()
    position = camera.GetPosition()
    focal_point = camera.GetFocalPoint()
    assert position[0] == pytest.approx(focal_point[0])
    assert position[1] > focal_point[1]
    assert position[2] == pytest.approx(focal_point[2])
    assert camera.GetDirectionOfProjection() == pytest.approx((0.0, -1.0, 0.0))
    assert camera.GetViewUp() == pytest.approx((0.0, 0.0, 1.0))


def test_prepare_run_uses_robust_crop(tmp_path, monkeypatch):
    service = TotalSegmentatorService(device="cpu")
    monkeypatch.setattr(service, "_resolve_executable", lambda: "/test/TotalSegmentator")
    run = service.prepare_run(_reference_volume(tmp_path))
    assert "--robust_crop" in run.arguments
    assert "--fast" not in run.arguments
    first_roi = run.arguments.index("--roi_subset") + 1
    assert run.arguments[first_roi:first_roi + len(THORACIC_LUMBAR_ROIS)] == list(
        THORACIC_LUMBAR_ROIS
    )


def test_overlapping_lumbar_masks_keep_single_labels_on_ct_grid(tmp_path):
    reference = _reference_volume(tmp_path)
    for roi in THORACIC_LUMBAR_ROIS:
        array = np.zeros((3, 4, 4), dtype=np.float32)
        if roi == "vertebrae_L2":
            array[1, 1, 1:3] = 0.5
        elif roi == "vertebrae_L3":
            array[1, 1, 1:3] = 256
        mask = sitk.GetImageFromArray(array)
        mask.CopyInformation(reference.sitk_image)
        if roi == "vertebrae_L3":
            mask.SetOrigin(reference.sitk_image.TransformIndexToPhysicalPoint((1, 0, 0)))
        sitk.WriteImage(mask, str(tmp_path / f"{roi}.nii.gz"))

    result = TotalSegmentatorService().load_from_directory(tmp_path, reference)
    labels = sitk.GetArrayFromImage(result.sitk_image)
    expected = np.zeros_like(labels)
    expected[1, 1, 1] = 14  # L2-only voxel survives.
    expected[1, 1, 2:4] = 15  # L3 wins the shared voxel without adding label IDs.
    np.testing.assert_array_equal(labels, expected)
    assert result.sitk_image.GetPixelID() == sitk.sitkUInt16
    assert result.sitk_image.GetOrigin() == reference.sitk_image.GetOrigin()
    assert result.sitk_image.GetDirection() == reference.sitk_image.GetDirection()


@pytest.mark.parametrize(
    "anatomy,levels,lumbar_only",
    [
        ("Lumbar Spine", ["L3", "L4", "L5"], True),
        ("Lumbar", [], True),
        (None, ["L1", "L2"], True),
        ("Thoracolumbar Spine", ["T12", "L1"], False),
        ("Lumbar Spine", ["T12", "L1"], False),
        ("Thoracic", [], False),
        (None, [], False),
    ],
)
def test_case_segmentation_subset(anatomy, levels, lumbar_only):
    from bart_spine_ui.segmentation.totalsegmentator_service import LUMBAR_ROIS, rois_for_case

    assert rois_for_case(anatomy, levels) == (
        LUMBAR_ROIS if lumbar_only else THORACIC_LUMBAR_ROIS
    )


def test_lumbar_run_and_loading_do_not_require_thoracic_masks(tmp_path, monkeypatch):
    from bart_spine_ui.segmentation.totalsegmentator_service import LUMBAR_ROIS

    service = TotalSegmentatorService(device="cpu")
    monkeypatch.setattr(service, "_resolve_executable", lambda: "/test/TotalSegmentator")
    reference = _reference_volume(tmp_path)
    run = service.prepare_run(reference, rois=LUMBAR_ROIS)
    first_roi = run.arguments.index("--roi_subset") + 1
    assert run.arguments[first_roi:run.arguments.index("--device")] == list(LUMBAR_ROIS)
    assert len(run.expected_masks) == 5
    for index, path in enumerate(run.expected_masks):
        array = np.zeros((3, 4, 4), dtype=np.uint8)
        array.flat[index] = 1
        mask = sitk.GetImageFromArray(array)
        mask.CopyInformation(reference.sitk_image)
        sitk.WriteImage(mask, str(path))
    assert service.missing_masks(run) == []
    result = service.load_result(run, reference)
    assert result.labels == {13 + index: f"L{index + 1}" for index in range(5)}
    assert set(np.unique(sitk.GetArrayFromImage(result.sitk_image))) == {0, 13, 14, 15, 16, 17}
