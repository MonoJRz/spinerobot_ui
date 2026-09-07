import vtk


def default_window_level(scalar_min: float, scalar_max: float) -> tuple[float, float]:
    """Return a useful initial 2D window/level."""
    if scalar_min < -500 and scalar_max > 500:
        return 1800.0, 500.0

    window = max(1.0, scalar_max - scalar_min)
    level = 0.5 * (scalar_min + scalar_max)
    return float(window), float(level)


def configure_volume_property(
    volume_property: vtk.vtkVolumeProperty,
    scalar_min: float,
    scalar_max: float,
) -> None:
    """Apply the current bone-oriented 3D rendering preset."""
    color = vtk.vtkColorTransferFunction()
    opacity = vtk.vtkPiecewiseFunction()

    if scalar_min < -500 and scalar_max > 500:
        color.AddRGBPoint(-1000, 0.0, 0.0, 0.0)
        color.AddRGBPoint(-200, 0.12, 0.10, 0.09)
        color.AddRGBPoint(150, 0.55, 0.42, 0.35)
        color.AddRGBPoint(400, 0.85, 0.75, 0.65)
        color.AddRGBPoint(1000, 1.0, 0.95, 0.85)
        color.AddRGBPoint(2000, 1.0, 1.0, 1.0)

        opacity.AddPoint(-1000, 0.0)
        opacity.AddPoint(100, 0.0)
        opacity.AddPoint(250, 0.03)
        opacity.AddPoint(450, 0.12)
        opacity.AddPoint(900, 0.35)
        opacity.AddPoint(1800, 0.65)
    else:
        span = max(1.0, scalar_max - scalar_min)
        p20 = scalar_min + 0.20 * span
        p50 = scalar_min + 0.50 * span
        p80 = scalar_min + 0.80 * span

        color.AddRGBPoint(scalar_min, 0.0, 0.0, 0.0)
        color.AddRGBPoint(p50, 0.55, 0.55, 0.55)
        color.AddRGBPoint(scalar_max, 1.0, 1.0, 1.0)

        opacity.AddPoint(scalar_min, 0.0)
        opacity.AddPoint(p20, 0.0)
        opacity.AddPoint(p50, 0.08)
        opacity.AddPoint(p80, 0.30)
        opacity.AddPoint(scalar_max, 0.60)

    volume_property.SetColor(color)
    volume_property.SetScalarOpacity(opacity)
