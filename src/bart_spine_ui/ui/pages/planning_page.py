from pathlib import Path

from PySide6.QtCore import QProcess, QThread, Signal
from PySide6.QtWidgets import QHBoxLayout, QMessageBox

from ...controllers import ImagingController
from ...imaging.models import MedicalVolume
from ...segmentation import (
    THORACIC_LUMBAR_ROIS,
    SegmentationRun,
    SegmentationVolume,
    TotalSegmentatorService,
)
from ...visualization import ImagingWorkspace
from ...workflows import WorkflowPage
from ..planning_left_sidebar import PlanningLeftSidebar


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
    """Planning stage with synchronized T1-L5 segmentation visualization."""

    def __init__(
        self,
        controller: ImagingController,
        *,
        segmentation_service: TotalSegmentatorService | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.controller = controller
        self.segmentation_service = segmentation_service or TotalSegmentatorService()
        self.current_run: SegmentationRun | None = None
        self.current_segmentation: SegmentationVolume | None = None
        self._displayed_volume: MedicalVolume | None = None
        self._run_volume: MedicalVolume | None = None
        self._running = False
        self._active = False
        self._load_workers: set[SegmentationLoadWorker] = set()

        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.left_sidebar = PlanningLeftSidebar()
        self.workspace = ImagingWorkspace()

        main.addWidget(self.left_sidebar)
        main.addWidget(self.workspace, 1)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        self.left_sidebar.segmentation_requested.connect(self._start_segmentation)
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

    def on_deactivated(self) -> None:
        self._active = False

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
            and all(
                (output_dir / f"{roi}.nii.gz").is_file()
                for roi in THORACIC_LUMBAR_ROIS
            )
        )
        if has_existing_segmentation:
            self.left_sidebar.set_loading(True)
            self.left_sidebar.set_loading_progress(5, "Preparing CT views")
            self.left_sidebar.set_status(
                "Loading CT and existing segmentation...", "waiting"
            )
            self.left_sidebar.loading_progress.repaint()

        volume_changed = volume is not self._displayed_volume
        if volume_changed:
            if not has_existing_segmentation:
                self.left_sidebar.set_loading(False)
            self._displayed_volume = volume
            self.current_segmentation = None
            self.workspace.clear_segmentation()
            self.workspace.set_volume(volume)

        self.left_sidebar.set_ct(volume.name)

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
        except Exception as exc:
            self._show_error(str(exc))
            return

        self.current_run = run
        self._run_volume = volume
        self.current_segmentation = None
        self.workspace.clear_segmentation()
        self._running = True
        self.left_sidebar.set_running(True)
        self.left_sidebar.set_status(
            "Starting full-resolution T1-L5 segmentation...",
            "waiting",
        )
        self.left_sidebar.set_output_directory(str(run.output_dir))
        self.status_changed.emit("TotalSegmentator — T1-L5 segmentation started")

        self.process.setProgram(run.executable)
        self.process.setArguments(run.arguments)
        self.process.start()

    def _on_process_output(self) -> None:
        text = bytes(self.process.readAllStandardOutput()).decode(
            "utf-8",
            errors="replace",
        )
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
            lambda message, job=worker: self._on_segmentation_load_failed(
                job, message, volume
            )
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
        if (
            worker not in self._load_workers
            or self.controller.current_volume is not worker.volume
        ):
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
        if (
            worker not in self._load_workers
            or self.controller.current_volume is not volume
        ):
            return

        self.left_sidebar.set_loading_progress(95, "Preparing MPR and 3D views")
        self.left_sidebar.loading_progress.repaint()
        self.current_segmentation = segmentation
        self.workspace.set_segmentation(segmentation)
        self.left_sidebar.set_loading_progress(100, "Segmentation ready")
        self.left_sidebar.set_loading(False)
        self._finish_ui()

        message = (
            "Existing segmentation loaded in MPR and 3D."
            if existing
            else "Complete — segmentation shown in MPR and 3D."
        )
        self.left_sidebar.set_status(message, "ok")
        self.status_changed.emit(
            f"Segmentation loaded — {segmentation.source_directory}"
        )

    def _on_segmentation_load_failed(
        self,
        worker: SegmentationLoadWorker,
        message: str,
        volume: MedicalVolume,
    ) -> None:
        if (
            worker not in self._load_workers
            or self.controller.current_volume is not volume
        ):
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
