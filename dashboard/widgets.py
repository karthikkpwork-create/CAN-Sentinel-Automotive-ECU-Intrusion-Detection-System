"""widgets.py - small reusable pieces (PyQt5)."""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout


class StatCard(QFrame):
    """A small card with a title and a big number."""

    def __init__(self, title, value="0", accent=None, font_px=None):
        super().__init__()
        self.font_px = font_px
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("CardTitle")
        self.value_lbl = QLabel(str(value))
        self.value_lbl.setObjectName("CardValue")
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.setGraphicsEffect(shadow)

        if accent:
            self.set_accent(accent)

    def set_value(self, value):
        self.value_lbl.setText(str(value))

    def set_accent(self, color):
        style = f"color: {color};"
        if self.font_px:
            style += f" font-size: {self.font_px}px;"
        self.value_lbl.setStyleSheet(style)


class StatusPill(QLabel):
    """Rounded label such as 'No alerts' (green) or 'ALERTS FOUND' (red)."""

    def __init__(self, text="Ready", color="#2ecc71"):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.set_state(text, color)

    def set_state(self, text, color):
        self.setText(text)
        self.setStyleSheet(
            f"background-color: {color}; color: white; font-weight: 600;"
            "border-radius: 12px; padding: 4px 14px;"
        )