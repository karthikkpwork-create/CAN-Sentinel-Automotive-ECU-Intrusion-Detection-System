"""CAN ID monitoring panel for the dashboard."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


def normalize_can_id(value) -> str:
    """Return a stable lowercase CAN ID string without the 0x prefix."""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if text.startswith("0x"):
        text = text[2:]
    return text


class CanIdMonitorPanel(QWidget):
    """Live summary of CAN IDs with counts, intervals, and activity status."""

    HEADERS = ["CAN ID", "Frames", "Rate", "Last seen", "Mean gap", "Status"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats: Dict[str, Dict[str, object]] = {}
        self._clock = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.title = QLabel("CAN ID Monitor")
        self.title.setObjectName("SectionTitle")
        layout.addWidget(self.title)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def reset(self):
        self._stats.clear()
        self.table.setRowCount(0)

    def record_frame(self, frame):
        """Record one frame into the live ID statistics."""
        can_id = normalize_can_id(frame.get("can_id", ""))
        if not can_id:
            return

        try:
            timestamp = float(frame.get("timestamp", 0))
        except (TypeError, ValueError):
            timestamp = None

        if can_id not in self._stats:
            self._stats[can_id] = {
                "count": 0,
                "first_seen": timestamp,
                "last_seen": timestamp,
                "last_interval": None,
                "intervals": [],
            }

        stats = self._stats[can_id]
        stats["count"] = int(stats["count"]) + 1
        if stats["first_seen"] is None or (timestamp is not None and stats["first_seen"] is not None and timestamp < float(stats["first_seen"])):
            stats["first_seen"] = timestamp

        if timestamp is not None and stats["last_seen"] is not None:
            interval = timestamp - float(stats["last_seen"])
            if interval >= 0:
                stats["last_interval"] = interval
                stats["intervals"].append(interval)

        stats["last_seen"] = timestamp
        self._refresh()

    def load_rows(self, rows, header):
        """Load a CSV snapshot and rebuild the monitor from it."""
        self.reset()
        lower = [str(h).strip().lower() for h in header]
        can_name = "can_id_hex" if "can_id_hex" in lower else "can_id"
        can_idx = lower.index(can_name) if can_name in lower else None
        time_idx = lower.index("timestamp") if "timestamp" in lower else None
        for row in rows:
            if can_idx is None:
                continue
            can_id = normalize_can_id(row[can_idx] if can_idx < len(row) else "")
            if not can_id:
                continue
            frame = {"can_id": can_id}
            if time_idx is not None and time_idx < len(row):
                try:
                    frame["timestamp"] = float(row[time_idx])
                except (TypeError, ValueError):
                    frame["timestamp"] = None
            self.record_frame(frame)

    def _status_for(self, can_id: str, stats: Dict[str, object]) -> str:
        last_seen = stats.get("last_seen")
        if last_seen is None:
            return "No data"
        now = self._now_seconds()
        if now - float(last_seen) <= 5.0:
            return "Active"
        return "Quiet"

    def _now_seconds(self):
        try:
            import time
            return time.time()
        except Exception:
            return 0.0

    def snapshot(self):
        """Return rows sorted by frame count descending."""
        rows = []
        for can_id, stats in self._stats.items():
            count = int(stats["count"])
            intervals = list(stats.get("intervals", []))
            mean_gap = sum(intervals) / len(intervals) if intervals else 0.0
            first_seen = stats.get("first_seen")
            last_seen = stats.get("last_seen")
            elapsed = 1.0
            if first_seen is not None and last_seen is not None:
                elapsed = max(1.0, float(last_seen) - float(first_seen))
            rows.append({
                "can_id": can_id,
                "count": count,
                "rate": round(count / elapsed, 3),
                "last_seen": last_seen,
                "mean_gap": mean_gap,
                "status": self._status_for(can_id, stats),
            })
        rows.sort(key=lambda row: (-row["count"], row["can_id"]))
        return rows

    def _refresh(self):
        rows = self.snapshot()
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            self.table.setItem(row_idx, 0, QTableWidgetItem(row["can_id"]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(row["count"])))

            rate_value = "{:.2f}/s".format(row["rate"]) if row["rate"] else "0.00/s"
            self.table.setItem(row_idx, 2, QTableWidgetItem(rate_value))

            last_seen = row["last_seen"]
            if last_seen is None:
                value = "-"
            else:
                value = f"{float(last_seen):.3f}"
            self.table.setItem(row_idx, 3, QTableWidgetItem(value))

            mean_gap = row["mean_gap"]
            self.table.setItem(row_idx, 4, QTableWidgetItem(f"{mean_gap:.3f}s" if mean_gap else "-"))
            self.table.setItem(row_idx, 5, QTableWidgetItem(row["status"]))

            for col in range(self.table.columnCount()):
                item = self.table.item(row_idx, col)
                if item is None:
                    continue
                if row["status"] == "Active":
                    item.setBackground(self.palette().alternateBase())
                else:
                    item.setBackground(self.table.palette().base())

        if rows:
            self.table.resizeRowsToContents()


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    panel = CanIdMonitorPanel()
    panel.resize(700, 260)
    panel.show()
    panel.record_frame({"timestamp": 1.0, "can_id": "0x123"})
    panel.record_frame({"timestamp": 2.0, "can_id": "123"})
    sys.exit(app.exec_())
