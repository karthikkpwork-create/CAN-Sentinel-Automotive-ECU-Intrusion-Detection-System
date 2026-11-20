import json
from pathlib import Path

from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication

SETTINGS = Path(__file__).with_name("theme_setting.json")


def _settings():
    return QSettings("CAN-Sentinel", "Dashboard")


def saved_dark_mode():
    """Return the saved mode, migrating the legacy JSON setting if present."""
    legacy_dark_mode = True
    if SETTINGS.exists():
        legacy_value = json.loads(SETTINGS.read_text(encoding="utf-8")).get("dark")
        if isinstance(legacy_value, bool):
            legacy_dark_mode = legacy_value
    return _settings().value("dark_mode", legacy_dark_mode, type=bool)


def apply_theme(dark):
    """Apply and remember the application-wide color palette."""
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

    _settings().setValue("dark_mode", bool(dark))
