from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LiveDataView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Live Data"))
