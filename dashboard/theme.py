import json
from pathlib import Path

from PyQt5.QtWidgets import QApplication

SETTINGS = Path(__file__).with_name("theme_setting.json")


def saved_dark_mode():
    """Return True if dark mode was used last time (dark by default)."""
    try:
        return json.loads(SETTINGS.read_text())["dark"]
    except Exception:
        return True


def apply_theme(dark):
    """Remember the mode. The colors come from style.py."""
    SETTINGS.write_text(json.dumps({"dark": dark}))
    app = QApplication.instance()
    if app is not None:
        app.setStyle("Fusion")