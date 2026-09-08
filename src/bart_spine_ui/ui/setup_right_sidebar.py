from PySide6.QtCore import QTime
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QFrame, QLabel, QTextEdit, QVBoxLayout, QWidget

from .status_indicator import StatusIndicator, StatusState


class SetupRightSidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RightSidebar")
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(10)

        layout.addWidget(self._section("CASE"))
        # PLACEHOLDER: Replace with case data from the clinical case service.
        self.case_label = QLabel(
            "Case ID: BART-2026-0042\n"
            "CT: Lumbar CT\n"
            "  •  Region L3–L5"
        )
        self.case_label.setObjectName("SidebarText")
        self.case_label.setWordWrap(True)
        layout.addWidget(self.case_label)

        layout.addSpacing(8)
        layout.addWidget(self._section("SETUP STATUS"))
        self.case_status = StatusIndicator("Case")
        self.ct_status = StatusIndicator("Clinical CT")
        self.robot_status = StatusIndicator("Robot")
        self.tracking_status = StatusIndicator("Tracking system")
        self.patient_status = StatusIndicator("Patient marker")
        layout.addWidget(self.case_status)
        layout.addWidget(self.ct_status)
        layout.addWidget(self.robot_status)
        layout.addWidget(self.tracking_status)
        layout.addWidget(self.patient_status)

        layout.addSpacing(5)
        layout.addWidget(self._section("LOG"))
        self.log = QTextEdit()
        self.log.setObjectName("LogBox")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(220)
        layout.addWidget(self.log, 1)

        self.add_log("Waiting for setup status")

    def _section(self, title: str) -> QWidget:
        widget = QWidget()
        box = QVBoxLayout(widget)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        line = QFrame()
        line.setObjectName("SectionLine")
        box.addWidget(label)
        box.addWidget(line)
        return widget

    def set_ct_loaded(self, name: str, *, is_demo: bool = False) -> None:
        if is_demo:
            self.ct_status.set_status(StatusState.WAITING, "Waiting for clinical CT")
            self.add_log("Demo CT loaded; waiting for clinical CT")
            return

        self.ct_status.set_status(StatusState.READY, "Loaded")
        # PLACEHOLDER: Keep the case ID and region until the case service supplies them.
        self.case_label.setText(
            "Case ID: BART-2026-0042\n"
            f"CT: {name}\n"
            "  •  Region L3–L5"
        )
        self.add_log(f"CT loaded: {name}")

    def set_case(self, case_id: str, ct_name: str, region: str) -> None:
        self.case_label.setText(f"Case ID: {case_id}\nCT: {ct_name}\n  •  Region {region}")
        self.case_status.set_status(StatusState.READY, "Created")
        self.add_log(f"Case loaded: {case_id}")

    def set_robot_connected(self, connected: bool | None) -> None:
        self.robot_status.set_connected(connected)

    def set_tracking_connected(self, connected: bool | None) -> None:
        self.tracking_status.set_connected(connected)

    def set_patient_marker_tracked(self, tracked: bool | None) -> None:
        self.patient_status.set_connected(tracked, unavailable="Not tracked")

    def add_log(self, message: str) -> None:
        stamp = QTime.currentTime().toString("HH:mm")
        self.log.append(f"{stamp} {message}")
        self.log.moveCursor(QTextCursor.End)
