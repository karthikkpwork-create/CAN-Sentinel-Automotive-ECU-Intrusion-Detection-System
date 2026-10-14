import os
import threading
import unittest

from src.simulator.attack_traffic_simulator import (
    ATTACK_INJECTION,
    ATTACK_MISSING_MESSAGE,
    ATTACK_MIXED,
    ATTACK_NONE,
    ATTACK_PAYLOAD_TAMPERING,
    ATTACK_UNKNOWN_ID,
    run_attack_simulation,
)
from src.utils.config import load_config

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "config", "config.example.json")


class AttackSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config(EXAMPLE)

    def test_attack_none_produces_only_normal_labels(self):
        rows = []
        stats = run_attack_simulation(
            cfg=self.cfg,
            attack_mode=ATTACK_NONE,
            stop=threading.Event(),
            sender=None,
            on_record=rows.append,
            dry_run=True,
        )
        self.assertGreater(len(rows), 0)
        self.assertEqual(stats.attack_count, 0)
        self.assertEqual(stats.normal_count, len(rows))
        for r in rows:
            self.assertEqual(r["label"], 0)
            self.assertEqual(r["attack_type"], "normal")

    def test_injection_attack_generates_high_rate_burst(self):
        rows = []
        stats = run_attack_simulation(
            cfg=self.cfg,
            attack_mode=ATTACK_INJECTION,
            stop=threading.Event(),
            sender=None,
            on_record=rows.append,
            dry_run=True,
            target_id=0x100,
            attack_start=2.0,
            attack_duration=3.0,
            injection_interval_ms=5.0,
        )
        self.assertGreater(stats.attack_count, 0)
        self.assertIn(ATTACK_INJECTION, stats.per_attack_type)
        inj_rows = [r for r in rows if r["attack_type"] == ATTACK_INJECTION]
        self.assertGreaterEqual(len(inj_rows), 500)
        for r in inj_rows:
            self.assertEqual(r["label"], 1)
            self.assertEqual(r["can_id"], 0x100)

    def test_unknown_id_attack(self):
        rows = []
        unknown_can_id = 0x7FF
        stats = run_attack_simulation(
            cfg=self.cfg,
            attack_mode=ATTACK_UNKNOWN_ID,
            stop=threading.Event(),
            sender=None,
            on_record=rows.append,
            dry_run=True,
            unknown_id=unknown_can_id,
            attack_start=2.0,
            attack_duration=2.0,
        )
        self.assertGreater(stats.attack_count, 0)
        unk_rows = [r for r in rows if r["can_id"] == unknown_can_id]
        self.assertGreater(len(unk_rows), 0)
        for r in unk_rows:
            self.assertEqual(r["label"], 1)
            self.assertEqual(r["attack_type"], ATTACK_UNKNOWN_ID)

    def test_payload_tampering(self):
        rows = []
        stats = run_attack_simulation(
            cfg=self.cfg,
            attack_mode=ATTACK_PAYLOAD_TAMPERING,
            stop=threading.Event(),
            sender=None,
            on_record=rows.append,
            dry_run=True,
            target_id=0x100,
            attack_start=2.0,
            attack_duration=2.0,
        )
        self.assertGreater(stats.attack_count, 0)
        tamper_rows = [r for r in rows if r["attack_type"] == ATTACK_PAYLOAD_TAMPERING]
        self.assertGreater(len(tamper_rows), 0)
        for r in tamper_rows:
            self.assertEqual(r["label"], 1)
            self.assertEqual(r["can_id"], 0x100)

    def test_missing_message_suppression(self):
        rows = []
        stats = run_attack_simulation(
            cfg=self.cfg,
            attack_mode=ATTACK_MISSING_MESSAGE,
            stop=threading.Event(),
            sender=None,
            on_record=rows.append,
            dry_run=True,
            target_id=0x100,
            attack_start=2.0,
            attack_duration=3.0,
        )
        self.assertGreater(stats.suppressed, 0)

    def test_reproducibility(self):
        rows1, rows2 = [], []
        run_attack_simulation(
            cfg=self.cfg,
            attack_mode=ATTACK_MIXED,
            stop=threading.Event(),
            sender=None,
            on_record=rows1.append,
            dry_run=True,
        )
        run_attack_simulation(
            cfg=self.cfg,
            attack_mode=ATTACK_MIXED,
            stop=threading.Event(),
            sender=None,
            on_record=rows2.append,
            dry_run=True,
        )
        self.assertEqual(len(rows1), len(rows2))
        self.assertEqual([r["payload_hex"] for r in rows1], [r["payload_hex"] for r in rows2])


if __name__ == "__main__":
    unittest.main()
