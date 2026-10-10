import os
import unittest
from collections import Counter

from src.capture.can_monitor import frame_to_row
from src.utils.can_frame import pack_frame, unpack_frame
from src.utils.compare_logs import compare
from src.utils.config import load_config

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "config", "config.example.json")


class FrameToRowTests(unittest.TestCase):
    def setUp(self):
        self.names = load_config(EXAMPLE).id_lookup()

    def test_known_id_and_inter_arrival(self):
        seen = {}
        f = unpack_frame(pack_frame(0x100, bytes.fromhex("0352000000000001")))
        r1 = frame_to_row(f, 100.0, seen, self.names, "vcan0")
        r2 = frame_to_row(f, 100.1, seen, self.names, "vcan0")
        self.assertEqual(r1["can_id_hex"], "0x100")
        self.assertEqual(r1["ecu_name"], "engine_ecu")
        self.assertEqual(r1["payload_hex"], "0352000000000001")
        self.assertEqual(r1["inter_arrival_s"], "")
        self.assertAlmostEqual(float(r2["inter_arrival_s"]), 0.1, places=6)

    def test_unknown_id(self):
        f = unpack_frame(pack_frame(0x555, b"\x01"))
        r = frame_to_row(f, 1.0, {}, self.names, "vcan0")
        self.assertEqual(r["ecu_name"], "unknown")
        self.assertEqual(r["dlc"], 1)


class CompareTests(unittest.TestCase):
    def test_all_matched(self):
        sent = Counter({("0x100", "AA"): 2, ("0x200", "BB"): 1})
        obs = Counter({("0x100", "AA"): 2, ("0x200", "BB"): 1})
        t = compare(sent, obs)["totals"]
        self.assertEqual((t["missing"], t["unexpected"], t["matched"]), (0, 0, 3))

    def test_missing_and_unexpected(self):
        sent = Counter({("0x100", "AA"): 3})
        obs = Counter({("0x100", "AA"): 2, ("0x100", "CC"): 1})
        t = compare(sent, obs)["totals"]
        self.assertEqual((t["missing"], t["unexpected"], t["matched"]), (1, 1, 2))


if __name__ == "__main__":
    unittest.main()
