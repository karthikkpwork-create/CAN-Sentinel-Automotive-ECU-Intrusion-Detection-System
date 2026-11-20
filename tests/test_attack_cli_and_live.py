import os
import tempfile
import threading
import unittest

from src.simulator.attack_traffic_simulator import (
    ATTACK_INJECTION,
    ATTACK_MIXED,
    main,
    run_attack_simulation,
)
from src.utils.config import load_config

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "config", "config.example.json")


class FakeSender:
    """Stands in for SocketCanSender so the LIVE code path runs without CAN support."""

    def __init__(self, fail_calls=()):
        self.sent = []
        self.fail_calls = set(fail_calls)  # 0-based call numbers that fail
        self.calls = 0

    def send(self, can_id, payload):
        n = self.calls
        self.calls += 1
        if n in self.fail_calls:
            raise OSError(105, "No buffer space available")
        self.sent.append((can_id, bytes(payload)))


class LivePathTests(unittest.TestCase):
    def setUp(self):
        import dataclasses
        self.cfg = dataclasses.replace(load_config(EXAMPLE), runtime_seconds=1.0, rate_scale=20.0)

    def test_live_mode_transmits_every_generated_frame(self):
        sender, rows = FakeSender(), []
        stats = run_attack_simulation(
            cfg=self.cfg, attack_mode=ATTACK_INJECTION, stop=threading.Event(), sender=sender,
            on_record=rows.append, dry_run=False, attack_start=0.2, attack_duration=0.4,
        )
        self.assertEqual(stats.transmitted, stats.generated)
        self.assertEqual(len(sender.sent), len(rows))
        self.assertTrue(all(r["status"] == "transmitted" for r in rows))
        self.assertGreater(stats.attack_count, 0)
        for (cid, payload), r in zip(sender.sent, rows):
            self.assertEqual(cid, r["can_id"])
            self.assertEqual(payload.hex().upper(), r["payload_hex"])

    def test_live_mode_requires_sender(self):
        with self.assertRaises(RuntimeError):
            run_attack_simulation(cfg=self.cfg, attack_mode=ATTACK_MIXED, stop=threading.Event(),
                                  sender=None, on_record=lambda r: None, dry_run=False)

    def test_send_failures_are_recorded_not_fatal(self):
        sender, rows = FakeSender(fail_calls={3, 4, 5}), []
        stats = run_attack_simulation(
            cfg=self.cfg, attack_mode=ATTACK_INJECTION, stop=threading.Event(), sender=sender,
            on_record=rows.append, dry_run=False, attack_start=0.2, attack_duration=0.3,
        )
        self.assertEqual(stats.failed, 3)
        self.assertEqual(stats.transmitted, stats.generated - 3)
        self.assertEqual(sum(r["status"].startswith("failed:") for r in rows), 3)

    def test_persistent_send_failure_aborts_after_50(self):
        sender = FakeSender(fail_calls=range(10_000))
        with self.assertRaises(RuntimeError):
            run_attack_simulation(cfg=self.cfg, attack_mode=ATTACK_INJECTION, stop=threading.Event(),
                                  sender=sender, on_record=lambda r: None, dry_run=False,
                                  attack_start=0.0, attack_duration=0.5)

    def test_stop_event_ends_run_early(self):
        stop = threading.Event()
        stop.set()
        stats = run_attack_simulation(cfg=self.cfg, attack_mode=ATTACK_MIXED, stop=stop, sender=FakeSender(),
                                      on_record=lambda r: None, dry_run=False)
        self.assertTrue(stats.interrupted)
        self.assertEqual(stats.generated, 0)


class CliValidationTests(unittest.TestCase):
    def run_cli(self, *extra):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "o.csv")
            code = main(["--config", EXAMPLE, "--dry-run", "--output", out, "--log-level", "ERROR", *extra])
            files = sorted(os.listdir(d))
        return code, files

    def test_valid_run_writes_dataset_and_suppressed_file(self):
        code, files = self.run_cli("--attack", "mixed", "--duration", "20")
        self.assertEqual(code, 0)
        self.assertEqual(files, ["o.csv", "o_suppressed.csv"])

    def test_attack_after_end_of_run_is_rejected(self):
        self.assertEqual(self.run_cli("--attack", "injection", "--duration", "3")[0], 2)

    def test_unconfigured_target_id_is_rejected(self):
        self.assertEqual(self.run_cli("--attack", "missing_message", "--target-id", "0x555", "--duration", "30")[0], 2)

    def test_out_of_range_id_is_rejected(self):
        self.assertEqual(self.run_cli("--attack", "unknown_id", "--unknown-id", "0x800", "--duration", "30")[0], 2)

    def test_bad_interval_is_rejected(self):
        self.assertEqual(self.run_cli("--attack", "injection", "--injection-interval-ms", "0", "--duration", "30")[0], 2)

    def test_same_seed_gives_identical_output(self):
        outs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as d:
                out = os.path.join(d, "o.csv")
                main(["--config", EXAMPLE, "--dry-run", "--attack", "mixed", "--duration", "20", "--seed", "3",
                      "--output", out, "--log-level", "ERROR"])
                outs.append(open(out, "rb").read())
        self.assertEqual(outs[0], outs[1])


if __name__ == "__main__":
    unittest.main()
