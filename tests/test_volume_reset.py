from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtCore import QProcess

from bart_spine_ui.ui.pages.planning_construct_page import PlanningPage as ConstructPage
from bart_spine_ui.ui.pages.planning_page import PlanningPage


def make_page(volume):
    page = SimpleNamespace(
        _loaded_volume=object(), _displayed_volume=object(), _active=False,
        controller=SimpleNamespace(current_volume=volume),
        current_run=None, _run_volume=None, _running=False,
        current_segmentation=object(), plans={("L4", "left"): object()},
        accepted={("L4", "left")}, skipped={("L4", "right")}, _auto_dimensions={("L4", "left"): (6, 40)},
        _queue=[("L4", "left")], _target_index=2,
        workspace=MagicMock(), left_sidebar=MagicMock(), screw_table=MagicMock(),
        segmentation_service=MagicMock(), process=MagicMock(),
    )
    page.process.state.return_value = QProcess.ProcessState.NotRunning
    page._reset_volume_state = lambda: PlanningPage._reset_volume_state(page)
    return page


def test_volume_change_resets_inactive_planning_and_same_volume_preserves_it():
    volume = SimpleNamespace(name="New CT", source_path=None)
    page = make_page(volume)
    PlanningPage._on_volume_loaded(page, volume)
    assert page.current_segmentation is None
    assert not page.skipped
    assert not page.plans and not page.accepted and not page._auto_dimensions
    assert not page._queue and page._target_index == 0
    page.workspace.clear_segmentation.assert_called_once()
    page.left_sidebar.reset_planning.assert_called_once()
    page.screw_table.clear.assert_called_once()
    page.workspace.set_volume.assert_not_called()  # Rendering stays lazy.
    page.current_segmentation = result = object()
    PlanningPage._on_volume_loaded(page, volume)
    assert page.current_segmentation is result
    page.left_sidebar.reset_planning.assert_called_once()


def test_volume_change_stops_old_process_and_ignores_late_worker_events():
    volume = SimpleNamespace(name="New CT", source_path=None)
    page = make_page(volume)
    page.current_run = run = object()
    page._run_volume = old_volume = object()
    page._running = True
    page.process.state.return_value = QProcess.ProcessState.Running
    PlanningPage._on_volume_loaded(page, volume)
    page.process.kill.assert_called_once()
    page.process.waitForFinished.assert_called_once()
    page.segmentation_service.cleanup.assert_called_once_with(run)
    assert page.current_run is None and page._run_volume is None and not page._running
    worker = SimpleNamespace(volume=old_volume)
    page._load_workers = [worker]
    page.left_sidebar.reset_mock()
    PlanningPage._on_load_progress(page, worker, 80, "Old progress")
    PlanningPage._on_segmentation_loaded(page, worker, object(), old_volume, False)
    PlanningPage._on_segmentation_load_failed(page, worker, "Old error", old_volume)
    PlanningPage._on_process_finished(page, 1, None)
    assert not page.left_sidebar.mock_calls
    assert page.current_segmentation is None
    assert not page.skipped


def test_construct_review_is_cleared_on_volume_change(monkeypatch):
    monkeypatch.setattr(PlanningPage, "_reset_volume_state", lambda self: None)
    page = SimpleNamespace(
        construct_review=MagicMock(), _rod_plans={"left": object()},
        left_sidebar=MagicMock(), workspace=MagicMock(), screw_table=MagicMock(),
    )
    # super() requires a real instance; bypass QWidget construction for this state-only check.
    page_instance = ConstructPage.__new__(ConstructPage)
    for key, value in vars(page).items():
        setattr(page_instance, key, value)
    ConstructPage._reset_volume_state(page_instance)
    assert page_instance._rod_plans == {"left": None, "right": None}
    page.construct_review.set_construct.assert_called_once_with(
        [], set(), {"left": None, "right": None}
    )
    page.construct_review.hide.assert_called_once()
    page.left_sidebar.set_three_d_view.assert_called_once_with(page.workspace.three_d)


def test_sidebar_reset_restores_segmentation_action_and_clears_target():
    from PySide6.QtWidgets import QApplication

    from bart_spine_ui.ui.planning_left_sidebar import PlanningLeftSidebar

    app = QApplication.instance() or QApplication([])
    sidebar = PlanningLeftSidebar()
    sidebar.set_target(0, 1, "L4", "left", has_plan=True)
    sidebar.set_marking(True)
    sidebar.set_segmentation_ready(True)
    sidebar.set_running(True)
    sidebar.set_loading(True)
    sidebar.reset_planning()
    assert not sidebar.segmentation_button.isHidden()
    assert sidebar.segmentation_button.isEnabled()
    assert sidebar.loading_progress.isHidden()
    assert sidebar._active_key is None
    assert not sidebar._marking
    assert not sidebar.accept_button.isEnabled()
    assert not sidebar.reject_button.isEnabled()
    assert "READY" not in sidebar.status_label.text()
    sidebar.close()
    assert app is not None


def test_case_change_resets_old_subset_and_ignores_its_worker():
    from bart_spine_ui.segmentation.totalsegmentator_service import (
        LUMBAR_ROIS,
        THORACIC_LUMBAR_ROIS,
    )

    volume = SimpleNamespace(name="CT", source_path=None)
    page = make_page(volume)
    page.case_anatomy = None
    page.segmentation_rois = THORACIC_LUMBAR_ROIS
    page._loaded_volume = volume
    page._sync_screw_table = MagicMock()
    page._on_volume_loaded = lambda value: PlanningPage._on_volume_loaded(page, value)
    PlanningPage.set_case_region(page, "L3 – L5", "Lumbar Spine")
    assert page.segmentation_rois == LUMBAR_ROIS
    assert page.levels_of_interest == ["L3", "L4", "L5"]
    assert page.current_segmentation is None
    assert not page.skipped
    assert not page.plans
    worker = SimpleNamespace(volume=volume, rois=THORACIC_LUMBAR_ROIS)
    page._load_workers = [worker]
    page.left_sidebar.reset_mock()
    PlanningPage._on_segmentation_loaded(page, worker, object(), volume, True)
    PlanningPage._on_load_progress(page, worker, 80, "Old subset")
    PlanningPage._on_segmentation_load_failed(page, worker, "Old error", volume)
    assert not page.left_sidebar.mock_calls


def test_background_loader_passes_selected_subset_to_service():
    from bart_spine_ui.segmentation.totalsegmentator_service import LUMBAR_ROIS
    from bart_spine_ui.ui.pages.planning_page import SegmentationLoadWorker

    worker = SimpleNamespace(
        service=MagicMock(), output_dir="segmentation", volume=object(),
        rois=LUMBAR_ROIS, progress_changed=MagicMock(),
        result_ready=MagicMock(), load_failed=MagicMock(),
    )
    SegmentationLoadWorker.run(worker)
    worker.service.load_from_directory.assert_called_once_with(
        worker.output_dir, worker.volume, rois=LUMBAR_ROIS,
        progress_callback=worker.progress_changed.emit,
    )
    worker.result_ready.emit.assert_called_once_with(
        worker.service.load_from_directory.return_value
    )
