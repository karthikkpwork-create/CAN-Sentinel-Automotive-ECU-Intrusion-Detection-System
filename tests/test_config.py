import copy
import json
import os
import tempfile
import unittest

from src.utils.config import ConfigError, load_config, parse_config

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "config", "config.example.json")


def base():
    with open(EXAMPLE, encoding="utf-8") as fh:
        return json.load(fh)


class ConfigValidationTests(unittest.TestCase):
    def test_example_config_is_valid(self):
        cfg = load_config(EXAMPLE)
        self.assertEqual(cfg.interface, "vcan0")
        self.assertEqual(len(cfg.messages), 4)
        self.assertEqual(sorted(cfg.id_lookup()), [0x100, 0x200, 0x300, 0x400])

    def _expect_error(self, mutate, fragment):
        raw = copy.deepcopy(base())
        mutate(raw)
        with self.assertRaises(ConfigError) as ctx:
            parse_config(raw)
        self.assertIn(fragment, str(ctx.exception))

    def msg(self, raw):
        return raw["ecus"][0]["messages"][0]

    def test_can_id_out_of_range(self):
        self._expect_error(lambda r: self.msg(r).update(can_id="0x800"), "11-bit")

    def test_can_id_not_a_number(self):
        self._expect_error(lambda r: self.msg(r).update(can_id="hello"), "not a valid number")

    def test_dlc_too_large(self):
        self._expect_error(lambda r: self.msg(r).update(dlc=9), "out of range")

    def test_interval_zero(self):
        self._expect_error(lambda r: self.msg(r).update(interval_ms=0), "interval_ms")

    def test_duplicate_can_id(self):
        self._expect_error(lambda r: r["ecus"][1]["messages"][0].update(can_id="0x100"), "already used")

    def test_signal_does_not_fit_dlc(self):
        def mutate(r):
            self.msg(r)["dlc"] = 2
        self._expect_error(mutate, "dlc")

    def test_overlapping_bytes(self):
        def mutate(r):
            self.msg(r)["signals"][1]["start_byte"] = 1  # collides with 2-byte rpm at 0..1
        self._expect_error(mutate, "used twice")

    def test_physical_interface_rejected(self):
        self._expect_error(lambda r: r.update(interface="can0"), "virtual")

    def test_unknown_key_rejected(self):
        self._expect_error(lambda r: r.update(runtime_secs=5), "unknown setting")

    def test_bad_log_level(self):
        self._expect_error(lambda r: r.update(log_level="LOUD"), "log_level")

    def test_negative_runtime(self):
        self._expect_error(lambda r: r.update(runtime_seconds=-1), "runtime_seconds")

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_config("does/not/exist.json")

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{ not json")
            path = fh.name
        try:
            with self.assertRaises(ConfigError) as ctx:
                load_config(path)
            self.assertIn("not valid JSON", str(ctx.exception))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
