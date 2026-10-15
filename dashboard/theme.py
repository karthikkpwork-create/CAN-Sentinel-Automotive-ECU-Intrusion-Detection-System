from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication


def _settings():
    return QSettings("CAN-Sentinel", "Dashboard")


def saved_dark_mode():
    """True if the user left the dashboard in dark mode last time."""
    return _settings().value("dark_mode", False, type=bool)


def apply_theme(dark):
    """Switch the whole application to dark or light colors and remember it."""
    app = QApplication.instance()
    app.setStyle("Fusion")

    if not dark:
        app.setPalette(app.style().standardPalette())
    else:
        p = QPalette()
        p.setColor(QPalette.Window, QColor(53, 53, 53))
        p.setColor(QPalette.WindowText, Qt.white)
        p.setColor(QPalette.Base, QColor(35, 35, 35))
        p.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        p.setColor(QPalette.ToolTipBase, Qt.white)
        p.setColor(QPalette.ToolTipText, Qt.black)
        p.setColor(QPalette.Text, Qt.white)
        p.setColor(QPalette.Button, QColor(53, 53, 53))
        p.setColor(QPalette.ButtonText, Qt.white)
        p.setColor(QPalette.BrightText, Qt.red)
        p.setColor(QPalette.Highlight, QColor(42, 130, 218))
        p.setColor(QPalette.HighlightedText, Qt.black)
        p.setColor(QPalette.Disabled, QPalette.Text, Qt.gray)
        p.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.gray)
        app.setPalette(p)

    _settings().setValue("dark_mode", dark)