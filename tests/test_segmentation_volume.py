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
