from enum import Enum
from typing import ClassVar

from PySide6.QtWidgets import QLabel


class StatusState(Enum):
    """Presentation states shared by setup status indicators."""

    WAITING = "waiting"
    READY = "ready"
    WARNING = "warning"
    ERROR = "error"


class StatusIndicator(QLabel):
    """A status label that starts neutral until a subsystem reports real state."""

    _STYLE_NAMES: ClassVar = {
        StatusState.WAITING: "StatusWaiting",
        StatusState.READY: "StatusOk",
        StatusState.WARNING: "StatusWarn",
        StatusState.ERROR: "StatusError",
    }
    _PREFIXES: ClassVar = {
        StatusState.WAITING: "…",
        StatusState.READY: "✓",
        StatusState.WARNING: "⚠",
        StatusState.ERROR: "✕",
    }

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.setWordWrap(True)
        self.set_status(StatusState.WAITING, "Waiting for status")

    def set_status(self, state: StatusState, detail: str = "") -> None:
        prefix = self._PREFIXES[state]
        suffix = f" — {detail}" if detail else ""
        self.setText(f"{prefix}  {self.name}{suffix}")
        self.setObjectName(self._STYLE_NAMES[state])
        self.style().unpolish(self)
        self.style().polish(self)

    def set_connected(self, connected: bool | None, *, unavailable: str = "Disconnected") -> None:
        if connected is None:
            self.set_status(StatusState.WAITING, "Waiting for status")
        elif connected:
            self.set_status(StatusState.READY, "Connected")
        else:
            self.set_status(StatusState.WARNING, unavailable)
