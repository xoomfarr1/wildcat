"""Programming tab — placeholder.

Accepts the shared :class:`~wildcat.gui.connection.ConnectionModel` so the window
builds; the security-access / ECU-identification UI is wired next.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wildcat.gui.connection import ConnectionModel


class ProgrammingView(QWidget):
    def __init__(self, connection: ConnectionModel, parent=None):
        super().__init__(parent)
        self._connection = connection
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Programming"))
