import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from wildcat.gui import MainWindow


def test_gui_imports():
    assert MainWindow is not None
