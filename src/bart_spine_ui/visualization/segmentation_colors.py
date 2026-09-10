import vtk

VERTEBRA_LABEL_COUNT = 17
MPR_SEGMENTATION_OPACITY = 0.35

# Fixed, muted categorical colors keep adjacent vertebrae distinct without the
# artificial ordering and high saturation of a spectral rainbow.
MEDICAL_SEGMENTATION_COLORS = (
    (78, 121, 167),
    (242, 142, 43),
    (225, 87, 89),
    (118, 183, 178),
    (89, 161, 79),
    (237, 201, 72),
    (176, 122, 161),
    (255, 157, 167),
    (156, 117, 95),
    (186, 176, 172),
    (114, 158, 206),
    (255, 190, 125),
    (255, 151, 153),
    (158, 218, 229),
    (134, 188, 110),
    (255, 226, 138),
    (211, 166, 204),
)


def create_segmentation_lookup_table(*, opacity: float = 1.0) -> vtk.vtkLookupTable:
    """Create stable, muted categorical colors for the T1-L5 integer labels."""

    table = vtk.vtkLookupTable()
    table.SetNumberOfTableValues(VERTEBRA_LABEL_COUNT + 1)
    table.SetRange(0, VERTEBRA_LABEL_COUNT)
    table.SetTableValue(0, 0.0, 0.0, 0.0, 0.0)
    for label, rgb in enumerate(MEDICAL_SEGMENTATION_COLORS, start=1):
        red, green, blue = (channel / 255.0 for channel in rgb)
        table.SetTableValue(label, red, green, blue, opacity)
    table.Build()
    return table
