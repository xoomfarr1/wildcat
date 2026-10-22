"""Glass-like dark theme stylesheet for the desktop UI."""

GLASS_STYLE = """
QWidget {
    background-color: #1e1e2e;
    color: #e0e0e0;
    font-family: 'Segoe UI', 'SF Pro Text', sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #161625;
}
QTabWidget::pane {
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    background-color: rgba(30,30,46,0.85);
    margin-top: 4px;
}
QTabBar::tab {
    background-color: rgba(40,40,60,0.6);
    color: #b0b0c0;
    padding: 8px 18px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: rgba(70,70,110,0.9);
    color: #ffffff;
}
QPushButton {
    background-color: rgba(90,90,140,0.7);
    color: #ffffff;
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 10px;
    padding: 8px 16px;
}
QPushButton:hover {
    background-color: rgba(110,110,170,0.85);
}
QLabel {
    color: #e0e0e0;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: rgba(20,20,35,0.9);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 6px;
    color: #e0e0e0;
}
"""
