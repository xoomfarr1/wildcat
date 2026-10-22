"""Main application window."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wildcat.gui.theme import GLASS_STYLE
from wildcat.gui.views.diagnostics_view import DiagnosticsView
from wildcat.gui.views.live_data_view import LiveDataView
from wildcat.gui.views.programming_view import ProgrammingView
from wildcat.gui.web_launcher import open_web_ui


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wildcat Diagnostics")
        self.resize(1000, 700)
        self.setStyleSheet(GLASS_STYLE)

        tabs = QTabWidget()
        tabs.addTab(DiagnosticsView(), "Diagnostics")
        tabs.addTab(LiveDataView(), "Live Data")
        tabs.addTab(ProgrammingView(), "Programming")

        open_btn = QPushButton("Open Web UI")
        open_btn.clicked.connect(lambda: open_web_ui())

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(tabs)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(open_btn)
        layout.addLayout(btn_row)
        self.setCentralWidget(container)
