"""Optional OpenCascade backend, imported only in the export subprocess."""

import json
from pathlib import Path

import numpy as np
import trimesh
from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeSolid,
    BRepBuilderAPI_Sewing,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepLib import BRepLib
from OCP.gp import gp_Pnt
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_DocumentTool


def volume(shape):
    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties)
    return properties.Mass()


def enumerate_shapes(shape, kind):
    iterator = TopExp_Explorer(shape, kind)
    items = []
    while iterator.More():
        items.append(iterator.Current())
        iterator.Next()
    return items


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mesh_to_solid(mesh, name):
    require(
        mesh.is_watertight and mesh.is_winding_consistent,
        f"{name}: the surface is not a closed, consistently oriented mesh",
    )
    pieces = []
    # Preserve every closed connected component under its vertebra's name.
    for piece in mesh.split(only_watertight=False):
        require(piece.is_watertight, f"{name}: an open surface component was found")
        sewing = BRepBuilderAPI_Sewing(1e-5)
        for triangle in piece.triangles:
            polygon = BRepBuilderAPI_MakePolygon()
            for vertex in triangle:
                polygon.Add(gp_Pnt(*vertex))
            polygon.Close()
            sewing.Add(BRepBuilderAPI_MakeFace(polygon.Wire()).Face())
        sewing.Perform()
        shells = enumerate_shapes(sewing.SewedShape(), TopAbs_SHELL)
        require(len(shells) == 1, f"{name}: could not form a closed CAD shell")
        solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(shells[0])).Solid()
        BRepLib.OrientClosedSolid_s(solid)
        require(BRepCheck_Analyzer(solid).IsValid(), f"{name}: invalid CAD solid")
        require(volume(solid) > 0, f"{name}: nonpositive solid volume")
        pieces.append(solid)
    require(bool(pieces), f"{name}: empty surface")
    if name.startswith("Screw"):
        require(len(pieces) == 1, f"{name}: screw must contain exactly one solid")
    if len(pieces) == 1:
        return pieces[0], 1
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for piece in pieces:
        builder.Add(compound, piece)
    return compound, len(pieces)


def export_solids(output_directory, report, progress):
    output = Path(output_directory)
    document = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    compound = TopoDS_Compound()
    BRep_Builder().MakeCompound(compound)
    root = shapes.AddShape(compound, True)
    TDataStd_Name.Set_s(root, TCollection_ExtendedString("Spine_Planned_Screws_LPS_mm"))
    scene = trimesh.Scene()
    (output / "step_parts").mkdir(exist_ok=True)
    for part in report["parts"]:
        name = part["name"]
        mesh_path = output / "stl" / f"{name}.stl"
        mesh = trimesh.load_mesh(mesh_path, process=True)
        mesh.fix_normals(multibody=True)
        solid, solid_count = mesh_to_solid(mesh, name)
        mesh.export(mesh_path)
        label = shapes.AddShape(solid, False)
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))
        colors.SetColor(label, Quantity_Color(*part["color"], Quantity_TOC_RGB), XCAFDoc_ColorGen)
        component = shapes.AddComponent(root, label, TopLoc_Location())
        TDataStd_Name.Set_s(component, TCollection_ExtendedString(name))
        writer = STEPControl_Writer()
        require(
            writer.Transfer(solid, STEPControl_AsIs) == IFSelect_RetDone,
            f"{name}: STEP conversion failed",
        )
        require(
            writer.Write(str(output / "step_parts" / f"{name}.step")) == IFSelect_RetDone,
            f"{name}: STEP file could not be written",
        )
        mesh.visual.vertex_colors = np.array(
            [*[int(c * 255) for c in part["color"]], 255], dtype="uint8"
        )
        scene.add_geometry(mesh, node_name=name, geom_name=name)
        part.update(
            {
                "cad_valid": True,
                "cad_solid_count": solid_count,
                "volume_mm3": volume(solid),
                "mesh_watertight": True,
                "mesh_winding_consistent": True,
            }
        )
        progress(f"{name}: CAD solid verified")
    shapes.UpdateAssemblies()
    progress("Saving the STEP assembly")
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    writer.SetColorMode(True)
    require(writer.Transfer(document, STEPControl_AsIs), "Assembly STEP conversion failed")
    step_path = output / "spine_screws_assembly.step"
    require(writer.Write(str(step_path)) == IFSelect_RetDone, "Could not write STEP assembly")
    glb_scene = scene.copy()
    glb_scene.apply_transform(np.diag([0.001, 0.001, 0.001, 1]))
    glb_scene.export(output / "spine_screws_assembly.glb")
    with (output / "spine_screws_assembly.obj").open("w") as stream:
        offset = 1
        for name, mesh in scene.geometry.items():
            stream.write(f"o {name}\ng {name}\n")
            for vertex in mesh.vertices:
                stream.write("v " + " ".join(f"{value:.7f}" for value in vertex) + "\n")
            for face in mesh.faces:
                stream.write("f " + " ".join(str(value) for value in face + offset) + "\n")
            offset += len(mesh.vertices)
    progress("Reopening STEP to verify all parts")
    reader = STEPControl_Reader()
    require(reader.ReadFile(str(step_path)) == IFSelect_RetDone, "Could not reopen STEP assembly")
    reader.TransferRoots()
    solids = enumerate_shapes(reader.OneShape(), TopAbs_SOLID)
    expected_count = sum(part["cad_solid_count"] for part in report["parts"])
    require(len(solids) == expected_count, "STEP round trip changed the solid count")
    require(
        all(BRepCheck_Analyzer(solid).IsValid() for solid in solids),
        "Invalid solid after STEP round trip",
    )
    expected_volume = sum(part["volume_mm3"] for part in report["parts"])
    actual_volume = sum(volume(solid) for solid in solids)
    error = abs(expected_volume - actual_volume) / expected_volume
    require(error < 1e-6, "STEP round trip changed the model volume")
    report["assembly_validation"] = {
        "round_trip_solid_count": len(solids),
        "all_solids_valid": True,
        "expected_solid_count": expected_count,
        "named_part_count": len(report["parts"]),
        "volume_relative_error": error,
    }
    (output / "geometry_report.json").write_text(json.dumps(report, indent=2))
    progress(f"Complete: {len(report['parts'])} named parts, {len(solids)} valid solids")
