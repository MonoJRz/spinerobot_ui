"""Run with python -m bart_spine_ui.exporting.cli SNAPSHOT OUTPUT."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy

from ..segmentation.surfaces import (
    SEGMENTATION_GAUSSIAN_RADIUS_FACTOR,
    SEGMENTATION_GAUSSIAN_SIGMA_VOXELS,
)
from .geometry import implant_surfaces, vertebra_surfaces, write_stl


def progress(message):
    print(f"PROGRESS {message}", flush=True)


def export_snapshot(snapshot_directory, output_directory):
    # Fail before processing if optional CAD dependencies are unavailable.
    from .solids import export_solids

    snapshot = Path(snapshot_directory)
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError("Choose a new output folder; existing exports are never overwritten.")
    request = json.loads((snapshot / "request.json").read_text())
    if request.get("coordinate_system") != "LPS" or request.get("units") != "mm":
        raise ValueError("CAD export requires patient LPS coordinates in millimetres.")
    reader = vtk.vtkXMLImageDataReader()
    reader.SetFileName(str(snapshot / "segmentation.vti"))
    reader.Update()
    if reader.GetOutput().GetPointData().GetScalars() is None:
        raise ValueError("No segmentation image in the export snapshot.")
    output.mkdir(parents=True)
    for folder in ("stl", "meshes_ui_resolution"):
        (output / folder).mkdir()
    report = {
        "coordinate_system": "LPS",
        "units": "mm",
        "parts": [],
        "source_directory": request.get("source_directory"),
        "smoothing": {
            "method": "same per-label Gaussian extraction as UI",
            "sigma_voxels": SEGMENTATION_GAUSSIAN_SIGMA_VOXELS,
            "radius_factor": SEGMENTATION_GAUSSIAN_RADIUS_FACTOR,
            "isovalue": 0.5,
            "cad_face_target_per_vertebra": 12000,
        },
        "plans": request["plans"],
    }
    (output / "source_planning.json").write_text(json.dumps(request, indent=2))

    def add(name, poly, color):
        write_stl(poly, output / "stl" / f"{name}.stl")
        report["parts"].append(
            {
                "name": name,
                "color": color,
                "triangles": poly.GetNumberOfCells(),
                "bounds_lps_mm": poly.GetBounds(),
            }
        )

    progress("Smoothing vertebrae using the 3D view's surface pipeline")
    bones = set()
    for name, reduced, full, color in vertebra_surfaces(reader.GetOutput(), request["labels"]):
        progress(f"Preparing {name}")
        bones.add(name)
        add(name, reduced, color)
        write_stl(full, output / "meshes_ui_resolution" / f"{name}.stl")
        errors = []
        for source, target in ((reduced, full), (full, reduced)):
            distance = vtk.vtkImplicitPolyDataDistance()
            distance.SetInput(target)
            vertices = vtk_to_numpy(source.GetPoints().GetData())
            # Uniformly sample up to 10,000 vertices per direction for a bounded check.
            sample = vertices[:: max(1, len(vertices) // 10000)]
            errors.extend(abs(distance.EvaluateFunction(v)) for v in sample)
        report["parts"][-1]["sampled_distance_from_ui_surface_mm"] = {
            "max": float(np.max(errors)),
            "p95": float(np.percentile(errors, 95)),
        }
    if not bones:
        raise ValueError("The segmentation contains no vertebral surfaces.")
    for plan in request["plans"]:
        if plan["level"] not in bones:
            raise ValueError(f"No segmented vertebra for the {plan['level']} screw.")
    for name, poly, color in implant_surfaces(request["plans"]):
        add(name, poly, color)
    export_solids(output, report, progress)
    (output / "README.md").write_text(
        "# Smoothed spine CAD export\n\n"
        "Open spine_screws_assembly.step as an assembly; preserve the separate named parts. "
        "All STEP/STL/OBJ coordinates are patient LPS in millimetres; do not auto-center parts. "
        "The GLB preview applies a 0.001 scale for metres and retains +Z superior.\n\n"
        "Vertebrae use the exact Gaussian surface extraction shared with the UI "
        "(sigma 1.5 voxels, radius factor 2, isovalue 0.5). "
        "meshes_ui_resolution contains those full-resolution surfaces. CAD/STL copies are "
        "reduced to at most approximately 12,000 faces per vertebra and remain faceted solids. "
        "geometry_report.json records the sampled differences from the UI surfaces.\n\n"
        "Each whole vertebra, screw shaft, and tulip head is a separate named part. "
        "Screws overlap the bone at the saved entry points and trajectories; no holes are cut. "
        "All current plans are included, with draft/accepted status preserved in source_planning.json. "
        "No additional screws or rods are inferred.\n\n"
        "Screw threads are generic (2.5 mm pitch, core diameter 72% of nominal, "
        "tip length 75% of nominal diameter); heads reuse the BART generic tulip. "
        "Head slots follow projected patient superior, not a fitted rod. "
        "This geometry is for visualization, not an implant manufacturing definition. "
        "The source research plan still requires manual verification.\n\n"
        "The STEP assembly was reopened and its solid count, validity, and summed volume checked.\n"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        export_snapshot(args.snapshot, args.output)
    except Exception as exc:  # noqa: BLE001 -- report native/backend failures to the parent UI
        print(f"ERROR {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
