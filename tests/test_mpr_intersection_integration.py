"""Exercise the view refresh, so a disconnected geometry helper is caught."""

# ruff: noqa: I001
from types import SimpleNamespace

import vtk
import pytest

from bart_spine_ui.ui import MainWindow  # noqa: F401
from bart_spine_ui.planning.models import ScrewPlan
from bart_spine_ui.planning.workspace import PlanningWorkspace


def test_view_refresh_uses_slice_section_and_removes_old_actors():
    class Panel:
        def __init__(self):
            self.renderer = vtk.vtkRenderer()
            self.reslice = vtk.vtkImageReslice()

        def render(self):
            pass

    panel = Panel()
    axes = vtk.vtkMatrix4x4()
    axes.Identity()
    panel.reslice.SetResliceAxes(axes)
    plan = ScrewPlan("L4", "left", (0, -20, 0), (0, 1, 0), (0, 20, 0), 40, 8, 6, 40, (0, 0, 1))
    workspace = SimpleNamespace(
        _mpr_overlay_actors={panel: []},
        _pending_entry_point=None,
        _active_plan=plan,
    )
    PlanningWorkspace._refresh_mpr_overlay(workspace, panel)
    actors = workspace._mpr_overlay_actors[panel]
    assert len(actors) == 2
    assert actors[0].GetMapper().GetInput().GetBounds() == pytest.approx(
        (-3, 3, -20, 20, 0, 0),
        abs=0.005,
    )
    for offset in (4, 0, 4, 0):
        axes.SetElement(2, 3, offset)
        PlanningWorkspace._refresh_mpr_overlay(workspace, panel)
        expected = 0 if offset == 4 else 2
        assert len(workspace._mpr_overlay_actors[panel]) == expected
        assert panel.renderer.GetViewProps().GetNumberOfItems() == expected
    workspace._active_plan = None
    PlanningWorkspace._refresh_mpr_overlay(workspace, panel)
    assert panel.renderer.GetViewProps().GetNumberOfItems() == 0
