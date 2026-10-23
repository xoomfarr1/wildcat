import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from wildcat.gui.connection import ConnectionModel
from wildcat.gui.views.programming_view import ProgrammingView

_APP = QApplication.instance() or QApplication([])


def test_programming_view_ecu_info_and_security_access():
    connection = ConnectionModel()
    view = ProgrammingView(connection)

    connection.connect("Virtual (simulated)", "Mercedes C300 (2008)")

    assert view.vehicle_label.text() == "Mercedes C300 (2008)"
    assert view.ecu_id_label.text() == "0x12"
    assert view.security_label.text() == "Yes"
    assert view.status.text() == "Ready"

    view.request_button.click()

    assert view.seed_label.text()  # non-empty seed
    assert view.key_label.text()  # non-empty key
    assert view.status.text() == "Unlocked"

    connection.disconnect()
    assert view.status.text() == "Not connected"
    assert view.vehicle_label.text() == ""
