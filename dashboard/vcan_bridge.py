import json
import socket
import can

HOST = "0.0.0.0"
PORT = 8765

def main():
    bus = can.Bus(interface="socketcan", channel="vcan0")

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

                    frame = {
                        "timestamp": msg.timestamp,
                        "can_id": hex(msg.arbitration_id),
                        "dlc": msg.dlc,
                        "data": msg.data.hex(" ").upper(),
                        "extended": msg.is_extended_id,
                    }

                    payload = (
                        json.dumps(frame, separators=(",", ":")) + "\n"
                    ).encode("utf-8")

                    try:
                        conn.sendall(payload)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        print("Dashboard disconnected.")
                        break

                    print(frame)

    except KeyboardInterrupt:
        print("\nStopping CAN bridge.")
    finally:
        server.close()
        bus.shutdown()

if __name__ == "__main__":
    main()
