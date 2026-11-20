
import can
import time
import random

bus = can.Bus(
    interface="socketcan",
    channel="vcan0"
)

def send_message(can_id):
    message = can.Message(
        arbitration_id=can_id,
        data=[random.randint(0, 255) for _ in range(8)],
        is_extended_id=False
    )
    bus.send(message)

try:
    print("CAN-Sentinel automatic sender started")

    # Phase 1: Normal traffic
    print("Normal traffic started")

    end = time.monotonic() + 60

    while time.monotonic() < end:
        send_message(0x100)
        time.sleep(0.5)

    # Phase 2: High-rate abnormal traffic
    print("High-rate traffic started")

    end = time.monotonic() + 10

    while time.monotonic() < end:
        send_message(0x7FF)
        time.sleep(0.01)

    # Phase 3: Normal traffic again
    print("Normal traffic resumed")

    end = time.monotonic() + 110

    while time.monotonic() < end:
        send_message(0x100)
        time.sleep(0.5)

    print("CAN traffic generation completed")

except KeyboardInterrupt:
    print("Sender stopped")

finally:
    bus.shutdown()

