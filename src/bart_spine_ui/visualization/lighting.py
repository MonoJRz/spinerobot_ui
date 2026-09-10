"""Camera-relative studio lighting for anatomy and implant surfaces."""

import vtk


def configure_studio_lighting(renderer: vtk.vtkRenderer) -> None:
    renderer.AutomaticLightCreationOff()
    renderer.RemoveAllLights()
    renderer.SetBackground(0.025, 0.035, 0.05)
    renderer.SetBackground2(0.11, 0.14, 0.18)
    renderer.GradientBackgroundOn()
    renderer.UseFXAAOn()
    for position, intensity, color in (
        ((-0.6, 0.8, 1.0), 0.85, (1.0, 0.97, 0.93)),
        ((0.8, 0.25, 0.6), 0.35, (0.88, 0.94, 1.0)),
        ((0.2, 0.8, -0.8), 0.55, (0.95, 0.97, 1.0)),
    ):
        light = vtk.vtkLight()
        light.SetLightTypeToCameraLight()
        light.SetPosition(*position)
        light.SetFocalPoint(0, 0, 0)
        light.SetColor(*color)
        light.SetIntensity(intensity)
        light.PositionalOff()
        renderer.AddLight(light)
