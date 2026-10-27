import sys
from PyQt5.QtCore import QCoreApplication, QTimer
from bridge_client import BridgeClient

app = QCoreApplication(sys.argv)
client = BridgeClient()
client.status_changed.connect(lambda s: print("Status:", s))
client.frame_received.connect(lambda f: print("Frame:", f))
client.start()
QTimer.singleShot(60000, app.quit)  # stops after 60 seconds
app.exec_()
client.stop()