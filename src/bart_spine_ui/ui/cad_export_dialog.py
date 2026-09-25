"""Settings-only entry point for cancellable, isolated CAD export."""

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..exporting.snapshot import write_snapshot


class CadExportDialog(QDialog):
    def __init__(self, planning_page, parent=None):
        super().__init__(parent)
        self.planning_page = planning_page
        self.setWindowTitle("Export CAD model")
        self.setObjectName("CadExportDialog")
        self.setMinimumWidth(520)
        self._temporary = None
        self._target = None
        self._cancelled = False
        self._busy = False
        self._log = ""
        self._pending_line = ""
        layout = QVBoxLayout(self)
        description = QLabel(
            "Save separate vertebrae, screws, and heads as a STEP assembly and STL files. "
            "The spine uses the same smoothing as the 3D view. All current screws, "
            "including drafts, are included."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("Save CAD model…")
        self.save_button.setObjectName("PrimaryAction")
        self.save_button.clicked.connect(self._choose_destination)
        buttons.addWidget(self.save_button)
        self.open_button = QPushButton("Open export folder")
        self.open_button.setObjectName("SecondaryAction")
        self.open_button.clicked.connect(self._open_folder)
        self.open_button.hide()
        buttons.addWidget(self.open_button)
        self.cancel_button = QPushButton("Cancel export")
        self.cancel_button.setObjectName("SecondaryAction")
        self.cancel_button.clicked.connect(self._cancel_export)
        self.cancel_button.hide()
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)
        self.refresh_state()

    def refresh_state(self):
        if self._busy:
            return
        page = self.planning_page
        ready = page.current_segmentation is not None and not page._running
        self.save_button.setEnabled(ready)
        if ready:
            self.status.setText(
                f"Ready: {len(page.current_segmentation.labels)} vertebra labels, "
                f"{len(page.plans)} screws. Choose a folder for a new export."
            )
        else:
            self.status.setText("Load a CT and finish loading its segmentation in Planning first.")

    def _choose_destination(self):
        self.refresh_state()
        if not self.save_button.isEnabled():
            return
        initial = str(self.planning_page.current_segmentation.source_directory.parent)
        parent = QFileDialog.getExistingDirectory(self, "Save CAD model in", initial)
        if parent:
            name = "spine_cad_" + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
            self._begin_export(Path(parent) / name)

    def _begin_export(self, target):
        if self._busy:
            return
        page = self.planning_page
        if page.current_segmentation is None or page._running:
            self.refresh_state()
            return
        self._target = Path(target)
        self._cancelled = False
        self._log = ""
        self._pending_line = ""
        self.open_button.hide()
        try:
            if self._target.exists():
                raise FileExistsError("That folder already exists. Choose a new export folder.")
            self._temporary = tempfile.TemporaryDirectory(
                prefix=".spine-cad-", dir=self._target.parent
            )
            snapshot = Path(self._temporary.name)
            write_snapshot(
                snapshot, page.current_segmentation, page.plans, page.accepted, page.case_region
            )
        except Exception as exc:  # noqa: BLE001 -- surface export errors without closing the UI
            self._cleanup()
            self.status.setText(f"Could not prepare export: {exc}")
            return
        self._busy = True
        self.save_button.setEnabled(False)
        self.cancel_button.show()
        self.cancel_button.setEnabled(True)
        self.progress.show()
        self.status.setText("Processing the current model in the background…")
        environment = QProcessEnvironment.systemEnvironment()
        # Ensure the child runs this checkout even with a separate optional CAD runtime.
        source_root = str(Path(__file__).resolve().parents[2])
        existing = environment.value("PYTHONPATH", "")
        environment.insert("PYTHONPATH", source_root + (os.pathsep + existing if existing else ""))
        self.process.setProcessEnvironment(environment)
        self.process.start(
            os.environ.get("BART_CAD_PYTHON", sys.executable),
            ["-u", "-m", "bart_spine_ui.exporting.cli", str(snapshot), str(snapshot / "result")],
        )

    def _read_output(self):
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._log = (self._log + data)[-20000:]
        self._pending_line += data
        lines = self._pending_line.split("\n")
        self._pending_line = lines.pop()
        for line in lines:
            if line.startswith("PROGRESS ") and not self._cancelled:
                self.status.setText(line.removeprefix("PROGRESS "))

    def _finished(self, exit_code, exit_status):
        if not self._busy:
            return
        self._read_output()
        success = False
        if self._cancelled:
            message = "Export cancelled. No model was saved."
        elif exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            try:
                result = Path(self._temporary.name) / "result"
                if self._target.exists():
                    raise FileExistsError(
                        "The destination was created during export; it was not overwritten."
                    )
                (result / "export.log").write_text(self._log)
                result.rename(self._target)
                message = f"Saved and verified the CAD model in:\n{self._target}"
                success = True
            except Exception as exc:  # noqa: BLE001 -- surface export errors without closing the UI
                message = f"Could not save export: {exc}"
        else:
            errors = [
                line.removeprefix("ERROR ")
                for line in self._log.splitlines()
                if line.startswith("ERROR ")
            ]
            detail = errors[-1] if errors else self._log[-1500:] or self.process.errorString()
            if "No module named" in detail:
                detail += (
                    "\nInstall the application's optional CAD dependencies: pip install -e '.[cad]'"
                )
            message = f"CAD export failed: {detail}"
        self._busy = False
        self._cleanup()
        self.progress.hide()
        self.cancel_button.hide()
        self.refresh_state()
        self.status.setText(message)
        self.open_button.setVisible(success)

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._finished(-1, QProcess.ExitStatus.CrashExit)

    def _cancel_export(self):
        if self._busy:
            self._cancelled = True
            self.status.setText("Cancelling export…")
            self.cancel_button.setEnabled(False)
            self.process.kill()

    def _cleanup(self):
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def stop_export(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self._cancelled = True
            self.process.kill()
            self.process.waitForFinished(3000)
        self._busy = False
        self._cleanup()

    def closeEvent(self, event):
        self.stop_export()
        super().closeEvent(event)

    def reject(self):
        self.stop_export()
        super().reject()

    def _open_folder(self):
        if self._target is not None and self._target.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._target)))
