from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QDateTime, QTimer, Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from ..workflows import WorkflowPage


class ProcedureShell(QWidget):
    """Procedure shell with workflow navigation and persistent system context."""

    stage_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AppRoot")
        self._pages: OrderedDict[str, WorkflowPage] = OrderedDict()
        self._buttons: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = QFrame()
        self.top_bar.setObjectName("TopBar")
        self.top_bar.setFixedHeight(86)
        top = QHBoxLayout(self.top_bar)
        top.setContentsMargins(20, 8, 20, 8)
        top.setSpacing(12)

        # Official BART LAB logo
        brand = QVBoxLayout()
        brand.setContentsMargins(0, 0, 0, 0)
        brand.setSpacing(0)

        self.brand_logo = QLabel()
        self.brand_logo.setObjectName("BrandLogo")
        self.brand_logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        logo_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "Bartlab_long_logo.png"
        )

        logo_pixmap = QPixmap(str(logo_path))

        if logo_pixmap.isNull():
            # Fallback if asset cannot be loaded
            self.brand_logo.setText("BART LAB")
        else:
            self.brand_logo.setPixmap(
                logo_pixmap.scaledToHeight(
                    68,
                    Qt.SmoothTransformation,
                )
            )

        self.brand_logo.setFixedHeight(72)

        top.addWidget(self.brand_logo)
        top.addSpacing(20)

        self.stage_row = QHBoxLayout()
        self.stage_row.setSpacing(0)
        top.addLayout(self.stage_row, 1)

        # PLACEHOLDER: Connect settings and help buttons when those dialogs exist.
        for symbol, tooltip in (("⚙", "Settings"), ("?", "Help")):
            button = QPushButton(symbol)
            button.setObjectName("UtilityButton")
            button.setToolTip(tooltip)
            top.addWidget(button)

        time_divider = QFrame()
        time_divider.setObjectName("HeaderDivider")
        top.addWidget(time_divider)

        clock = QVBoxLayout()
        clock.setSpacing(1)
        self.date_label = QLabel()
        self.date_label.setObjectName("HeaderMeta")
        self.time_label = QLabel()
        self.time_label.setObjectName("HeaderTime")
        clock.addWidget(self.date_label)
        clock.addWidget(self.time_label)
        top.addLayout(clock)

        room_divider = QFrame()
        room_divider.setObjectName("HeaderDivider")
        top.addWidget(room_divider)

        # PLACEHOLDER: Replace with the operating-room context service.
        room = QLabel("OR-1")
        room.setObjectName("RoomLabel")
        top.addWidget(room)

        root.addWidget(self.top_bar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        footer = QFrame()
        footer.setObjectName("FooterBar")
        footer.setFixedHeight(42)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 0, 18, 0)
        footer_layout.setSpacing(14)

        self.system_status = QLabel("●  Waiting for system status")
        self.system_status.setObjectName("FooterWaiting")
        footer_layout.addWidget(self.system_status)
        footer_layout.addStretch(1)

        # PLACEHOLDER: Replace version text with package/release metadata.
        product = QLabel("Spinal Surgical Robot   |    Version 0.1.0")
        product.setObjectName("FooterMeta")
        footer_layout.addWidget(product)
        footer_layout.addStretch(1)

        self.dataset_status = QLabel("▣  Waiting for clinical CT")
        self.dataset_status.setObjectName("FooterMeta")
        footer_layout.addWidget(self.dataset_status)
        root.addWidget(footer)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    def add_workflow(self, page: WorkflowPage) -> None:
        key = page.workflow_key
        if key in self._pages:
            raise ValueError(f"Workflow already registered: {key}")

        self._pages[key] = page
        self.stack.addWidget(page)

        step = len(self._pages)
        button = QPushButton(f"{step}    {page.workflow_title}")
        button.setObjectName("StageButton")
        button.setCheckable(True)
        button.clicked.connect(lambda _checked=False, k=key: self.activate(k))
        self._buttons[key] = button
        self.stage_row.addWidget(button)

        if len(self._pages) == 1:
            self.activate(key)

    def activate(self, key: str) -> None:
        page = self._pages[key]
        previous = self.stack.currentWidget()
        if previous is not None and previous is not page:
            previous.on_deactivated()

        self.stack.setCurrentWidget(page)
        for button_key, button in self._buttons.items():
            button.setChecked(button_key == key)

        page.on_activated()
        self.stage_changed.emit(key)

    def set_system_status(self, text: str, state: str = "waiting") -> None:
        object_names = {
            "waiting": "FooterWaiting",
            "ready": "FooterReady",
            "warning": "FooterWarning",
        }
        self.system_status.setText(f"●  {text}")
        self.system_status.setObjectName(object_names.get(state, "FooterWaiting"))
        self.system_status.style().unpolish(self.system_status)
        self.system_status.style().polish(self.system_status)

    def set_dataset_status(self, text: str) -> None:
        self.dataset_status.setText(f"▣  {text}")

    def _update_clock(self) -> None:
        now = QDateTime.currentDateTime()
        self.date_label.setText(now.toString("ddd, MMM d, yyyy"))
        self.time_label.setText(now.toString("h:mm AP"))
