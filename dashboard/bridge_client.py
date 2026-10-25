import json
import socket

from PyQt5.QtCore import QThread, pyqtSignal


class BridgeClient(QThread):
    """Reads CAN frames (one JSON object per line) from the vcan0 bridge."""

    frame_received = pyqtSignal(dict)
    status_changed = pyqtSignal(str)

    def __init__(self, host="127.0.0.1", port=8765, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self._running = True

    def run(self):
        while self._running:
            sock = None
            try:
                self.status_changed.emit("Connecting...")
                sock = socket.create_connection((self.host, self.port), timeout=3)
                sock.settimeout(1.0)
                self.status_changed.emit("Connected")
                buf = b""
                while self._running:
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break  # bridge closed the connection
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if not line.strip():
                            continue
                        try:
                            self.frame_received.emit(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            except OSError:
                pass
            finally:
                if sock:
                    sock.close()
            if self._running:
                self.status_changed.emit("Disconnected - retrying")
                self.msleep(2000)

    def stop(self):
        self._running = False
        self.wait(3000)