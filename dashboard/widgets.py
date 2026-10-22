"""widgets.py - small reusable pieces (PyQt5)."""
from collections import deque

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout
import pyqtgraph as pg

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


class MessageRateChart(pg.PlotWidget):
    """Live line chart of CAN messages per second (last N seconds)"""

    def __init__(self, window_seconds=60, dark=True, parent=None):
        super().__init__(parent)
        self.window_seconds = window_seconds
        self.rates = deque([0] * window_seconds, maxlen=window_seconds)
        self.x = list(range(-window_seconds + 1, 1))  # X-axis values for the last N seconds
        self._count = 0

        self.setLabel("left", "Messages per second")
        self.setLabel("bottom", "seconds ago")
        self.showGrid(x=True, y=True, alpha=0.2)
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.setYRange(0, 10)
        self.curve = self.plot(
            self.x, list(self.rates),
            pen=pg.mkPen("#3b82f6", width=2),
            fillLevel=0, brush=(59, 130, 246, 50),
        )
        self.set_dark(dark)

        # every 1 second: store the count and redraw
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def record(self, n=1):
        """Call this once for every frame (or record(len(batch)) for a batch)."""
        self._count += n

    def _tick(self):
        self.rates.append(self._count)
        self._count = 0
        self.curve.setData(self.x, list(self.rates))
        self.enableAutoRange(axis="y")

    def set_dark(self, dark):
        self.setBackground("#1e1e1e" if dark else "#ffffff")
        axis_color = "#cccccc" if dark else "#333333"
        for name in ("left", "bottom"):
            ax = self.getAxis(name)
            ax.setPen(axis_color)
            ax.setTextPen(axis_color)