"""Capture the current UI model without changing the saved clinical plan."""

import json
from pathlib import Path

import vtk


def write_snapshot(directory, segmentation, plans, accepted, case_region):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    writer = vtk.vtkXMLImageDataWriter()
    writer.SetFileName(str(directory / "segmentation.vti"))
    writer.SetInputData(segmentation.vtk_image)
    writer.SetDataModeToAppended()
    if not writer.Write():
        raise OSError("Could not snapshot the current segmentation.")
    request = {
        "coordinate_system": "LPS",
        "units": "mm",
        "case_region": case_region,
        "source_directory": str(segmentation.source_directory),
        "labels": segmentation.labels,
        "plans": [
            {**plan.to_dict(), "status": "accepted" if key in accepted else "draft"}
            for key, plan in sorted(plans.items())
        ],
    }
    (directory / "request.json").write_text(json.dumps(request, indent=2))
