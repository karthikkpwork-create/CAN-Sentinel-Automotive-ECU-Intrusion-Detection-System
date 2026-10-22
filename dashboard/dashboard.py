import csv
import random
import sys
import time
from collections import Counter

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableView, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QHeaderView,
    QSplitter, QGroupBox,
)
import pyqtgraph as pg          # keep this import AFTER the PyQt5 imports

from widgets import MessageRateChart, StatCard, StatusPill
from theme import apply_theme, saved_dark_mode   # functions from your theme.py
from style import extra_qss, get_colors          # extra look, works on top of theme.py

ALERT_COLUMNS = ["Time", "ID", "Type", "Score"]

NORMAL_VALUES = ("", "0", "normal", "benign", "none", "r", "false")
SUSPICIOUS_VALUES = ("suspicious", "warning", "warn")
LABEL_COLUMN_NAMES = ("label", "class", "attack", "type")

# see-through colors: readable on a light or a dark window
ATTACK_COLOR = QColor(220, 53, 69, 70)
SUSPICIOUS_COLOR = QColor(245, 166, 35, 70)


def is_normal(value):
    return str(value).strip().lower() in NORMAL_VALUES


def read_csv(path):
    """Return (header, rows). Short rows are padded, blank lines are skipped."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        rows = []
        for row in reader:
            if not any(row):
                continue
            row = row + [""] * (len(header) - len(row))
            rows.append(row[:len(header)])
    return header, rows


class CsvTableModel(QAbstractTableModel):
    """Table of frames loaded from a CSV file.
    If the file has a label column, attack rows are colored."""

    def __init__(self):
        super().__init__()
        self.header = []
        self.rows = []
        self.label_col = None

    def rowCount(self, parent=None):
        return len(self.rows)

    def columnCount(self, parent=None):
        return len(self.header)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self.rows[index.row()][index.column()]
        if role == Qt.ToolTipRole:
            return self.rows[index.row()][index.column()]
        if role == Qt.BackgroundRole and self.label_col is not None:
            value = self.rows[index.row()][self.label_col]
            if is_normal(value):
                return None
            if value.strip().lower() in SUSPICIOUS_VALUES:
                return SUSPICIOUS_COLOR
            return ATTACK_COLOR
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self.header[section]
            return str(section + 1)
        return None

    def load_csv(self, path):
        header, rows = read_csv(path)
        lower = [h.strip().lower() for h in header]
        label_col = None
        for name in LABEL_COLUMN_NAMES:
            if name in lower:
                label_col = lower.index(name)
                break
        self.beginResetModel()
        self.header = header
        self.rows = rows
        self.label_col = label_col
        self.endResetModel()


class AlertTableModel(QAbstractTableModel):
    """Table of alerts. Rows are added one at a time with add()."""

    def __init__(self):
        super().__init__()
        self.rows = []

    def rowCount(self, parent=None):
        return len(self.rows)

    def columnCount(self, parent=None):
        return len(ALERT_COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self.rows[index.row()][index.column()]
        if role == Qt.BackgroundRole:
            return ATTACK_COLOR
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return ALERT_COLUMNS[section]
            return str(section + 1)
        return None

    def add(self, values):
        n = len(self.rows)
        self.beginInsertRows(QModelIndex(), n, n)
        self.rows.append([str(v) for v in values])
        self.endInsertRows()

    def clear(self):
        self.beginResetModel()
        self.rows = []
        self.endResetModel()


class Dashboard(QMainWindow):
    def __init__(self, csv_path=None):
        super().__init__()
        self.setWindowTitle("CAN-Sentinel Dashboard")
        self.resize(1200, 720)

        self.frame_model = CsvTableModel()
        self.alert_model = AlertTableModel()
        self.dark = saved_dark_mode()                 # last mode used
        self.rate_chart = MessageRateChart(
            window_seconds=60,
            dark=self.dark,
        )

        # ---- top bar: title, status, buttons ----
        title = QLabel("Infotact Solutions CAN-Sentinel")
        title.setObjectName("AppTitle")
        self.status_pill = StatusPill("No alerts", "#2ecc71")

        btn_frames = QPushButton("Open frames CSV...")
        btn_frames.setObjectName("Primary")
        btn_frames.clicked.connect(self.choose_frames_file)
        btn_alerts = QPushButton("Open alerts CSV...")
        btn_alerts.clicked.connect(self.choose_alerts_file)
        btn_test = QPushButton("Add test alert")
        btn_test.clicked.connect(self.add_test_alert)
        btn_clear = QPushButton("Clear alerts")
        btn_clear.clicked.connect(self.clear_alerts)
        self.theme_button = QPushButton()             # dark / light button
        self.theme_button.clicked.connect(self.toggle_theme)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(title)
        top.addWidget(self.status_pill)
        top.addStretch()
        for b in (btn_frames, btn_alerts, btn_test, btn_clear, self.theme_button):
            top.addWidget(b)

        # ---- counter cards ----
        self.card_frames = StatCard("Frames loaded", 0)
        self.card_alerts = StatCard("Alerts", 0)
        self.card_type = StatCard("Last alert type", "None", font_px=18)
        self.card_score = StatCard("Highest score", "-")
        cards = QHBoxLayout()
        cards.setSpacing(12)
        for c in (self.card_frames, self.card_alerts, self.card_type, self.card_score):
            cards.addWidget(c)

        # ---- left: frame table ----
        self.frame_view = QTableView()
        self.frame_view.setModel(self.frame_model)
        self.frame_view.setAlternatingRowColors(True)
        self.frame_view.setShowGrid(False)
        self.frame_view.setWordWrap(False)
        hh = self.frame_view.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setDefaultSectionSize(120)
        hh.setStretchLastSection(True)
        frames_box = QGroupBox("Frames")
        fl = QVBoxLayout()
        fl.addWidget(self.frame_view)
        frames_box.setLayout(fl)

        # ---- right top: alert panel ----
        self.alert_view = QTableView()
        self.alert_view.setModel(self.alert_model)
        self.alert_view.setShowGrid(False)
        header = self.alert_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        alerts_box = QGroupBox("Alerts")
        al = QVBoxLayout()
        al.addWidget(self.alert_view)
        alerts_box.setLayout(al)

        # ---- right bottom: alerts by type chart ----
        self.plot = pg.PlotWidget()
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(False, False)
        self.plot.hideButtons()
        
        chart_box = QGroupBox("Alerts by type")
        cl = QVBoxLayout()
        cl.addWidget(self.plot)
        chart_box.setLayout(cl)

        rate_box = QGroupBox("Message rate")
        rate_layout = QVBoxLayout()
        rate_layout.addWidget(self.rate_chart)
        rate_box.setLayout(rate_layout)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        rl.addWidget(alerts_box, 3)
        rl.addWidget(chart_box, 2)
        rl.addWidget(rate_box, 2)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(frames_box)
        splitter.addWidget(right)
        splitter.setSizes([700, 450])
        splitter.setChildrenCollapsible(False)

        self.status = QLabel("No file loaded")
        self.status.setObjectName("Muted")

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addLayout(cards)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.status)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.set_theme(self.dark)                     # apply the saved mode
        self.update_counters()
        if csv_path:
            self.load_frames(csv_path)

    # ---------- dark / light mode (uses theme.py, then style.py) ----------
    def set_theme(self, dark):
        self.dark = dark
        apply_theme(dark)                             # your theme.py
        self.rate_chart.set_dark(dark)
        self.setStyleSheet(extra_qss(dark))           # extra look on top
        self.theme_button.setText("Light mode" if dark else "Dark mode")

        c = get_colors(dark)
        self.card_frames.set_accent(c["accent"])
        self.card_alerts.set_accent(c["danger"])
        self.card_type.set_accent(c["warn"])
        self.card_score.set_accent(c["ok"])
        self.plot.setBackground(c["panel"])
        for side in ("left", "bottom"):
            axis = self.plot.getAxis(side)
            axis.setPen(c["border"])
            axis.setTextPen(c["muted"])
        self.plot.showGrid(x=False, y=True, alpha=0.15)
        self.update_counters()

    def toggle_theme(self):
        self.set_theme(not self.dark)

    # ---------- counters, status and chart ----------
    def update_counters(self):
        c = get_colors(self.dark)
        rows = self.alert_model.rows
        n_alerts = len(rows)

        self.card_frames.set_value(self.frame_model.rowCount())
        self.card_alerts.set_value(n_alerts)
        self.card_type.set_value(rows[-1][2] if rows else "None")

        scores = []
        for r in rows:
            try:
                scores.append(float(r[3]))
            except ValueError:
                pass
        self.card_score.set_value(f"{max(scores):.2f}" if scores else "-")

        if n_alerts:
            self.status_pill.set_state("ALERTS FOUND", c["danger"])
        else:
            self.status_pill.set_state("No alerts", c["ok"])

        self.update_chart()

    def update_chart(self):
        c = get_colors(self.dark)
        counts = Counter(r[2] for r in self.alert_model.rows).most_common(8)
        self.plot.clear()
        if not counts:
            self.plot.getAxis("bottom").setTicks([[]])
            return
        xs = list(range(len(counts)))
        bars = pg.BarGraphItem(x=xs, height=[n for _, n in counts],
                               width=0.6, brush=c["accent"])
        self.plot.addItem(bars)
        self.plot.getAxis("bottom").setTicks(
            [[(i, name) for i, (name, _) in enumerate(counts)]])

    # ---------- frame table ----------
    def choose_frames_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open frames CSV", "", "CSV files (*.csv)")
        if path:
            self.load_frames(path)

    def load_frames(self, path):
        try:
            self.frame_model.load_csv(path)
            self.rate_chart.record(self.frame_model.rowCount())
            self.status.setText(f"{path}  |  {self.frame_model.rowCount()} frames")
        except Exception as e:
            self.status.setText(f"Could not load file: {e}")
        self.update_counters()

    # ---------- alert panel ----------
    def add_alert(self, when, can_id, attack_type, score, refresh=True):
        """The detector (Day 7) calls this once for every alert it finds."""
        self.alert_model.add((when, can_id, attack_type, score))
        if refresh:
            self.alert_view.scrollToBottom()
            self.update_counters()

    def clear_alerts(self):
        self.alert_model.clear()
        self.update_counters()

    def choose_alerts_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open alerts CSV", "", "CSV files (*.csv)"
        )
        if path:
            self.load_alerts(path)

    def load_alerts(self, path):
        try:
            header, rows = read_csv(path)
        except Exception as e:
            self.status.setText(f"Could not load file: {e}")
            return

        lower = [h.strip().lower() for h in header]

        def pick(names, position):
            for n in names:
                if n in lower:
                    return lower.index(n)

            if position is not None and position < len(header):
                return position

            return None

        idx = [
            pick(["time", "timestamp"], 0),
            pick(["id", "can_id", "arbitration_id"], 1),
            pick(["type", "attack", "attack_type", "label"], 2),
            pick(
                ["score", "attack_score"],
                3 if len(header) <= 4 else None
            ),
        ]

        added = 0

        for row in rows:
            values = [
                row[i] if i is not None and i < len(row) else ""
                for i in idx
            ]

            if is_normal(values[2]):
                continue

            self.add_alert(*values, refresh=False)
            added += 1

        self.alert_view.scrollToBottom()
        self.update_counters()

        self.status.setText(
            f"{path} | loaded {added} alerts "
            f"({len(rows) - added} normal rows skipped)"
        )
    def add_test_alert(self):
        """For testing only. Remove when the real detector is connected."""
        kinds = ["injection", "unknown ID", "payload tampering", "missing message"]
        self.add_alert(time.strftime("%H:%M:%S"),
                       hex(random.randint(0x100, 0x7FF)),
                       random.choice(kinds),
                       round(random.uniform(0.6, 1.0), 2))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = sys.argv[1] if len(sys.argv) > 1 else None
    window = Dashboard(path)
    window.show()
    sys.exit(app.exec_())