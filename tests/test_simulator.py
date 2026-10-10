import os
import threading
import unittest

from src.simulator.normal_traffic_simulator import run_simulation
from src.simulator.payload import PayloadGenerator
from src.utils.config import load_config

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "config", "config.example.json")


def dry_rows(seed=42, runtime=2.0):
    import dataclasses
    cfg = dataclasses.replace(load_config(EXAMPLE), random_seed=seed, runtime_seconds=runtime)
    rows = []
    stats = run_simulation(cfg, threading.Event(), None, rows.append, dry_run=True)
    return cfg, rows, stats


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config(EXAMPLE)

    def test_same_seed_same_sequence(self):
        for m in self.cfg.messages:
            a = PayloadGenerator(m, 1)
            b = PayloadGenerator(m, 1)
            self.assertEqual([a.next_payload() for _ in range(50)], [b.next_payload() for _ in range(50)])

    def test_different_seed_differs(self):
        m = self.cfg.messages[0]
        a = [PayloadGenerator(m, 1).next_payload() for _ in range(1)]
        ga, gb = PayloadGenerator(m, 1), PayloadGenerator(m, 2)
        self.assertNotEqual([ga.next_payload() for _ in range(50)], [gb.next_payload() for _ in range(50)])

    def test_length_bounds_and_small_steps(self):
        for m in self.cfg.messages:
            g = PayloadGenerator(m, 7)
            prev = None
            for i in range(300):
                p = g.next_payload()
                self.assertEqual(len(p), m.dlc)
                self.assertLessEqual(len(p), 8)
                for s in m.signals:
                    v = int.from_bytes(p[s.start_byte:s.start_byte + s.size], "big")
                    self.assertTrue(s.minimum <= v <= s.maximum)
                    if prev is not None:
                        pv = int.from_bytes(prev[s.start_byte:s.start_byte + s.size], "big")
                        self.assertLessEqual(abs(v - pv), s.max_step)
                if m.counter_byte is not None:
                    self.assertEqual(p[m.counter_byte], i % 256)
                prev = p


class DryRunTests(unittest.TestCase):
    def test_reproducible(self):
        _, a, _ = dry_rows()
        _, b, _ = dry_rows()
        self.assertEqual(a, b)

    def test_seed_changes_output(self):
        _, a, _ = dry_rows(seed=1)
        _, b, _ = dry_rows(seed=2)
        self.assertNotEqual([r["payload_hex"] for r in a], [r["payload_hex"] for r in b])

    def test_counts_match_intervals(self):
        cfg, rows, stats = dry_rows(runtime=10.0)
        self.assertEqual(stats.generated, len(rows))
        self.assertEqual(stats.transmitted, 0)
        for m in cfg.messages:
            n = sum(1 for r in rows if r["can_id"] == m.can_id)
            expected = 10.0 / (m.interval_ms / 1000.0)
            self.assertLessEqual(abs(n - expected), 2, f"{m.name}: {n} vs ~{expected}")

    def test_rows_are_valid_frames(self):
        _, rows, _ = dry_rows()
        for r in rows:
            self.assertLessEqual(r["dlc"], 8)
            self.assertEqual(len(r["payload_hex"]), r["dlc"] * 2)
            self.assertEqual(r["status"], "dry_run")

    def test_stop_event_halts_immediately(self):
        import dataclasses
        cfg = dataclasses.replace(load_config(EXAMPLE), runtime_seconds=100)
        stop = threading.Event()
        stop.set()
        rows = []
        stats = run_simulation(cfg, stop, None, rows.append, dry_run=True)
        self.assertEqual(rows, [])
        self.assertTrue(stats.interrupted)


if __name__ == "__main__":
    unittest.main()
