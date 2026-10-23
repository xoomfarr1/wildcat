"""Diagnostics tab — read and clear stored fault codes (DTCs).

This is the reference tab implementation: it drives the shared
:class:`~wildcat.gui.connection.ConnectionModel`, renders the fault codes in a
table, and auto-reads when a session connects. The live-data and programming
tabs follow the same pattern.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wildcat.core.exceptions import WildcatError
from wildcat.gui.connection import ConnectionModel


class DiagnosticsView(QWidget):
    """A table of the vehicle's stored fault codes with read/clear controls."""

    def __init__(self, connection: ConnectionModel) -> None:
        super().__init__()
        self._connection = connection

        title = QLabel("Stored Fault Codes")
        title.setObjectName("tab_title")

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Code", "Description", "Severity", "Temp"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        read_btn = QPushButton("Read DTCs")
        read_btn.clicked.connect(self._read)
        clear_btn = QPushButton("Clear Codes")
        clear_btn.clicked.connect(self._clear)
        self.status = QLabel("Not connected")
        self.status.setObjectName("hint")

        btn_row = QHBoxLayout()
        btn_row.addWidget(read_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.status)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.table)
        layout.addLayout(btn_row)

        # React to session state so the table stays in sync with the bus.
        connection.connected.connect(self._on_connected)
        connection.disconnected.connect(self._on_disconnected)

    # ------------------------------------------------------------------ events
    def _on_connected(self, _car) -> None:
        """Auto-read fault codes as soon as a session comes up."""
        self._read()

    def _on_disconnected(self) -> None:
        self._populate([])
        self.status.setText("Not connected")

    # -------------------------------------------------------------------- actions
    def _read(self) -> None:
        try:
            dtcs = self._connection.read_dtcs()
        except WildcatError as exc:  # surfaced centrally by the main window
            self.status.setText(str(exc))
            return
        self._populate(dtcs)
        self.status.setText(f"{len(dtcs)} code(s)")

    def _clear(self) -> None:
        try:
            self._connection.clear_dtcs()
        except WildcatError as exc:
            QMessageBox.warning(self, "Wildcat", str(exc))
            return
        self._populate([])
        self.status.setText("Codes cleared")

    # ------------------------------------------------------------------ render
    def _populate(self, dtcs) -> None:
        self.table.setRowCount(len(dtcs))
        for row, dtc in enumerate(dtcs):
            self.table.setItem(row, 0, QTableWidgetItem(str(dtc.code)))
            self.table.setItem(row, 1, QTableWidgetItem(str(dtc.description)))
            self.table.setItem(row, 2, QTableWidgetItem(str(dtc.severity)))
            self.table.setItem(
                row, 3, QTableWidgetItem("yes" if dtc.is_temporary else "")
            )
        self.table.scrollToTop()
