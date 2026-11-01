"""id_chart.py - live bar chart of how many frames each CAN ID has sent."""
from collections import Counter

from PyQt5.QtCore import QTimer
import pyqtgraph as pg


class IdCountChart(pg.PlotWidget):
    """Bar chart of the busiest CAN IDs. The busiest ID is drawn in orange."""

    def __init__(self, top_n=8, dark=True, parent=None):
        super().__init__(parent)
        self.top_n = top_n
        self.counts = Counter()
        self._changed = False

        self.setLabel("left", "Frames")
        self.setLabel("bottom", "CAN ID (busiest first)")
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.hideButtons()
        self.showGrid(x=False, y=True, alpha=0.2)
        self.set_dark(dark)                 # also draws the empty chart

        # redraw at most twice per second, even if thousands of frames arrive
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)

    # ---------- data ----------
    def add(self, can_id):
        """Call once for every frame."""
        self.counts[str(can_id)] += 1
        self._changed = True

    def reset_counts(self):
        """Forget all counts (used when a new live session starts)."""
        self.counts.clear()
        self._changed = True

    def top(self):
        """The busiest IDs as a list of (can_id, count)."""
        return self.counts.most_common(self.top_n)

    # ---------- drawing ----------
    def _tick(self):
        if self._changed:
            self._changed = False
            self._redraw()

    def _redraw(self):
        self.clear()                        # removes the old bars
        data = self.top()
        axis = self.getAxis("bottom")
        if not data:
            axis.setTicks([[]])
            self.setYRange(0, 10)
            return

        heights = [count for _, count in data]
        brushes = [self.hot_color] + [self.bar_color] * (len(data) - 1)
        bars = pg.BarGraphItem(x=list(range(len(data))), height=heights,
                               width=0.6, brushes=brushes)
        self.addItem(bars)
        axis.setTicks([[(i, name) for i, (name, _) in enumerate(data)]])
        self.setXRange(-0.7, self.top_n - 0.3)
        self.setYRange(0, max(heights) * 1.15)

    def set_dark(self, dark):
        """Follow the dark / light mode button."""
        self.setBackground("#1e1e1e" if dark else "#ffffff")
        axis_color = "#cccccc" if dark else "#333333"
        for name in ("left", "bottom"):
            ax = self.getAxis(name)
            ax.setPen(axis_color)
            ax.setTextPen(axis_color)
        self.bar_color = "#3b82f6"
        self.hot_color = "#f59e0b"
        self._redraw()