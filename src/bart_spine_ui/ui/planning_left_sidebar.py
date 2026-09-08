from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QPushButton, QVBoxLayout


class PlanningLeftSidebar(QFrame):
    segmentation_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LeftSidebar")
        self.setFixedWidth(320)
        self._running = False
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 7, 10)
        root.setSpacing(10)

        ct_card, ct_layout = self._card("▣   PLANNING DATA")
        self.ct_label = QLabel("CT: not loaded")
        self.ct_label.setObjectName("SidebarText")
        self.ct_label.setWordWrap(True)
        ct_layout.addWidget(self.ct_label)

        self.output_label = QLabel("Output: —")
        self.output_label.setObjectName("RangeText")
        self.output_label.setWordWrap(True)
        ct_layout.addWidget(self.output_label)
        root.addWidget(ct_card)

        segmentation_card, segmentation_layout = self._card(
            "◫   AUTO SEGMENTATION"
        )

        method = QLabel("TotalSegmentator")
        method.setObjectName("StatusGroup")
        segmentation_layout.addWidget(method)

        target = QLabel(
            "Target anatomy\n"
            "T1-T12 + L1-L5 vertebrae only\n"
            "17 segmentation masks"
        )
        target.setObjectName("SidebarText")
        target.setWordWrap(True)
        segmentation_layout.addWidget(target)

        self.segmentation_button = QPushButton("◈    SEGMENTATION")
        self.segmentation_button.setObjectName("PrimaryAction")
        self.segmentation_button.setToolTip(
            "Run full-resolution TotalSegmentator for T1 through L5"
        )
        segmentation_layout.addWidget(self.segmentation_button)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusWaiting")
        self.status_label.setWordWrap(True)
        segmentation_layout.addWidget(self.status_label)

        self.loading_progress = QProgressBar()
        self.loading_progress.setObjectName("SegmentationLoadProgress")
        self.loading_progress.setRange(0, 100)
        self.loading_progress.setValue(0)
        self.loading_progress.setFormat("Loading masks — %p%")
        self.loading_progress.setAccessibleName("Segmentation loading progress")
        self.loading_progress.hide()
        segmentation_layout.addWidget(self.loading_progress)

        root.addWidget(segmentation_card)
        root.addStretch(1)

        self.segmentation_button.clicked.connect(self.segmentation_requested)

    @staticmethod
    def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("SidebarCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(7)

        header = QLabel(title)
        header.setObjectName("CardTitle")
        layout.addWidget(header)

        divider = QFrame()
        divider.setObjectName("CardDivider")
        layout.addWidget(divider)

        return card, layout

    def set_ct(self, name: str | None) -> None:
        self.ct_label.setText(f"CT: {name}" if name else "CT: not loaded")

    def set_output_directory(self, path: str | None) -> None:
        self.output_label.setText(f"Output: {path}" if path else "Output: —")

    def set_running(self, running: bool) -> None:
        self._running = running
        self._sync_action_state()

    def set_loading(self, loading: bool) -> None:
        was_loading = self._loading
        self._loading = loading
        self.loading_progress.setVisible(loading)
        if loading and not was_loading:
            self.loading_progress.setValue(0)
        self._sync_action_state()

    def set_loading_progress(self, value: int, text: str) -> None:
        self.loading_progress.setValue(max(0, min(100, value)))
        self.loading_progress.setFormat(f"{text} — %p%")

    def _sync_action_state(self) -> None:
        busy = self._running or self._loading
        self.segmentation_button.setEnabled(not busy)
        self.segmentation_button.setText(
            "◌    SEGMENTING..."
            if self._running
            else "◌    LOADING..."
            if self._loading
            else "◈    SEGMENTATION"
        )

    def set_status(self, text: str, state: str = "waiting") -> None:
        object_names = {
            "waiting": "StatusWaiting",
            "ok": "StatusOk",
            "error": "StatusError",
            "warning": "StatusWarn",
        }
        self.status_label.setText(text)
        self.status_label.setObjectName(
            object_names.get(state, "StatusWaiting")
        )
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
