from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .status_indicator import StatusIndicator, StatusState


class SetupRightSidebar(QFrame):
    case_changed = Signal(str, str, str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RightSidebar")
        self.setFixedWidth(320)
        self._status_times: dict[StatusIndicator, QLabel] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(7, 10, 10, 10)
        root.setSpacing(10)

        self.edit_case_button = QPushButton("✎  Edit")
        self.edit_case_button.setObjectName("CardAction")
        case_card, case = self._card("▤   CASE INFORMATION", self.edit_case_button)
        case_grid = QGridLayout()
        case_grid.setHorizontalSpacing(14)
        case_grid.setVerticalSpacing(9)
        self.case_values: dict[str, QLabel] = {}
        # PLACEHOLDER: Replace initial values with data from the clinical case service.
        case_data = (
            ("Case ID", "BART-2026-0042"),
            ("Modality", "CT (DICOM)"),
            ("Anatomy", "Lumbar Spine"),
            ("Region", "L3 – L5"),
            ("Patient", "Anonymous"),
        )
        for row, (name, value) in enumerate(case_data):
            label = QLabel(name)
            label.setObjectName("CaseKey")
            value_label = QLabel(value)
            value_label.setObjectName("CaseValue")
            value_label.setWordWrap(True)
            case_grid.addWidget(label, row, 0)
            case_grid.addWidget(value_label, row, 1)
            self.case_values[name] = value_label
        case_grid.setColumnStretch(1, 1)
        case.addLayout(case_grid)
        root.addWidget(case_card)

        status_card, status = self._card("●   SETUP STATUS")
        self.case_status = self._compact_status("Case")
        self.ct_status = self._compact_status("Clinical CT")
        self.robot_status = self._compact_status("Robot")
        self.tracking_status = self._compact_status("Tracking system")
        self.patient_status = self._compact_status("Patient marker")
        for indicator in (
            self.case_status,
            self.ct_status,
            self.robot_status,
            self.tracking_status,
            self.patient_status,
        ):
            status.addLayout(self._status_row(indicator))
        root.addWidget(status_card)

        clear_button = QPushButton("▱  Clear")
        clear_button.setObjectName("CardAction")
        log_card, log_layout = self._card("▤   LOG", clear_button)
        self.log = QTextEdit()
        self.log.setObjectName("LogBox")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(180)
        log_layout.addWidget(self.log, 1)
        root.addWidget(log_card, 1)

        self.edit_case_button.clicked.connect(self._edit_case)
        clear_button.clicked.connect(self.log.clear)
        self.add_log("Waiting for real setup status")

    @staticmethod
    def _card(title: str, action: QPushButton | None = None) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("SidebarCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 13)
        layout.setSpacing(8)

        header = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("CardTitle")
        header.addWidget(label)
        header.addStretch(1)
        if action is not None:
            header.addWidget(action)
        layout.addLayout(header)

        divider = QFrame()
        divider.setObjectName("CardDivider")
        layout.addWidget(divider)
        return card, layout

    def _status_row(self, indicator: StatusIndicator) -> QHBoxLayout:
        row = QHBoxLayout()
        time = QLabel("—")
        time.setObjectName("StatusTime")
        time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._status_times[indicator] = time
        row.addWidget(indicator, 1)
        row.addWidget(time)
        return row

    @staticmethod
    def _compact_status(name: str) -> StatusIndicator:
        indicator = StatusIndicator(name)
        indicator.set_status(StatusState.WAITING)
        return indicator

    def _stamp(self, indicator: StatusIndicator, has_status: bool = True) -> None:
        self._status_times[indicator].setText(
            QTime.currentTime().toString("HH:mm") if has_status else "—"
        )

    def _edit_case(self) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("CaseEditor")
        dialog.setWindowTitle("Edit case information")
        dialog.setMinimumWidth(420)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        fields: dict[str, QLineEdit] = {}
        for name in ("Case ID", "Modality", "Anatomy", "Region", "Patient"):
            field = QLineEdit(self.case_values[name].text())
            field.setObjectName("CaseField")
            form.addRow(name, field)
            fields[name] = field
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = tuple(fields[name].text().strip() for name in fields)
        if not values[0]:
            fields["Case ID"].setFocus()
            return
        self.case_changed.emit(*values)

    def set_ct_loaded(self, name: str, *, is_demo: bool = False) -> None:
        if is_demo:
            self.ct_status.set_status(StatusState.WAITING)
            self._stamp(self.ct_status, False)
            self.add_log("Demo CT loaded; waiting for clinical CT")
            return

        self.ct_status.set_status(StatusState.READY, "Loaded")
        self._stamp(self.ct_status)
        # PLACEHOLDER: Keep other case fields until the case service supplies them.
        self.case_values["Modality"].setText(name)
        self.add_log(f"CT loaded: {name}")

    def set_case(
        self,
        case_id: str,
        modality: str,
        anatomy: str,
        region: str,
        patient: str,
    ) -> None:
        values = {
            "Case ID": case_id,
            "Modality": modality,
            "Anatomy": anatomy,
            "Region": region,
            "Patient": patient,
        }
        for name, value in values.items():
            self.case_values[name].setText(value)
        self.case_status.set_status(StatusState.READY, "Created")
        self._stamp(self.case_status)
        self.add_log(f"Case updated: {case_id}")

    def set_robot_connected(self, connected: bool | None) -> None:
        self.robot_status.set_connected(connected)
        self._stamp(self.robot_status, connected is not None)

    def set_tracking_connected(self, connected: bool | None) -> None:
        self.tracking_status.set_connected(connected)
        self._stamp(self.tracking_status, connected is not None)

    def set_patient_marker_tracked(self, tracked: bool | None) -> None:
        self.patient_status.set_connected(tracked, unavailable="Not tracked")
        self._stamp(self.patient_status, tracked is not None)

    def add_log(self, message: str) -> None:
        stamp = QTime.currentTime().toString("HH:mm")
        self.log.append(f"●  {stamp}   {message}")
        self.log.moveCursor(QTextCursor.End)
