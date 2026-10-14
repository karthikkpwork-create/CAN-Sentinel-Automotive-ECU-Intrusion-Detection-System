import sys
from PyQt5.QtWidgets import QApplication, QMainWindow


class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAN-Sentinel Dashboard")
        self.resize(1000, 600)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Dashboard()
    win.show()
    sys.exit(app.exec_())
