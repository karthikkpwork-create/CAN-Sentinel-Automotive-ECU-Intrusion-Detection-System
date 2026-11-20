"""frame_detail.py - panel that shows one selected frame byte by byte."""
from PyQt5.QtWidgets import (QGroupBox, QHeaderView, QLabel, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

ID_NAMES = ("can_id", "can_id_hex", "arbitration_id", "id")
DATA_NAMES = ("data", "payload_hex", "payload")
DLC_NAMES = ("dlc", "length")
TIME_NAMES = ("timestamp", "time")


def find_column(header, names):
    """Column number for the first matching column name, or None."""
    lower = [str(h).strip().lower() for h in header]
    for name in names:
        if name in lower:
            return lower.index(name)
    return None


def split_bytes(text):
    """'11 22 AA' or '1122AA' -> ['11', '22', 'AA']"""
    parts = str(text).replace(",", " ").split()
    if len(parts) == 1 and len(parts[0]) > 2:        # no spaces: 1122AA
        s = parts[0]
        parts = [s[i:i + 2] for i in range(0, len(s), 2)]
    return [p.upper() for p in parts]


class FrameDetail(QGroupBox):
    """Shows the ID, length, time and every data byte of one frame."""

    def __init__(self, parent=None):
        super().__init__("Frame detail", parent)
        self.summary = QLabel()
        self.summary.setObjectName("Muted")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Byte", "Hex", "Decimal", "Binary"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.table)
        self.setMaximumHeight(260)
        self.clear()

    def clear(self):
        self.table.setRowCount(0)
        self.summary.setText("Click a row in the Frames table to see its bytes.")

    def show_frame(self, header, row):
        """header = column names of the frames table, row = values of one frame."""
        def value(names):
            col = find_column(header, names)
            return row[col] if col is not None and col < len(row) else "-"

        data = split_bytes(value(DATA_NAMES)) if value(DATA_NAMES) != "-" else []
        self.summary.setText(
            f"ID {value(ID_NAMES)}   |   length {value(DLC_NAMES)}   |   "
            f"time {value(TIME_NAMES)}   |   {len(data)} data bytes")

        self.table.setRowCount(len(data))
        for i, text in enumerate(data):
            try:
                number = int(text, 16)
                cells = [str(i), f"0x{number:02X}", str(number), f"{number:08b}"]
            except ValueError:
                cells = [str(i), text, "-", "-"]       # not a valid hex byte
            for c, cell in enumerate(cells):
                self.table.setItem(i, c, QTableWidgetItem(cell))