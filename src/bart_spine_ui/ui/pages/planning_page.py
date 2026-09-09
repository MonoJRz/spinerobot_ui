from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess, QThread, Signal
from PySide6.QtWidgets import QHBoxLayout, QMessageBox

from ...controllers import ImagingController
from ...imaging.models import MedicalVolume
from ...planning import PediclePlanningService, ScrewPlan, Side, parse_levels_of_interest
from ...planning.workspace import PlanningWorkspace
from ...segmentation import (
    THORACIC_LUMBAR_ROIS,
    SegmentationRun,
    SegmentationVolume,
    TotalSegmentatorService,
)
from ...workflows import WorkflowPage
from ..planning_left_sidebar import PlanningLeftSidebar
from ..screw_table_panel import ScrewTablePanel


class SegmentationLoadWorker(QThread):
    """Load and combine masks without blocking Qt GUI updates."""

    progress_changed = Signal(int, str)
    result_ready = Signal(object)
    load_failed = Signal(str)

    def __init__(self, service, output_dir, volume, parent=None):
        super().__init__(parent)
        self.service = service
        self.output_dir = output_dir
        self.volume = volume

    def run(self) -> None:
        try:
            segmentation = self.service.load_from_directory(
                self.output_dir,
                self.volume,
                progress_callback=self.progress_changed.emit,
            )
        except Exception as exc:  # noqa: BLE001 -- forward service errors to the UI
            self.load_failed.emit(str(exc))
            return
        self.result_ready.emit(segmentation)


