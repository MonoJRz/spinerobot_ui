from pathlib import Path

import SimpleITK as sitk


def canonicalize_image(image: sitk.Image) -> sitk.Image:
    """
    Reorient to LPS when possible.

    DICOM and ITK naturally use LPS. Keeping one explicit internal convention avoids silently
    mixing Slicer-style RAS coordinates with ITK geometry later in planning/registration.
    """
    try:
        return sitk.DICOMOrient(image, "LPS")
    except Exception:
        return image


def read_image_file(path: str | Path) -> tuple[sitk.Image, str]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    image = sitk.ReadImage(str(path))
    return canonicalize_image(image), path.name


def read_dicom_directory(directory: str | Path) -> tuple[sitk.Image, str]:
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(directory)

    series_ids = sitk.ImageSeriesReader.GetGDCMSeriesIDs(str(directory))
    if not series_ids:
        raise RuntimeError("No DICOM series was found in this folder.")

    # Starter behavior: choose the first series.
    # Replace this with a DICOM browser/series selector in a later workflow.
    series_id = series_ids[0]
    filenames = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(
        str(directory),
        series_id,
    )

    reader = sitk.ImageSeriesReader()
    reader.SetFileNames(filenames)
    image = reader.Execute()

    return canonicalize_image(image), f"DICOM series {series_id}"
