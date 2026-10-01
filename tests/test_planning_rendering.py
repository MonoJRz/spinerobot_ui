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


def test_breach_line_connects_actual_endpoints_at_true_scale():
    import numpy as np

    from bart_spine_ui.planning.assessment import ScrewAssessment
    from bart_spine_ui.ui.pages.planning_construct_page import PlanningPage

    result = ScrewAssessment(.3, 'B', np.array([0., 20.]), np.array([100., 200.]),
                             np.ones(2), breach_point_lps=(12.3, 20., 30.),
                             bone_point_lps=(12., 20., 30.), breach_depth_mm=15.)
    actor, label = PlanningPage._breach_actors(result)
    data = actor.GetMapper().GetInput()
    np.testing.assert_allclose(data.GetPoint(0), result.bone_point_lps)
    np.testing.assert_allclose(data.GetPoint(1), result.breach_point_lps)
    assert np.isclose(np.linalg.norm(np.array(data.GetPoint(1))-data.GetPoint(0)), .3)
    assert label.GetInput() == '0.3 mm'
    result.breach_mm = 0
    assert PlanningPage._breach_actors(result) == []
    assert PlanningPage._breach_actors(None) == []


def test_locate_breach_uses_raw_geometry_and_perpendicular_camera():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import numpy as np

    from bart_spine_ui.planning.assessment import ScrewAssessment
    from bart_spine_ui.ui.pages.planning_construct_page import PlanningPage

    result = ScrewAssessment(.3, 'B', np.array([0., 40.]), np.array([100., 200.]),
                             np.ones(2), breach_point_lps=(3.3, -15., 0.),
                             bone_point_lps=(3., -15., 0.), breach_depth_mm=15.)
    cube = vtk.vtkCubeSource()
    cube.Update()
    result.boundary_mesh = cube.GetOutput()
    result.screw_mesh = cube.GetOutput()
    renderer = vtk.vtkRenderer()
    panel = SimpleNamespace(renderer=renderer, segmentation_actor=vtk.vtkActor(),
                            vtk_widget=MagicMock())
    workspace = SimpleNamespace(three_d=panel, _clear_three_d_overlays=MagicMock(),
                                _three_d_actors=[], _cylinder_actor=PlanningWorkspace._cylinder_actor)
    plan = ScrewPlan('L4', 'left', (0, 0, 0), (0, -1, 0), (0, -40, 0),
                     40, 8, 6, 40, (0, 0, 1))
    page = SimpleNamespace(_assessments={('L4', 'left'): result}, plans={('L4', 'left'): plan},
                           workspace=workspace, construct_review=MagicMock(),
                           _breach_actors=PlanningPage._breach_actors)
    PlanningPage._locate_breach(page, ('L4', 'left'))
    assert len(workspace._three_d_actors) == 4
    assert not panel.segmentation_actor.GetVisibility()
    camera = renderer.GetActiveCamera()
    np.testing.assert_allclose(camera.GetFocalPoint(), result.breach_point_lps)
    # The measured line runs in X; the camera views it from Z, not end-on.
    assert abs(camera.GetDirectionOfProjection()[0]) < 1e-6
    assert camera.GetParallelScale() == 2
    page.construct_review.overview_button.show.assert_called_once()


def test_construct_keeps_screws_when_rods_are_toggled():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QApplication

    from bart_spine_ui.planning.rod import build_rod_plan
    from bart_spine_ui.ui.pages.planning_construct_page import ConstructReviewWidget, PlanningPage

    app = QApplication.instance() or QApplication([])
    review = ConstructReviewWidget()
    renderer = vtk.vtkRenderer()
    workspace = SimpleNamespace(
        three_d=SimpleNamespace(renderer=renderer, vtk_widget=MagicMock()),
        _three_d_actors=[],
        _screw_actor=PlanningWorkspace._screw_actor,
        _tulip_actors=PlanningWorkspace._tulip_actors,
        _cylinder_actor=PlanningWorkspace._cylinder_actor,
    )

    def clear():
        for actor in workspace._three_d_actors:
            renderer.RemoveActor(actor)
        workspace._three_d_actors.clear()

    workspace._clear_three_d_overlays = clear
    plans = {
        (level, "left"): ScrewPlan(level, "left", (0, 0, z), (0, -1, 0),
                                  (0, -40, z), 40, 8, 6.5, 40, (0, 0, 1))
        for level, z in (("L3", 0), ("L4", 30))
    }
    page = SimpleNamespace(
        workspace=workspace, construct_review=review, plans=plans, _assessments={},
        _rod_plans={"left": build_rod_plan(plans, "left"), "right": None},
        _restore_review_segmentation=MagicMock(),
        _breach_actors=PlanningPage._breach_actors, _tube_actor=PlanningPage._tube_actor,
    )
    try:
        for visible in (True, False, True):
            review.rods_visible.setChecked(visible)
            PlanningPage._render_construct(page)
            actors = workspace._three_d_actors
            assert len(actors) == (5 if visible else 4)
            assert renderer.GetActors().GetNumberOfItems() == len(actors)
            for actor in actors[:4]:
                assert renderer.HasViewProp(actor)
                assert actor.GetVisibility()
                assert actor.GetMapper().GetInput().GetNumberOfPolys() > 100
    finally:
        review.close()
        app.processEvents()
