import os
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from bart_spine_ui.ui import MainWindow  # noqa: F401
from bart_spine_ui.ui.pages.planning_construct_page import PlanningPage as ConstructPage
from bart_spine_ui.ui.pages.planning_page import PlanningPage
from bart_spine_ui.ui.planning_left_sidebar import PlanningLeftSidebar


def planner(queue):
    page = SimpleNamespace(
        _queue=queue, _target_index=0, current_segmentation=object(),
        plans={}, accepted=set(), skipped=set(), _auto_dimensions={},
        workspace=MagicMock(), left_sidebar=MagicMock(), status_changed=MagicMock(),
        _sync_screw_table=MagicMock(), _save_plans=MagicMock(),
        _activate_target=MagicMock(), _begin_entry_marking=MagicMock(),
    )
    page._finish_target = MethodType(PlanningPage._finish_target, page)
    return page


def test_skip_removes_existing_screw_and_advances_to_unresolved_target():
    first, second, third = ("L1", "left"), ("L1", "right"), ("L2", "left")
    page = planner([first, second, third])
    page.plans = {first: object(), second: object()}
    page.accepted = {first, second}
    page._auto_dimensions[first] = (6, 40)
    PlanningPage._skip_and_next(page)
    assert page.skipped == {first}
    assert first not in page.plans
    assert first not in page.accepted
    assert first not in page._auto_dimensions
    assert page._target_index == 2
    page._activate_target.assert_called_once()
    page._save_plans.assert_called_once()
    page.workspace.set_plans.assert_called_once_with(page.plans, active_key=None)


def test_completion_accepts_skipped_targets_but_not_unresolved_drafts():
    first, second = ("L1", "left"), ("L1", "right")
    page = planner([first, second])
    page.plans[first] = object()
    page.skipped.add(second)
    assert not ConstructPage._all_screws_accepted(page)
    PlanningPage._accept_and_next(page)
    assert ConstructPage._all_screws_accepted(page)
    page._activate_target.assert_not_called()
    # Replanning a skipped target removes its omission when accepted.
    page._target_index = 1
    page.plans[second] = object()
    PlanningPage._accept_and_next(page)
    assert not page.skipped
    assert page.accepted == {first, second}


def test_navigation_wraps_and_all_skipped_has_no_screws():
    first, second = ("L1", "left"), ("L1", "right")
    page = planner([first, second])
    page._target_index = 1
    PlanningPage._skip_and_next(page)
    assert page._target_index == 0
    PlanningPage._skip_and_next(page)
    assert not page.plans
    assert page.skipped == {first, second}
    assert "All targets skipped" in page.status_changed.emit.call_args.args[0]


def test_skip_button_works_without_a_screw_and_labels_skipped_target():
    app = QApplication.instance() or QApplication([])
    sidebar = PlanningLeftSidebar()
    sidebar.set_levels(["L1"])
    assert not sidebar.skip_button.isEnabled()
    sidebar.set_target(0, 2, "L1", "left", has_plan=False)
    events = []
    sidebar.skip_requested.connect(lambda: events.append(True))
    sidebar.skip_button.click()
    assert events == [True]
    sidebar.set_skipped({("L1", "left")})
    assert sidebar._target_buttons[("L1", "left")].text() == "Skip"
    sidebar.set_loading(True)
    assert not sidebar.skip_button.isEnabled()
    sidebar.reset_planning()
    assert not sidebar.skip_button.isEnabled()
    assert not sidebar._skipped
    sidebar.close()
    app.processEvents()
