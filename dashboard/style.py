from string import Template

PALETTES = {
    "dark": {
        "bg": "#0f1419", "panel": "#171d25", "panel_alt": "#1e2630",
        "border": "#2a3441", "text": "#e6edf3", "muted": "#8b98a8",
        "accent": "#3b9eff", "accent_hover": "#5cb0ff", "select": "#24456b",
        "ok": "#2ecc71", "warn": "#f5a623", "danger": "#ff5c5c",
    },
    "light": {
        "bg": "#f4f6f9", "panel": "#ffffff", "panel_alt": "#eef1f5",
        "border": "#d5dbe3", "text": "#1c2430", "muted": "#667385",
        "accent": "#1a73e8", "accent_hover": "#3b8af0", "select": "#cfe2fb",
        "ok": "#1e9e55", "warn": "#d98200", "danger": "#d93636",
    },
}

QSS = Template("""
QWidget {
    background-color: $bg; color: $text;
    font-family: "Segoe UI", "Inter", "Arial"; font-size: 13px;
}
QLabel { background: transparent; }
QLabel#AppTitle { font-size: 20px; font-weight: 700; }
QLabel#Muted { color: $muted; }

QFrame#Card {
    background-color: $panel; border: 1px solid $border; border-radius: 10px;
}
QLabel#CardTitle { color: $muted; font-size: 12px; }
QLabel#CardValue { font-size: 26px; font-weight: 700; }

QGroupBox {
    background-color: $panel; border: 1px solid $border; border-radius: 10px;
    margin-top: 14px; padding: 14px 8px 8px 8px; font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 14px; padding: 0 6px;
    color: $muted; background-color: $bg;
}

QTableView {
    background-color: $panel; alternate-background-color: $panel_alt;
    border: 1px solid $border; border-radius: 8px; gridline-color: $border;
    selection-background-color: $select; selection-color: $text;
}
QHeaderView::section {
    background-color: $panel_alt; color: $muted; padding: 6px;
    border: none; border-bottom: 1px solid $border; font-weight: 600;
}
QTableCornerButton::section { background-color: $panel_alt; border: none; }

QPushButton {
    background-color: $panel_alt; border: 1px solid $border;
    border-radius: 6px; padding: 6px 14px;
}
QPushButton:hover { border-color: $accent; }
QPushButton:pressed { background-color: $select; }
QPushButton#Primary { background-color: $accent; color: white; border: none; }
QPushButton#Primary:hover { background-color: $accent_hover; }

QSplitter::handle { background-color: transparent; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $border; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $muted; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QToolTip { background-color: $panel_alt; color: $text; border: 1px solid $border; padding: 4px; }
""")


def get_colors(dark):
    return PALETTES["dark" if dark else "light"]


def extra_qss(dark):
    return QSS.substitute(get_colors(dark))