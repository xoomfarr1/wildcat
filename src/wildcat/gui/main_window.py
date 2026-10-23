"""Main application window.

Owns the single shared :class:`~wildcat.gui.connection.ConnectionModel` and the
top connection bar (connector + vehicle selectors, Connect/Disconnect, status).
Every tab receives the same connection model so they all reflect one session.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wildcat.gui.connection import ConnectionModel
from wildcat.gui.theme import GLASS_STYLE
from wildcat.gui.views.diagnostics_view import DiagnosticsView
from wildcat.gui.views.live_data_view import LiveDataView
from wildcat.gui.views.programming_view import ProgrammingView
from wildcat.gui.web_launcher import open_web_ui


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wildcat Diagnostics")
        self.resize(1150, 740)
        self.setStyleSheet(GLASS_STYLE)

        # One shared session for the whole window.
        self.connection = ConnectionModel()
        self.connection.status_changed.connect(self._on_status)
        self.connection.error.connect(self._on_error)

        # --- connection bar -------------------------------------------------
        conn_combo = QComboBox()
        conn_combo.addItems(self.connection.available_connectors())
        veh_combo = QComboBox()
        veh_combo.addItems(self.connection.available_vehicles())
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._toggle_connection)
        self.status_label = QLabel("Not connected")
        self.status_label.setObjectName("hint")

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Connector:"))
        bar.addWidget(conn_combo, 1)
        bar.addWidget(QLabel("Vehicle:"))
        bar.addWidget(veh_combo, 1)
        bar.addWidget(self.connect_btn)
        bar.addSpacing(16)
        bar.addWidget(self.status_label)

        self._conn_combo = conn_combo
        self._veh_combo = veh_combo

        # --- tabs -----------------------------------------------------------
        tabs = QTabWidget()
        tabs.addTab(DiagnosticsView(self.connection), "Diagnostics")
        tabs.addTab(LiveDataView(self.connection), "Live Data")
        tabs.addTab(ProgrammingView(self.connection), "Programming")

        open_btn = QPushButton("Open Web UI")
        open_btn.clicked.connect(lambda: open_web_ui())

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addLayout(bar)
        layout.addWidget(tabs)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(open_btn)
        layout.addLayout(btn_row)
        self.setCentralWidget(container)

    # ------------------------------------------------------------------ events
    def _toggle_connection(self) -> None:
        """Connect or disconnect from the selected connector + vehicle."""
        if self.connection.is_connected:
            self.connection.disconnect()
            self.connect_btn.setText("Connect")
            return
        try:
            self.connection.connect(
                self._conn_combo.currentText(), self._veh_combo.currentText()
            )
            self.connect_btn.setText("Disconnect")
        except Exception:  # noqa: BLE001,S110 - error signal shows the dialog
            pass

    def _on_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _on_error(self, message: str) -> None:
        self.status_label.setText("Error")
        QMessageBox.warning(self, "Wildcat", message)
