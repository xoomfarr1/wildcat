"""Tests for the live-data view, driven by the shared ConnectionModel."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from wildcat.gui.connection import ConnectionModel
from wildcat.gui.views.live_data_view import LiveDataView

app = QApplication([])


def test_live_data_view_populates_on_connect():
    """Connecting a session auto-reads signals into the table."""
    conn = ConnectionModel()
    view = LiveDataView(conn)

    conn.connect("Virtual (simulated)", "Mercedes C300 (2008)")

    signals = conn.read_live_data()
    # No fabricated data: a fresh connection yields no live signals.
    assert view.table.rowCount() == 0
    assert view.table.rowCount() == len(signals)
    assert view.status.text() == f"{len(signals)} signal(s)"

    conn.disconnect()
    assert view.table.rowCount() == 0
    assert view.status.text() == "Not connected"
