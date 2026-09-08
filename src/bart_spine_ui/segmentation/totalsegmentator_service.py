import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import SimpleITK as sitk

from ..imaging.conversion import sitk_to_vtk
from ..imaging.models import MedicalVolume
from .models import SegmentationVolume

THORACIC_LUMBAR_ROIS = tuple(
    [f"vertebrae_T{i}" for i in range(1, 13)] + [f"vertebrae_L{i}" for i in range(1, 6)]
)


@dataclass(slots=True)
class SegmentationRun:
    executable: str
    arguments: list[str]
    input_path: Path
    output_dir: Path

    @property
    def expected_masks(self) -> tuple[Path, ...]:
        return tuple(self.output_dir / f"{roi}.nii.gz" for roi in THORACIC_LUMBAR_ROIS)


class TotalSegmentatorService:
    """Prepare, validate, and load full-resolution T1-L5 TotalSegmentator runs."""

    def __init__(self, *, device: str | None = None):
        self.device = device or os.environ.get("BART_TOTALSEG_DEVICE", "gpu")

    def prepare_run(self, volume: MedicalVolume) -> SegmentationRun:
        if volume.is_demo or volume.source_path is None:
            raise RuntimeError("Load a clinical CT in Setup before running segmentation.")

        executable = self._resolve_executable()
        output_dir = self.output_directory(volume.source_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Avoid stale masks being mistaken for a successful new inference.
        for roi in THORACIC_LUMBAR_ROIS:
            (output_dir / f"{roi}.nii.gz").unlink(missing_ok=True)

        # TotalSegmentator accepts NIfTI. Export the canonical in-memory CT so
        # DICOM, NRRD, MHA, and NIfTI inputs all follow one consistent path.
        input_path = output_dir / "_totalseg_input.nii.gz"
        sitk.WriteImage(volume.sitk_image, str(input_path), True)

        arguments = [
            "-i",
            str(input_path),
            "-o",
            str(output_dir),
            "--task",
            "total",
            "--roi_subset",
            *THORACIC_LUMBAR_ROIS,
            "--device",
            self.device,
        ]

        return SegmentationRun(
            executable=executable,
            arguments=arguments,
            input_path=input_path,
            output_dir=output_dir,
        )

    def load_result(
        self,
        run: SegmentationRun,
        reference: MedicalVolume,
    ) -> SegmentationVolume:
        return self.load_from_directory(run.output_dir, reference)

    def load_from_directory(
        self,
        output_dir: str | Path,
        reference: MedicalVolume,
        *,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> SegmentationVolume:
        """Combine individual masks on the exact CT grid as integer labels."""

        output_dir = Path(output_dir).expanduser().resolve()
        missing = [
            output_dir / f"{roi}.nii.gz"
            for roi in THORACIC_LUMBAR_ROIS
            if not (output_dir / f"{roi}.nii.gz").is_file()
        ]
        if missing:
            raise RuntimeError(
                f"Cannot load segmentation; {len(missing)} vertebra masks are missing."
            )

        reference_image = reference.sitk_image
        combined = sitk.Image(reference_image.GetSize(), sitk.sitkUInt16)
        combined.CopyInformation(reference_image)
        identity = sitk.Transform(reference_image.GetDimension(), sitk.sitkIdentity)
        labels: dict[int, str] = {}

        for label_value, roi in enumerate(THORACIC_LUMBAR_ROIS, start=1):
            if progress_callback is not None:
                progress_callback(
                    round((label_value - 1) / len(THORACIC_LUMBAR_ROIS) * 85),
                    f'Loading {roi.removeprefix("vertebrae_")} mask...',
                )
            mask = sitk.ReadImage(str(output_dir / f"{roi}.nii.gz"))
            aligned = sitk.Resample(
                mask,
                reference_image,
                identity,
                sitk.sitkNearestNeighbor,
                0,
                sitk.sitkUInt8,
            )
            binary = sitk.Cast(aligned > 0, sitk.sitkUInt16)
            combined = sitk.Maximum(combined, binary * label_value)
            labels[label_value] = roi.removeprefix("vertebrae_")

        if progress_callback is not None:
            progress_callback(90, "Preparing segmentation volume...")
        vtk_image = sitk_to_vtk(combined)
        if progress_callback is not None:
            progress_callback(100, "Segmentation masks loaded")

        return SegmentationVolume(
            sitk_image=combined,
            vtk_image=vtk_image,
            labels=labels,
            source_directory=output_dir,
        )

    @staticmethod
    def output_directory(source_path: Path) -> Path:
        source_path = source_path.expanduser().resolve()
        ct_directory = source_path if source_path.is_dir() else source_path.parent
        return ct_directory / "segmentation"

    @staticmethod
    def cleanup(run: SegmentationRun) -> None:
        try:
            run.input_path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def missing_masks(run: SegmentationRun) -> list[Path]:
        return [path for path in run.expected_masks if not path.exists()]

    @staticmethod
    def _resolve_executable() -> str:
        configured = os.environ.get("BART_TOTALSEG_EXECUTABLE")
        if configured:
            path = Path(configured).expanduser()
            if path.is_file():
                return str(path)
            raise RuntimeError(f"BART_TOTALSEG_EXECUTABLE does not point to a file: {path}")

        common_venv = Path.home() / ".venvs" / "totalseg" / "bin" / "TotalSegmentator"
        if common_venv.is_file():
            return str(common_venv)

        executable = shutil.which("TotalSegmentator")
        if executable:
            return executable

        raise RuntimeError(
            "TotalSegmentator was not found. Install it in ~/.venvs/totalseg "
            "or set BART_TOTALSEG_EXECUTABLE to its executable path."
        )
