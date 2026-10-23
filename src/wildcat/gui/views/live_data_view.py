"""Live signal data tab.

Reads live data from the shared :class:`~wildcat.gui.connection.ConnectionModel`
and renders it in a table, refreshing automatically while a session is
connected. The live-data tab mirrors the diagnostics view: it subscribes to the
model's connect/disconnect signals and lets the main window own error dialogs.
"""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wildcat.core.exceptions import WildcatError
from wildcat.gui.connection import ConnectionModel


class LiveDataView(QWidget):
    """A table of live vehicle signals with a manual refresh control."""

    def __init__(self, connection: ConnectionModel, parent=None) -> None:
        super().__init__(parent)
        self._connection = connection

        title = QLabel("Live Signals")
        title.setObjectName("tab_title")

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Signal", "Value", "Unit"])
        # Column 0 holds the signal name; let it absorb the extra width so the
        # Value/Unit columns stay compact.
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)

        self.status = QLabel("Not connected")
        self.status.setObjectName("hint")

        btn_row = QHBoxLayout()
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.status)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.table)
        layout.addLayout(btn_row)

        # The timer keeps the table current only while a session is live; it is
        # started on connect and stopped on disconnect so it never fires for a
        # closed session.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)

        # React to session state so the table stays in sync with the bus.
        connection.connected.connect(self._on_connected)
        connection.disconnected.connect(self._on_disconnected)

    # ------------------------------------------------------------------ events
    def _on_connected(self, _car) -> None:
        """Auto-read signals as soon as a session comes up."""
        self._refresh()
        self._timer.start(1000)

    def _on_disconnected(self) -> None:
        self._timer.stop()
        self._populate([])
        self.status.setText("Not connected")

    # -------------------------------------------------------------------- actions
    def _refresh(self) -> None:
        try:
            signals = self._connection.read_live_data()
        except WildcatError as exc:
            # main window owns the error dialog; we only update the status bar
            self.status.setText(str(exc))
            return
        self._populate(signals)
        self.status.setText(f"{len(signals)} signal(s)")

    # ------------------------------------------------------------------ render
    def _populate(self, signals) -> None:
        self.table.setRowCount(len(signals))
        for row, sig in enumerate(signals):
            self.table.setItem(row, 0, QTableWidgetItem(str(sig.name)))
            self.table.setItem(row, 1, QTableWidgetItem(str(sig.value)))
            self.table.setItem(row, 2, QTableWidgetItem(str(sig.unit)))
        self.table.scrollToTop()
