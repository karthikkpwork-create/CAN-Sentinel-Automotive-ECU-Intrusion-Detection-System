import csv
import random
import sys
import time

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableView, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QHeaderView,
    QSplitter, QGroupBox,
)

from theme import apply_theme, saved_dark_mode   # functions from your theme.py

ALERT_COLUMNS = ["Time", "ID", "Type", "Score"]


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
    """Table of frames loaded from a CSV file."""

    def __init__(self):
        super().__init__()
        self.header = []
        self.rows = []

    def rowCount(self, parent=None):
        return len(self.rows)

    def columnCount(self, parent=None):
        return len(self.header)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and index.isValid():
            return self.rows[index.row()][index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self.header[section]
            return str(section + 1)
        return None

    def load_csv(self, path):
        header, rows = read_csv(path)
        self.beginResetModel()
        self.header = header
        self.rows = rows
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
            # see-through red: readable on a light or a dark window
            return QColor(220, 53, 69, 70)
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
        self.resize(1100, 650)

        self.frame_model = CsvTableModel()
        self.alert_model = AlertTableModel()
        self.dark = saved_dark_mode()                 # last mode used

        # ---- top bar: buttons and counters ----
        btn_frames = QPushButton("Open frames CSV...")
        btn_frames.clicked.connect(self.choose_frames_file)
        btn_alerts = QPushButton("Open alerts CSV...")
        btn_alerts.clicked.connect(self.choose_alerts_file)
        btn_test = QPushButton("Add test alert")
        btn_test.clicked.connect(self.add_test_alert)
        btn_clear = QPushButton("Clear alerts")
        btn_clear.clicked.connect(self.clear_alerts)
        self.theme_button = QPushButton()             # dark / light button
        self.theme_button.clicked.connect(self.toggle_theme)

        self.lbl_frames = QLabel()
        self.lbl_alerts = QLabel()
        self.lbl_frames.setStyleSheet(
            "font-size: 16px; font-weight: bold; padding: 4px 12px;")
        self.lbl_alerts.setStyleSheet(
            "font-size: 16px; font-weight: bold; padding: 4px 12px; color: #e53935;")

        top = QHBoxLayout()
        for b in (btn_frames, btn_alerts, btn_test, btn_clear):
            top.addWidget(b)
        top.addStretch()
        top.addWidget(self.lbl_frames)
        top.addWidget(self.lbl_alerts)
        top.addWidget(self.theme_button)

        # ---- left: frame table ----
        self.frame_view = QTableView()
        self.frame_view.setModel(self.frame_model)
        self.frame_view.setAlternatingRowColors(True)
        self.frame_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        frames_box = QGroupBox("Frames")
        fl = QVBoxLayout()
        fl.addWidget(self.frame_view)
        frames_box.setLayout(fl)

        # ---- right: alert panel ----
        self.alert_view = QTableView()
        self.alert_view.setModel(self.alert_model)
        header = self.alert_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        alerts_box = QGroupBox("Alerts")
        al = QVBoxLayout()
        al.addWidget(self.alert_view)
        alerts_box.setLayout(al)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(frames_box)
        splitter.addWidget(alerts_box)
        splitter.setSizes([700, 400])

        self.status = QLabel("No file loaded")

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.status)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.set_theme(self.dark)                     # apply the saved mode
        self.update_counters()
        if csv_path:
            self.load_frames(csv_path)

    # ---------- dark / light mode (uses theme.py) ----------
    def set_theme(self, dark):
        self.dark = dark
        apply_theme(dark)
        self.theme_button.setText("Light mode" if dark else "Dark mode")

    def toggle_theme(self):
        self.set_theme(not self.dark)

    # ---------- counters ----------
    def update_counters(self):
        self.lbl_frames.setText(f"Frames: {self.frame_model.rowCount()}")
        self.lbl_alerts.setText(f"Alerts: {self.alert_model.rowCount()}")

    # ---------- frame table ----------
    def choose_frames_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open frames CSV", "", "CSV files (*.csv)")
        if path:
            self.load_frames(path)

    def load_frames(self, path):
        try:
            self.frame_model.load_csv(path)
            self.status.setText(f"{path}  |  {self.frame_model.rowCount()} frames")
        except Exception as e:
            self.status.setText(f"Could not load file: {e}")
        self.update_counters()

    # ---------- alert panel ----------
    def add_alert(self, when, can_id, attack_type, score):
        """The detector (Day 7) calls this once for every alert it finds."""
        self.alert_model.add((when, can_id, attack_type, score))
        self.alert_view.scrollToBottom()
        self.update_counters()

    def clear_alerts(self):
        self.alert_model.clear()
        self.update_counters()

    def choose_alerts_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open alerts CSV", "", "CSV files (*.csv)")
        if path:
            self.load_alerts(path)

    def load_alerts(self, path):
        """Finds columns by name. If the names do not match, uses the first four columns."""
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
            return position if position < len(header) else None

        idx = [pick(["time", "timestamp"], 0),
               pick(["id", "can_id", "arbitration_id"], 1),
               pick(["type", "attack", "attack_type", "label"], 2),
               pick(["score", "attack_score"], 3)]
        added = 0
        for row in rows:
            values = [row[i] if i is not None else "" for i in idx]
            if str(values[2]).strip().lower() in ("normal", "benign", "0", ""):
                continue        # a normal frame is not an alert
            self.add_alert(*values)
            added += 1
        self.status.setText(
            f"{path}  |  loaded {added} alerts ({len(rows) - added} normal rows skipped)")

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