"""Programming tab — ECU identification and security access.

Drives the shared :class:`~wildcat.gui.connection.ConnectionModel` to identify
the connected ECU and run a security-access (seed/key) exchange for flashing.
The actual ECU flashing lives in ``programming/flash.py`` (out of scope here):
this tab only proves the seed/key handshake succeeds so the flasher can
proceed once its driver is wired up.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wildcat.core.exceptions import WildcatError
from wildcat.gui.connection import ConnectionModel


class ProgrammingView(QWidget):
    """ECU identification panel and security-access (seed/key) exchange."""

    def __init__(self, connection: ConnectionModel, parent=None) -> None:
        super().__init__(parent)
        self._connection = connection

        title = QLabel("ECU Programming")
        title.setObjectName("tab_title")

        # ECU information group ------------------------------------------------
        self.vehicle_label = QLabel("")
        self.ecu_id_label = QLabel("")
        self.security_label = QLabel("")
        ecu_group = QGroupBox("ECU Info")
        ecu_layout = QFormLayout()
        ecu_layout.addRow("Vehicle:", self.vehicle_label)
        ecu_layout.addRow("ECU ID:", self.ecu_id_label)
        ecu_layout.addRow("Security Required:", self.security_label)
        ecu_group.setLayout(ecu_layout)

        # Security access group ------------------------------------------------
        self.request_button = QPushButton("Request Security Access")
        self.request_button.clicked.connect(self._request_security_access)
        self.status = QLabel("Not connected")
        self.status.setObjectName("hint")
        self.seed_label = QLabel("")
        self.key_label = QLabel("")
        security_group = QGroupBox("Security Access")
        sec_layout = QFormLayout()
        sec_layout.addRow("Seed:", self.seed_label)
        sec_layout.addRow("Key:", self.key_label)
        security_group.setLayout(sec_layout)

        # Layout ---------------------------------------------------------------
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(ecu_group)
        layout.addWidget(self.request_button)
        layout.addWidget(self.status)
        layout.addWidget(security_group)

        # React to session state so the fields stay in sync with the bus.
        connection.connected.connect(self._on_connected)
        connection.disconnected.connect(self._on_disconnected)

    # ------------------------------------------------------------------ events
    def _on_connected(self, _car) -> None:
        """Populate ECU info as soon as a session comes up."""
        try:
            info = self._connection.ecu_info()
        except WildcatError as exc:
            self.status.setText(str(exc))
            return
        self.vehicle_label.setText(info["name"])
        self.ecu_id_label.setText(hex(info["ecu_id"]))
        self.security_label.setText("Yes" if info["security_required"] else "No")
        self.status.setText("Ready")

    def _on_disconnected(self) -> None:
        """Clear all fields when the session drops."""
        self.vehicle_label.setText("")
        self.ecu_id_label.setText("")
        self.security_label.setText("")
        self.seed_label.setText("")
        self.key_label.setText("")
        self.status.setText("Not connected")

    # ------------------------------------------------------------------ actions
    def _request_security_access(self) -> None:
        """Run the seed/key exchange and surface the results (no modal)."""
        try:
            seed, key = self._connection.perform_security_access()
        except WildcatError as exc:
            self.status.setText(str(exc))
            return
        self.seed_label.setText(seed.hex())
        self.key_label.setText(key.hex())
        self.status.setText("Unlocked")