class PlanningPage(WorkflowPage):
    """Level-by-level pedicle screw planning on synchronized T1-L5 segmentation."""

    def __init__(
        self,
        controller: ImagingController,
        *,
        segmentation_service: TotalSegmentatorService | None = None,
        planning_service: PediclePlanningService | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.controller = controller
        self.segmentation_service = segmentation_service or TotalSegmentatorService()
        self.planning_service = planning_service or PediclePlanningService()
        self.current_run: SegmentationRun | None = None
        self.current_segmentation: SegmentationVolume | None = None
        self._displayed_volume: MedicalVolume | None = None
        self._run_volume: MedicalVolume | None = None
        self._running = False
        self._active = False
        self._load_workers: set[SegmentationLoadWorker] = set()

        self.case_region: str | None = None
        self.levels_of_interest: list[str] = []
        self._queue: list[tuple[str, Side]] = []
        self._target_index = 0
        self.plans: dict[tuple[str, Side], ScrewPlan] = {}
        self.accepted: set[tuple[str, Side]] = set()
        self._auto_dimensions: dict[tuple[str, Side], tuple[float, float]] = {}

        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.left_sidebar = PlanningLeftSidebar()
        self.workspace = PlanningWorkspace()
        self.screw_table = ScrewTablePanel()
        self.left_sidebar.set_three_d_view(self.workspace.three_d)

        main.addWidget(self.left_sidebar)
        main.addWidget(self.workspace, 1)
        main.addWidget(self.screw_table)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        self.left_sidebar.segmentation_requested.connect(self._start_segmentation)
        self.left_sidebar.accept_next_requested.connect(self._accept_and_next)
        self.left_sidebar.reject_requested.connect(self._reject_current)
        self.left_sidebar.target_requested.connect(self._select_and_mark_target)
        self.workspace.entry_point_picked.connect(self._entry_point_picked)
        self.workspace.screw_overlay.diameter_changed.connect(self._diameter_changed)
        self.workspace.screw_overlay.length_changed.connect(self._length_changed)
        self.workspace.angles_changed.connect(self._trajectory_angles_changed)
        self.workspace.screw_overlay.reset_requested.connect(self._restore_auto_dimensions)
        self.screw_table.target_requested.connect(self._select_target)
        self.screw_table.add_requested.connect(self._begin_entry_marking)
        self.screw_table.delete_requested.connect(self._delete_screw)

        self.controller.volume_loaded.connect(self._on_volume_loaded)
        self.process.readyReadStandardOutput.connect(self._on_process_output)
        self.process.finished.connect(self._on_process_finished)
        self.process.errorOccurred.connect(self._on_process_error)

        if self.controller.current_volume is not None:
            self._on_volume_loaded(self.controller.current_volume)

    @property
    def workflow_key(self) -> str:
        return "planning"

    @property
    def workflow_title(self) -> str:
        return "Planning"

    def on_activated(self) -> None:
        self._active = True
        volume = self.controller.current_volume
        if volume is not None:
            self._on_volume_loaded(volume)
        if self.current_segmentation is not None and self._queue:
            self._activate_target()

    def on_deactivated(self) -> None:
        self._active = False
        self.workspace.begin_entry_point_marking(False)
        self.left_sidebar.set_marking(False)

    def set_case_region(self, region: str | None) -> None:
        self.case_region = region.strip() if region and region.strip() else None
        parsed = parse_levels_of_interest(self.case_region)
        self.levels_of_interest = parsed
        self.left_sidebar.set_case_region(self.case_region, parsed)
        if parsed:
            allowed = set(parsed)
            self.plans = {key: plan for key, plan in self.plans.items() if key[0] in allowed}
            self.accepted = {key for key in self.accepted if key[0] in allowed}
            self._auto_dimensions = {
                key: value for key, value in self._auto_dimensions.items() if key[0] in allowed
            }
        self._sync_screw_table()
        if self.current_segmentation is not None:
            self._target_index = 0
            self._prepare_planning_queue()

    def _on_volume_loaded(self, volume: MedicalVolume) -> None:
        if not self._active:
            self.left_sidebar.set_ct(volume.name)
            output_dir = (
                self.segmentation_service.output_directory(volume.source_path)
                if volume.source_path is not None
                else None
            )
            self.left_sidebar.set_output_directory(
                str(output_dir) if output_dir is not None else None
            )
            return

        output_dir = (
            self.segmentation_service.output_directory(volume.source_path)
            if volume.source_path is not None
            else None
        )
        has_existing_segmentation = (
            volume is not self._displayed_volume
            and output_dir is not None
            and all((output_dir / f"{roi}.nii.gz").is_file() for roi in THORACIC_LUMBAR_ROIS)
        )
        if has_existing_segmentation:
            self.left_sidebar.set_loading(True)
            self.left_sidebar.set_loading_progress(5, "Preparing CT views")
            self.left_sidebar.set_status("Loading CT and existing segmentation...", "waiting")
            self.left_sidebar.loading_progress.repaint()

        volume_changed = volume is not self._displayed_volume
        if volume_changed:
            if not has_existing_segmentation:
                self.left_sidebar.set_loading(False)
            self._displayed_volume = volume
            self.current_segmentation = None
            self.plans.clear()
            self.accepted.clear()
            self._auto_dimensions.clear()
            self._queue.clear()
            self._target_index = 0
            self.workspace.clear_segmentation()
            self.workspace.set_volume(volume)
            self.left_sidebar.set_completed(set())
            self.left_sidebar.clear_plan_measurements()
            self.screw_table.clear()

        self.left_sidebar.set_ct(volume.name)
        self.left_sidebar.set_case_region(self.case_region, self.levels_of_interest)

        if volume.source_path is None:
            self.left_sidebar.set_output_directory(None)
            return

        self.left_sidebar.set_output_directory(str(output_dir))
        if has_existing_segmentation:
            self._load_segmentation(output_dir, volume, existing=True)

    def _start_segmentation(self) -> None:
        if self._running:
            return

        volume = self.controller.current_volume
        if volume is None or volume.is_demo:
            QMessageBox.warning(
                self,
                "Segmentation",
                "Load a clinical CT in the Setup page first.",
            )
            return

        try:
            run = self.segmentation_service.prepare_run(volume)
        except Exception as exc:  # noqa: BLE001
            self._show_error(str(exc))
            return

        self.current_run = run
        self._run_volume = volume
        self.current_segmentation = None
        self.plans.clear()
        self.accepted.clear()
        self._auto_dimensions.clear()
        self.workspace.clear_segmentation()
        self.screw_table.clear()
        self.left_sidebar.set_segmentation_ready(False)
        self._running = True
        self.left_sidebar.set_running(True)
        self.left_sidebar.set_status("Starting full-resolution T1-L5 segmentation...", "waiting")
        self.left_sidebar.set_output_directory(str(run.output_dir))
        self.status_changed.emit("TotalSegmentator — T1-L5 segmentation started")

        self.process.setProgram(run.executable)
        self.process.setArguments(run.arguments)
        self.process.start()

    def _on_process_output(self) -> None:
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            self.left_sidebar.set_status(lines[-1], "waiting")

    def _on_process_finished(self, exit_code: int, _exit_status) -> None:
        run = self.current_run
        volume = self._run_volume
        if run is None or volume is None:
            self._finish_ui()
            return

        self.segmentation_service.cleanup(run)
        if exit_code != 0:
            self._finish_ui()
            self._show_error(f"TotalSegmentator stopped with exit code {exit_code}.")
            return

        missing = self.segmentation_service.missing_masks(run)
        if missing:
            names = ", ".join(path.name for path in missing[:5])
            if len(missing) > 5:
                names += f" (+{len(missing) - 5} more)"
            self._finish_ui()
            self._show_error("Segmentation finished but some T1-L5 masks are missing: " + names)
            return

        if self.controller.current_volume is not volume:
            self._finish_ui()
            self.left_sidebar.set_status(
                "Complete, but the loaded CT changed. Results were not displayed.",
                "warning",
            )
            return
        self._load_segmentation(run.output_dir, volume)

    def _load_segmentation(
        self,
        output_dir: str | Path,
        volume: MedicalVolume,
        *,
        existing: bool = False,
    ) -> bool:
        self.left_sidebar.set_loading(True)
        loading_text = (
            "Loading existing segmentation masks..."
            if existing
            else "Loading completed segmentation masks..."
        )
        self.left_sidebar.set_status(loading_text, "waiting")
        self.status_changed.emit("Loading T1-L5 segmentation masks")

        worker = SegmentationLoadWorker(
            self.segmentation_service,
            output_dir,
            volume,
            parent=self,
        )
        self._load_workers.add(worker)
        worker.progress_changed.connect(
            lambda value, text, job=worker: self._on_load_progress(job, value, text)
        )
        worker.result_ready.connect(
            lambda result, job=worker: self._on_segmentation_loaded(
                job, result, volume, existing
            )
        )
        worker.load_failed.connect(
            lambda message, job=worker: self._on_segmentation_load_failed(job, message, volume)
        )
        worker.finished.connect(lambda job=worker: self._discard_load_worker(job))
        worker.finished.connect(worker.deleteLater)
        worker.start()
        return True

    def _on_load_progress(
        self,
        worker: SegmentationLoadWorker,
        value: int,
        text: str,
    ) -> None:
        if worker not in self._load_workers or self.controller.current_volume is not worker.volume:
            return
        self.left_sidebar.set_loading_progress(10 + round(value * 0.8), text)
        self.left_sidebar.set_status(text, "waiting")

    def _on_segmentation_loaded(
        self,
        worker: SegmentationLoadWorker,
        segmentation: SegmentationVolume,
        volume: MedicalVolume,
        existing: bool,
    ) -> None:
        if worker not in self._load_workers or self.controller.current_volume is not volume:
            return

        self.left_sidebar.set_loading_progress(95, "Preparing MPR and 3D views")
        self.left_sidebar.loading_progress.repaint()
        self.current_segmentation = segmentation
        stored_plans, stored_accepted = self.planning_service.load_plans(volume)
        if stored_plans:
            self.plans = stored_plans
            self.accepted = stored_accepted
            self._auto_dimensions = {
                key: (plan.diameter_mm, plan.length_mm)
                for key, plan in stored_plans.items()
            }
        self.workspace.set_segmentation(segmentation)
        self.left_sidebar.set_loading_progress(100, "Segmentation ready")
        self.left_sidebar.set_loading(False)
        self._finish_ui()
        self._prepare_planning_queue()

        message = (
            "Existing segmentation loaded — planning ready."
            if existing
            else "Complete — segmentation loaded and planning ready."
        )
        self.left_sidebar.set_status(message, "ok")
        self.left_sidebar.set_segmentation_ready(True)
        self.status_changed.emit(f"Segmentation loaded — {segmentation.source_directory}")

    def _prepare_planning_queue(self) -> None:
        segmentation = self.current_segmentation
        if segmentation is None:
            return
        available = self.planning_service.available_levels(segmentation)
        requested = parse_levels_of_interest(self.case_region)
        levels = [level for level in requested if level in available]
        if not levels:
            # Keep the workflow usable if the case region has not been populated yet.
            levels = available
            if self.case_region:
                self.left_sidebar.set_status(
                    f"No segmented levels matched '{self.case_region}'. Showing available levels.",
                    "warning",
                )

        self.levels_of_interest = levels
        self.left_sidebar.set_case_region(self.case_region, levels)
        self._queue = [(level, side) for level in levels for side in ("left", "right")]
        if not self._queue:
            self.left_sidebar.set_status("No vertebral levels available for planning.", "warning")
            return
        self._target_index = min(self._target_index, len(self._queue) - 1)
        self._activate_target()

    def _activate_target(self) -> None:
        if not self._queue or self.current_segmentation is None:
            return
        key = self._queue[self._target_index]
        level, side = key
        plan = self.plans.get(key)
        self.left_sidebar.set_completed(self.accepted)
        self.left_sidebar.set_target(
            self._target_index,
            len(self._queue),
            level,
            side,
            has_plan=plan is not None,
        )
        self.workspace.set_plans(self.plans, active_key=key if plan is not None else None)
        self.workspace.focus_three_d_level(level, side)
        self._sync_screw_table()

        if plan is not None:
            self.workspace.focus_on_physical_point(plan.entry_point, parallel_scale_mm=38.0)
            self._show_plan(plan, remember_auto=False)
            return

        self.left_sidebar.clear_plan_measurements()
        self.workspace.screw_overlay.clear_plan()
        try:
            focus = self.planning_service.suggested_focus_point(
                self.current_segmentation,
                level,
                side,
            )
        except Exception as exc:  # noqa: BLE001
            self.left_sidebar.set_status(f"Could not focus {level}: {exc}", "warning")
            return
        self.workspace.focus_on_physical_point(focus, parallel_scale_mm=42.0)

    def _begin_entry_marking(self) -> None:
        if self.current_segmentation is None or not self._queue:
            QMessageBox.information(
                self,
                "Planning",
                "Load or run segmentation before marking an entry point.",
            )
            return
        self.left_sidebar.set_marking(True)
        self.workspace.begin_entry_point_marking(True)
        level, side = self._queue[self._target_index]
        self.status_changed.emit(f"Mark entry point — {level} {side}")

    def _entry_point_picked(self, point_lps) -> None:
        self.left_sidebar.set_marking(False)
        if self.current_segmentation is None or not self._queue:
            return
        key = self._queue[self._target_index]
        level, side = key
        try:
            plan = self.planning_service.estimate(
                self.current_segmentation,
                level,
                side,
                tuple(float(v) for v in point_lps),
            )
        except Exception as exc:  # noqa: BLE001
            self._show_planning_error(f"Could not estimate {level} {side} screw: {exc}")
            return

        self.plans[key] = plan
        self.accepted.discard(key)
        self._auto_dimensions[key] = (plan.diameter_mm, plan.length_mm)
        self.workspace.set_plans(self.plans, active_key=key)
        self._sync_screw_table()
        self.workspace.focus_on_physical_point(plan.entry_point, parallel_scale_mm=38.0)
        self.left_sidebar.set_target(
            self._target_index,
            len(self._queue),
            level,
            side,
            has_plan=True,
        )
        self.left_sidebar.set_completed(self.accepted)
        self._show_plan(plan, remember_auto=True)
        self._save_plans()
        self.status_changed.emit(
            f"Estimated {level} {side}: Ø{plan.diameter_mm:.1f} × {plan.length_mm:.0f} mm"
        )

    def _show_plan(self, plan: ScrewPlan, *, remember_auto: bool) -> None:
        self.left_sidebar.set_plan_measurements(
            anatomical_length_mm=plan.anatomical_length_mm,
            pedicle_width_mm=plan.pedicle_width_mm,
            diameter_mm=plan.diameter_mm,
            length_mm=plan.length_mm,
            warning=plan.warning,
        )
        self.workspace.screw_overlay.set_plan(
            level=plan.level,
            side=plan.side,
            diameter_mm=plan.diameter_mm,
            length_mm=plan.length_mm,
            anatomical_length_mm=plan.anatomical_length_mm,
            pedicle_width_mm=plan.pedicle_width_mm,
            remember_auto=remember_auto,
        )

    def _diameter_changed(self, diameter_mm: float) -> None:
        self._update_current_dimensions(diameter_mm=diameter_mm)

    def _length_changed(self, length_mm: float) -> None:
        self._update_current_dimensions(length_mm=length_mm)

    def _trajectory_angles_changed(
        self,
        axial_angle_deg: float,
        sagittal_angle_deg: float,
    ) -> None:
        if not self._queue:
            return
        key = self._queue[self._target_index]
        plan = self.plans.get(key)
        if plan is None:
            return
        updated = plan.with_angles(
            axial_angle_deg=axial_angle_deg,
            sagittal_angle_deg=sagittal_angle_deg,
        )
        self.plans[key] = updated
        self.accepted.discard(key)
        self.left_sidebar.set_completed(self.accepted)
        self.workspace.set_plans(self.plans, active_key=key)
        self._sync_screw_table()
        self._save_plans()

    def _update_current_dimensions(
        self,
        *,
        diameter_mm: float | None = None,
        length_mm: float | None = None,
    ) -> None:
        if not self._queue:
            return
        key = self._queue[self._target_index]
        plan = self.plans.get(key)
        if plan is None:
            return
        updated = plan.with_dimensions(diameter_mm=diameter_mm, length_mm=length_mm)
        self.plans[key] = updated
        self.accepted.discard(key)
        self.left_sidebar.set_completed(self.accepted)
        self.workspace.set_plans(self.plans, active_key=key)
        self._sync_screw_table()
        self.left_sidebar.set_plan_measurements(
            anatomical_length_mm=updated.anatomical_length_mm,
            pedicle_width_mm=updated.pedicle_width_mm,
            diameter_mm=updated.diameter_mm,
            length_mm=updated.length_mm,
            warning=updated.warning,
        )
        self._save_plans()

    def _restore_auto_dimensions(self) -> None:
        if not self._queue:
            return
        key = self._queue[self._target_index]
        values = self._auto_dimensions.get(key)
        plan = self.plans.get(key)
        if values is None or plan is None:
            return
        diameter, length = values
        updated = plan.with_dimensions(diameter_mm=diameter, length_mm=length)
        self.plans[key] = updated
        self.accepted.discard(key)
        self.left_sidebar.set_completed(self.accepted)
        self.workspace.set_plans(self.plans, active_key=key)
        self._show_plan(updated, remember_auto=False)
        self._sync_screw_table()
        self._save_plans()

    def _accept_and_next(self) -> None:
        if not self._queue:
            return
        key = self._queue[self._target_index]
        if key not in self.plans:
            return
        self.accepted.add(key)
        self.left_sidebar.set_completed(self.accepted)
        self._sync_screw_table()
        saved = self._save_plans()
        level, side = key
        if self._target_index < len(self._queue) - 1:
            self._target_index += 1
            next_level, next_side = self._queue[self._target_index]
            self._activate_target()
            self._begin_entry_marking()
            self.status_changed.emit(
                f"Accepted {level} {side} screw — mark {next_level} {next_side} entry"
            )
            return
        self.status_changed.emit(
            f"Planning complete — saved to {saved}"
            if saved
            else "Planning complete"
        )

    def _previous_target(self) -> None:
        if self._target_index <= 0:
            return
        self._target_index -= 1
        self._activate_target()

    def _select_target(self, level: str, side: str) -> None:
        key = (level, side)
        if key not in self._queue:
            return
        self._target_index = self._queue.index(key)
        self._activate_target()

    def _select_and_mark_target(self, level: str, side: str) -> None:
        self._select_target(level, side)
        if (level, side) in self._queue:
            self._begin_entry_marking()

    def _reject_current(self) -> None:
        self.workspace.begin_entry_point_marking(False)
        self.left_sidebar.set_marking(False)
        if not self._queue:
            return
        key = self._queue[self._target_index]
        self.plans.pop(key, None)
        self.accepted.discard(key)
        self._auto_dimensions.pop(key, None)
        self.workspace.set_plans(self.plans, active_key=None)
        self.workspace.screw_overlay.clear_plan()
        self.left_sidebar.clear_plan_measurements()
        self.left_sidebar.set_completed(self.accepted)
        self._sync_screw_table()
        self._save_plans()
        self.status_changed.emit(f"Rejected {key[0]} {key[1]} screw")

    def _delete_screw(self, level: str, side: str) -> None:
        key = (level, side)
        if key not in self.plans:
            return
        answer = QMessageBox.question(
            self,
            "Delete screw",
            f"Delete the {level} {side} screw from this plan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self.plans[key]
        self.accepted.discard(key)
        self._auto_dimensions.pop(key, None)
        active_key = self._queue[self._target_index] if self._queue else None
        self.workspace.set_plans(
            self.plans,
            active_key=active_key if active_key in self.plans else None,
        )
        if key == active_key:
            self.left_sidebar.clear_plan_measurements()
            self.workspace.screw_overlay.clear_plan()
            self.left_sidebar.set_target(
                self._target_index,
                len(self._queue),
                key[0],
                key[1],
                has_plan=False,
            )
        self.left_sidebar.set_completed(self.accepted)
        self._sync_screw_table()
        self._save_plans()
        self.status_changed.emit(f"Deleted {level} {side} screw")

    def _sync_screw_table(self) -> None:
        active_key = self._queue[self._target_index] if self._queue else None
        self.screw_table.set_plans(self.plans, self.accepted, active_key)

    def _save_plans(self) -> Path | None:
        volume = self.controller.current_volume
        if volume is None:
            return None
        try:
            return self.planning_service.save_plans(
                volume,
                self.plans,
                case_region=self.case_region,
                accepted=self.accepted,
            )
        except OSError as exc:
            self.left_sidebar.set_status(f"Could not save planning JSON: {exc}", "warning")
            return None

    def _on_segmentation_load_failed(
        self,
        worker: SegmentationLoadWorker,
        message: str,
        volume: MedicalVolume,
    ) -> None:
        if worker not in self._load_workers or self.controller.current_volume is not volume:
            return
        self.left_sidebar.set_loading(False)
        self._finish_ui()
        self._show_error(f"Could not load segmentation masks: {message}")

    def _discard_load_worker(self, worker: SegmentationLoadWorker) -> None:
        self._load_workers.discard(worker)

    def _on_process_error(self, _error) -> None:
        if not self._running:
            return
        run = self.current_run
        if run is not None:
            self.segmentation_service.cleanup(run)
        message = self.process.errorString() or "Could not start TotalSegmentator."
        self._finish_ui()
        self._show_error(message)

    def _finish_ui(self) -> None:
        self._running = False
        self.left_sidebar.set_running(False)

    def _show_error(self, message: str) -> None:
        self.left_sidebar.set_status(f"Error: {message}", "error")
        self.status_changed.emit(f"Segmentation error — {message}")
        QMessageBox.critical(self, "Segmentation error", message)

    def _show_planning_error(self, message: str) -> None:
        self.left_sidebar.set_status(message, "error")
        self.status_changed.emit(message)
        QMessageBox.warning(self, "Planning", message)
