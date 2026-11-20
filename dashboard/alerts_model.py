from datetime import datetime
from PyQt5.QtCore import QAbstractTableModel, Qt, QModelIndex
from PyQt5.QtGui import QColor


class AlertsModel(QAbstractTableModel):
    HEADERS = ["ID", "Time", "Attack score"]
    MAX_ROWS = 500  # keeps the table fast during long live runs

    def __init__(self):
        super().__init__()
        self.rows = []  # each row: (can_id_hex, timestamp, score), newest first

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        can_id, ts, score = self.rows[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return can_id
            if col == 1:
                return datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
            if col == 2:
                return f"{score:.2f}"

        if role == Qt.ForegroundRole and col == 2:
            if score >= 0.9:
                return QColor("#e5484d")   # high
            if score >= 0.7:
                return QColor("#f5a623")   # medium

        if role == Qt.TextAlignmentRole and col == 2:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def add_alert(self, can_id_hex, timestamp, score):
        # insert at the top so the newest alert is always visible
        self.beginInsertRows(QModelIndex(), 0, 0)
        self.rows.insert(0, (can_id_hex, float(timestamp), float(score)))
        self.endInsertRows()

        if len(self.rows) > self.MAX_ROWS:
            last = len(self.rows) - 1
            self.beginRemoveRows(QModelIndex(), last, last)
            self.rows.pop()
            self.endRemoveRows()