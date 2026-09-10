# ruff: noqa: I001
import vtk

# Match application startup: the existing UI package eagerly imports its pages.
from bart_spine_ui.ui import MainWindow  # noqa: F401
from bart_spine_ui.planning.models import ScrewPlan
from bart_spine_ui.planning.workspace import PlanningWorkspace
from bart_spine_ui.visualization.lighting import configure_studio_lighting


def test_workspace_mesh_factories_used_by_construct_review():
    plan = ScrewPlan("L4", "left", (0, 0, 0), (0, -1, 0), (0, -40, 0), 40, 8, 6.5, 40, (0, 0, 1))
    screw = PlanningWorkspace._screw_actor(plan, color=(0.6, 0.7, 0.8), opacity=1)
    tulips = PlanningWorkspace._tulip_actors(
        plan, color=(1, 0.7, 0.2), opacity=1, slot_direction=(0, 0, 1)
    )
    assert screw.GetMapper().GetInput().GetNumberOfPolys() > 100
    assert len(tulips) == 1
    assert tulips[0].GetMapper().GetInput().GetNumberOfPolys() > 100
    assert tulips[0].GetUserMatrix().MultiplyPoint((1, 0, 0, 0))[:3] == (0, 0, 1)


def test_lighting_does_not_accumulate_and_follows_camera():
    renderer = vtk.vtkRenderer()
    configure_studio_lighting(renderer)
    configure_studio_lighting(renderer)
    lights = renderer.GetLights()
    assert lights.GetNumberOfItems() == 3
    lights.InitTraversal()
    for _ in range(3):
        assert lights.GetNextItem().LightTypeIsCameraLight()
