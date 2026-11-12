"""Live-mode pipeline test WITHOUT a CAN interface.

An in-process datagram socket pair carries the same 16-byte frames that
SocketCAN would. This checks simulator -> monitor -> CSV -> compare logic and
clean shutdown. It does NOT test SocketCAN or vcan0 itself; that needs a real
Linux CAN-capable kernel (see docs/week1_testing.md).
"""
import csv
import dataclasses
import logging
import os
import socket
import tempfile
import threading
import unittest

from src.capture.can_monitor import monitor
from src.simulator.normal_traffic_simulator import run_simulation
from src.utils.can_frame import pack_frame
from src.utils.compare_logs import _read, compare
from src.utils.config import load_config
from src.utils.dataset import OBSERVED_COLUMNS, SENDER_COLUMNS, CsvSink

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "config", "config.example.json")


class PairSender:
    def __init__(self, sock):
        self._sock = sock

    def send(self, can_id, payload):
        self._sock.send(pack_frame(can_id, payload))


class PipelineTest(unittest.TestCase):
    def test_sender_to_monitor_to_compare(self):
        cfg = dataclasses.replace(load_config(EXAMPLE), runtime_seconds=1.5)
        tx, rx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        log = logging.getLogger("test-pipeline")
        log.addHandler(logging.NullHandler())
        with tempfile.TemporaryDirectory() as tmp:
            sent_csv = os.path.join(tmp, "sent.csv")
            obs_csv = os.path.join(tmp, "obs.csv")
            mon_stop = threading.Event()
            result = {}
            with CsvSink(obs_csv, OBSERVED_COLUMNS) as obs_sink:
                t = threading.Thread(target=lambda: result.update(
                    stats=monitor(rx, mon_stop, "vcan0", cfg.id_lookup(), obs_sink, True, 0, None, log)))
                t.start()
                with CsvSink(sent_csv, SENDER_COLUMNS) as sent_sink:
                    stats = run_simulation(cfg, threading.Event(), PairSender(tx), sent_sink.write, logger=log)
                threading.Event().wait(0.7)  # let the monitor drain
                mon_stop.set()
                t.join(timeout=5)
                self.assertFalse(t.is_alive(), "monitor did not stop cleanly")

            self.assertGreater(stats.transmitted, 0)
            self.assertEqual(stats.transmitted, stats.generated)
            self.assertEqual(result["stats"].data_frames, stats.transmitted)

            totals = compare(_read(sent_csv, "can_id_hex", "payload_hex", "status"),
                             _read(obs_csv, "can_id_hex", "payload_hex", None))["totals"]
            self.assertEqual(totals["missing"], 0)
            self.assertEqual(totals["unexpected"], 0)

            with open(obs_csv, newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), stats.transmitted)
            self.assertEqual(list(rows[0].keys()), OBSERVED_COLUMNS)
        tx.close()
        rx.close()

    def test_monitor_ignores_malformed_data(self):
        tx, rx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        log = logging.getLogger("test-malformed")
        log.addHandler(logging.NullHandler())
        tx.send(b"\x01\x02\x03")                   # wrong size
        tx.send(bytes(72))                          # CAN-FD-sized frame
        tx.send(pack_frame(0x123, b"\xDE\xAD"))     # one valid frame
        stats = monitor(rx, threading.Event(), "vcan0", {}, None, True, 1, 5, log)
        self.assertEqual(stats.invalid, 2)
        self.assertEqual(stats.data_frames, 1)
        tx.close()
        rx.close()


if __name__ == "__main__":
    unittest.main()
