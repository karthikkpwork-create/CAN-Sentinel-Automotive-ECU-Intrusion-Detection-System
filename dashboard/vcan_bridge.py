import json
import socket
import can
from collections import defaultdict

HOST = "0.0.0.0"
PORT = 8765
ALERT_THRESHOLD = 0.7


class IntervalScorer:
    def __init__(self, warmup=50):
        self.stats = defaultdict(lambda: [0, 0.0, 0.0])
        self.warmup = warmup

    def score(self, can_id, interval):
        n, mean, m2 = self.stats[can_id]
        std = (m2 / n) ** 0.5 if n > 1 else 0.0
        score = 0.0
        if n >= self.warmup and std > 0:
            z = abs(interval - mean) / std
            score = min(1.0, z / 6.0)

        n += 1
        delta = interval - mean
        mean += delta / n
        m2 += delta * (interval - mean)
        self.stats[can_id] = [n, mean, m2]
        return score


def send(conn, message):
    payload = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
    conn.sendall(payload)
    print(message)


def main():
    bus = can.Bus(interface="socketcan", channel="vcan0")
    scorer = IntervalScorer()
    last_timestamp_by_can_id = {}

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)

    print(f"CAN bridge listening on port {PORT}")
    print("Waiting for the Windows dashboard to connect...")

    try:
        while True:
            conn, address = server.accept()
            print(f"Dashboard connected: {address}")

            with conn:
                while True:
                    msg = bus.recv()
                    if msg is None:
                        continue

                    timestamp = float(msg.timestamp)
                    can_id_hex = hex(msg.arbitration_id)
                    previous_timestamp = last_timestamp_by_can_id.get(can_id_hex)
                    interval_s = (
                        max(0.0, timestamp - previous_timestamp)
                        if previous_timestamp is not None
                        else 0.0
                    )
                    last_timestamp_by_can_id[can_id_hex] = timestamp
                    score = scorer.score(can_id_hex, interval_s)

                    frame = {
                        "timestamp": timestamp,
                        "can_id": hex(msg.arbitration_id),
                        "can_id_hex": can_id_hex,
                        "interval_s": interval_s,
                        "dlc": msg.dlc,
                        "data": msg.data.hex(" ").upper(),
                        "extended": msg.is_extended_id,
                    }

                    try:
                        send(conn, frame)
                        if score >= ALERT_THRESHOLD:
                            send(conn, {
                                "type": "alert",
                                "can_id_hex": can_id_hex,
                                "timestamp": timestamp,
                                "score": round(score, 3),
                            })
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        print("Dashboard disconnected.")
                        break

    except KeyboardInterrupt:
        print("\nStopping CAN bridge.")
    finally:
        server.close()
        bus.shutdown()

if __name__ == "__main__":
    main()
