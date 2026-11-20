import json
import socket
import time

from PyQt5.QtCore import QThread, pyqtSignal


class BridgeClient(QThread):
    """Reads CAN frames (one JSON object per line) from the vcan0 bridge."""

    frame_received = pyqtSignal(dict)
    alert_received = pyqtSignal(dict)
    messages_received = pyqtSignal(list)
    status_changed = pyqtSignal(str)

    BATCH_INTERVAL_SECONDS = 0.05
    MAX_BATCH_SIZE = 100

    def __init__(self, host="127.0.0.1", port=8765, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self._running = True

    def run(self):
        while self._running:
            sock = None
            pending = []
            try:
                self.status_changed.emit("Connecting...")
                sock = socket.create_connection((self.host, self.port), timeout=3)
                sock.settimeout(self.BATCH_INTERVAL_SECONDS)
                self.status_changed.emit("Connected")
                buf = b""
                last_batch_at = time.monotonic()
                while self._running:
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        if pending:
                            self.messages_received.emit(pending)
                            pending = []
                        last_batch_at = time.monotonic()
                        continue
                    if not chunk:
                        break  # bridge closed the connection
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if not line.strip():
                            continue
                        try:
                            message = json.loads(line)
                            if message.get("type") == "alert":
                                self.alert_received.emit(message)
                            else:
                                self.frame_received.emit(message)
                            pending.append(message)
                            if (
                                len(pending) >= self.MAX_BATCH_SIZE
                                or time.monotonic() - last_batch_at
                                >= self.BATCH_INTERVAL_SECONDS
                            ):
                                self.messages_received.emit(pending)
                                pending = []
                                last_batch_at = time.monotonic()
                        except json.JSONDecodeError:
                            pass
            except OSError:
                pass
            finally:
                if pending:
                    self.messages_received.emit(pending)
                if sock:
                    sock.close()
            if self._running:
                self.status_changed.emit("Disconnected - retrying")
                self.msleep(2000)

    def stop(self):
        self._running = False
        self.wait(3000)