import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow
from .ui.theme import APP_STYLESHEET


def create_application() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    QApplication.setApplicationName("BART Spine")
    QApplication.setOrganizationName("BART LAB")
    app.setStyleSheet(APP_STYLESHEET)
    return app


def main() -> int:
    app = create_application()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
