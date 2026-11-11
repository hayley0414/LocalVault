"""
styles.py —— 暗色主题（QSS 样式表）

简洁暗色 GUI。所有颜色在此集中定义，方便统一调整。
"""

DARK_STYLE = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #1e1e2e;
}
QListWidget, QLineEdit, QTextEdit, QComboBox, QPlainTextEdit {
    background-color: #282838;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px;
    color: #cdd6f4;
}
QListWidget::item:selected {
    background-color: #45475a;
    color: #f5c2e7;
}
QPushButton {
    background-color: #313244;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 6px 12px;
    color: #cdd6f4;
}
QPushButton:hover {
    background-color: #45475a;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton#danger {
    background-color: #45283c;
    border: 1px solid #f38ba8;
    color: #f38ba8;
}
QLabel#title {
    font-size: 18px;
    font-weight: bold;
    color: #f5c2e7;
}
QLabel#hint {
    color: #9399b2;
    font-size: 12px;
}
QStatusBar {
    background-color: #181825;
    color: #9399b2;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    color: #f5c2e7;
}
QScrollBar:vertical {
    background: #282838;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 5px;
}
"""
