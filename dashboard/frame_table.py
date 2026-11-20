
import csv
import sys

from PyQt5.QtCore import Qt, QAbstractTableModel
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableView, QPushButton,
    QLabel, QVBoxLayout, QWidget, QFileDialog, QHeaderView,
)


class CsvTableModel(QAbstractTableModel):
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
        with open(path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            rows = []
            for row in reader:
                row = row + [""] * (len(header) - len(row))
                rows.append(row[:len(header)])
        self.beginResetModel()
        self.header = header
        self.rows = rows
        self.endResetModel()


class FrameTableWindow(QMainWindow):
    def __init__(self, csv_path=None):
        super().__init__()
        self.setWindowTitle("CAN-Sentinel - Frame Table")
        self.resize(900, 500)

        self.model = CsvTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.status = QLabel("No file loaded")
        open_button = QPushButton("Open CSV...")
        open_button.clicked.connect(self.choose_file)

        layout = QVBoxLayout()
        layout.addWidget(open_button)
        layout.addWidget(self.table)
        layout.addWidget(self.status)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        if csv_path:
            self.load(csv_path)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV", "", "CSV files (*.csv)")
        if path:
            self.load(path)

    def load(self, path):
        try:
            self.model.load_csv(path)
            self.status.setText(f"{path}  |  {self.model.rowCount()} frames")
        except Exception as e:
            self.status.setText(f"Could not load file: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = sys.argv[1] if len(sys.argv) > 1 else None
    window = FrameTableWindow(path)
    window.show()
    sys.exit(app.exec_())
