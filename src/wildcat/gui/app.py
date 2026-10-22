"""Application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from wildcat.gui.main_window import MainWindow


def run() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()
