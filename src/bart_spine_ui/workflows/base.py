from abc import abstractmethod

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class WorkflowPage(QWidget):
    """
    Base class for major procedure pages.

    Planned examples:
        ImagingPage
        PlanningPage
        RegistrationPage
        RobotPage
        NavigationPage

    Each page owns its local UI and controller connections but shares application-level services
    through explicit constructor dependencies.
    """

    status_changed = Signal(str)

    @property
    @abstractmethod
    def workflow_key(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def workflow_title(self) -> str:
        raise NotImplementedError

    def on_activated(self) -> None:
        """Hook called when the page becomes active."""

    def on_deactivated(self) -> None:
        """Hook called when the page is no longer active."""
