from collections import OrderedDict

from .base import WorkflowPage


class WorkflowRegistry:
    """
    Small registry for procedure pages.

    This avoids hard-coding every future page into MainWindow. A new workflow can be registered
    in one location and the shell will add it automatically.
    """

    def __init__(self):
        self._pages: OrderedDict[str, WorkflowPage] = OrderedDict()

    def register(self, page: WorkflowPage) -> None:
        key = page.workflow_key
        if key in self._pages:
            raise ValueError(f"Workflow already registered: {key}")
        self._pages[key] = page

    def pages(self) -> tuple[WorkflowPage, ...]:
        return tuple(self._pages.values())
