"""Tests for src/detector/detector.py and scripts/run_demo.sh (Person A).

No CAN hardware, vcan0 or dashboard is needed. Integration tests use the
repo's own dry-run simulator with fixed seeds and write only to temp folders.
"""
import contextlib
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.detector import detector as det

ROOT = Path(__file__).resolve().parent.parent
RUN_DEMO = ROOT / "scripts" / "run_demo.sh"


def normal_features(n=60, seed=0):
    """Small synthetic feature table shaped like the real extractor output."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "window_start_s": 1_700_000_000.0 + np.arange(n),
        "frame_count": rng.integers(17, 21, n),
        "frames_per_second": 0.0,
        "unique_id_count": rng.integers(3, 5, n),
        "iat_mean": rng.normal(0.22, 0.02, n),
        "iat_std": rng.normal(0.22, 0.03, n),
        "payload_change_rate": 1.0,
        "payload_comparisons": rng.integers(13, 17, n),
    }).assign(frames_per_second=lambda d: d["frame_count"].astype(float))


def tiny_bundle(seed=42, threshold=0.0):
    feats = normal_features()
    X, _ = det.prepare_features(feats, det.FEATURE_COLUMNS, det.BLANK_FILL_VALUE)
    model = IsolationForest(n_estimators=50, contamination=0.05, random_state=seed).fit(X)
    return det.ModelBundle(
        model=model, feature_columns=list(det.FEATURE_COLUMNS), threshold=threshold,
        window_seconds=1.0, fill_value=det.BLANK_FILL_VALUE,
        id_stats={"0x100": {"mean": 10.0, "std": 1.0}, "0x200": {"mean": 5.0, "std": 0.5}},
        seed=seed, contamination=0.05)


class PrepareFeaturesTests(unittest.TestCase):
    def test_empty_input_is_rejected(self):
        with self.assertRaisesRegex(det.DetectorError, "empty"):
            det.prepare_features(pd.DataFrame(), det.FEATURE_COLUMNS, 0.0)

    def test_missing_column_is_named(self):
        feats = normal_features().drop(columns=["iat_std"])
        with self.assertRaisesRegex(det.DetectorError, "iat_std"):
            det.prepare_features(feats, det.FEATURE_COLUMNS, 0.0)

    def test_extra_columns_ignored_and_order_follows_model(self):
        feats = normal_features()
        shuffled = feats[list(reversed(feats.columns))].assign(extra_note="x")
        a, _ = det.prepare_features(feats, det.FEATURE_COLUMNS, 0.0)
        b, _ = det.prepare_features(shuffled, det.FEATURE_COLUMNS, 0.0)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(a.shape[1], len(det.FEATURE_COLUMNS))

    def test_non_numeric_value_is_rejected(self):
        feats = normal_features().astype({"iat_mean": object})
        feats.loc[3, "iat_mean"] = "abc"
        with self.assertRaisesRegex(det.DetectorError, "non-numeric"):
            det.prepare_features(feats, det.FEATURE_COLUMNS, 0.0)

    def test_infinite_value_is_rejected(self):
        feats = normal_features().astype({"frame_count": float})
        feats.loc[0, "frame_count"] = np.inf
        with self.assertRaisesRegex(det.DetectorError, "infinite"):
            det.prepare_features(feats, det.FEATURE_COLUMNS, 0.0)

    def test_blank_cells_are_filled_and_counted(self):
        feats = normal_features()
        feats.loc[2, ["iat_mean", "iat_std"]] = np.nan
        values, filled = det.prepare_features(feats, det.FEATURE_COLUMNS, 0.0)
        self.assertEqual(int(filled[2]), 2)
        self.assertEqual(int(filled.sum()), 2)
        self.assertFalse(np.isnan(values).any())
        self.assertEqual(values[2, det.FEATURE_COLUMNS.index("iat_mean")], 0.0)


class ModelFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "m.joblib"

    def test_missing_file(self):
        with self.assertRaisesRegex(det.DetectorError, "not found"):
            det.load_bundle(self.path)

    def test_corrupted_file(self):
        self.path.write_bytes(b"this is not a joblib file")
        with self.assertRaisesRegex(det.DetectorError, "unreadable or corrupted"):
            det.load_bundle(self.path)

    def test_wrong_object_type(self):
        joblib.dump([1, 2, 3], self.path)
        with self.assertRaisesRegex(det.DetectorError, "expected a dict"):
            det.load_bundle(self.path)

    def test_missing_keys(self):
        joblib.dump({"schema_version": 1}, self.path)
        with self.assertRaisesRegex(det.DetectorError, "missing keys"):
            det.load_bundle(self.path)

    def test_unsupported_schema_version(self):
        det.save_bundle(tiny_bundle(), self.path)
        raw = joblib.load(self.path)
        raw["schema_version"] = 99
        joblib.dump(raw, self.path)
        with self.assertRaisesRegex(det.DetectorError, "schema_version"):
            det.load_bundle(self.path)

    def test_feature_count_mismatch(self):
        det.save_bundle(tiny_bundle(), self.path)
        raw = joblib.load(self.path)
        raw["feature_columns"] = raw["feature_columns"][:3]
        joblib.dump(raw, self.path)
        with self.assertRaisesRegex(det.DetectorError, "expects 7 features"):
            det.load_bundle(self.path)

    def test_round_trip_keeps_scores(self):
        bundle = tiny_bundle()
        det.save_bundle(bundle, self.path)
        loaded = det.load_bundle(self.path)
        feats = normal_features(10, seed=5)
        a = det.score_features(feats, bundle)["anomaly_score"].to_numpy()
        b = det.score_features(feats, loaded)["anomaly_score"].to_numpy()
        np.testing.assert_allclose(a, b)


class ScoringTests(unittest.TestCase):
    def test_normal_vs_extreme_labels_not_reversed(self):
        bundle = tiny_bundle()
        feats = normal_features(5, seed=9)
        extreme = feats.iloc[[0]].copy()
        extreme["frame_count"] = 1000
        extreme["frames_per_second"] = 1000.0
        extreme["iat_mean"] = 0.001
        extreme["iat_std"] = 0.0
        results = det.score_features(pd.concat([feats.iloc[[1]], extreme], ignore_index=True), bundle)
        typical, flood = results.iloc[0], results.iloc[1]
        self.assertEqual(typical["status"], "normal")
        self.assertEqual(typical["prediction"], 1)
        self.assertEqual(flood["status"], "anomalous")
        self.assertEqual(flood["prediction"], -1)
        self.assertLess(flood["anomaly_score"], typical["anomaly_score"])
        self.assertLess(flood["anomaly_score"], 0.0)

    def test_threshold_override_changes_status(self):
        bundle = tiny_bundle()
        feats = normal_features(20, seed=3)
        strict = det.score_features(feats, bundle, threshold=10.0)
        lenient = det.score_features(feats, bundle, threshold=-10.0)
        self.assertTrue((strict["status"] == "anomalous").all())
        self.assertTrue((lenient["status"] == "normal").all())

    def test_output_schema(self):
        results = det.score_features(normal_features(8), tiny_bundle())
        self.assertEqual(list(results.columns), det.RESULT_COLUMNS)
        self.assertEqual(len(results), 8)
        self.assertTrue(set(results["status"]) <= {"normal", "anomalous"})

    def test_same_seed_gives_same_scores(self):
        feats = normal_features(15, seed=4)
        a = det.score_features(feats, tiny_bundle(seed=7))["anomaly_score"].to_numpy()
        b = det.score_features(feats, tiny_bundle(seed=7))["anomaly_score"].to_numpy()
        np.testing.assert_array_equal(a, b)

    def test_window_column_required(self):
        with self.assertRaisesRegex(det.DetectorError, "window_start_s"):
            det.score_features(normal_features().drop(columns=["window_start_s"]), tiny_bundle())


class SuspectTests(unittest.TestCase):
    STATS = {"0x100": {"mean": 10.0, "std": 1.0}, "0x200": {"mean": 5.0, "std": 0.0}}

    def test_flood_names_the_flooded_id(self):
        cid, reason, z = det.find_suspect({"0x100": 500, "0x200": 5}, self.STATS)
        self.assertEqual((cid, reason), ("0x100", "count_zscore"))
        self.assertGreater(z, 100)

    def test_unknown_id_wins(self):
        cid, reason, _ = det.find_suspect({"0x100": 10, "0x200": 5, "0x7FF": 3}, self.STATS)
        self.assertEqual((cid, reason), ("0x7FF", "id_not_in_training_baseline"))

    def test_silent_id_is_found_by_negative_z(self):
        cid, reason, z = det.find_suspect({"0x200": 5}, self.STATS)
        self.assertEqual((cid, reason), ("0x100", "count_zscore"))
        self.assertLess(z, 0)

    def test_no_deviation_gives_no_guess(self):
        cid, reason, _ = det.find_suspect({"0x100": 10, "0x200": 5}, self.STATS)
        self.assertEqual((cid, reason), ("", "no_count_deviation"))

    def test_zero_std_uses_floor_not_division_by_zero(self):
        _, _, z = det.find_suspect({"0x100": 10, "0x200": 7}, self.STATS)
        self.assertTrue(np.isfinite(z))

    def test_can_id_forms_are_normalised(self):
        self.assertEqual(det.normalize_can_id("0x7ff"), "0x7FF")
        self.assertEqual(det.normalize_can_id("256"), "0x100")
        with self.assertRaises(ValueError):
            det.normalize_can_id("zz")


class PipelineTests(unittest.TestCase):
    """Real simulator -> real extractor -> real model -> detector."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        for name, seed in (("train", 1), ("test", 2)):
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "generate_datasets.py"),
                 "--config", str(ROOT / "config" / "config.example.json"),
                 "--output-dir", str(cls.dir / name), "--duration", "60", "--seed", str(seed)],
                cwd=ROOT, check=True, capture_output=True)
        cls.bundle = det.train_bundle(cls.dir / "train" / "normal_traffic.csv", seed=42)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_bundle_matches_extractor_columns(self):
        self.assertEqual(self.bundle.feature_columns, list(det.FEATURE_COLUMNS))
        self.assertEqual(set(self.bundle.id_stats), {"0x100", "0x200", "0x300", "0x400"})

    def test_normal_traffic_has_few_false_alarms(self):
        res = det.detect_csv(self.dir / "test" / "normal_traffic.csv", self.bundle)
        self.assertLess((res["status"] == "anomalous").mean(), 0.15)

    def test_injection_flood_is_flagged_with_correct_id(self):
        path = self.dir / "test" / "attack_injection.csv"
        res = det.detect_csv(path, self.bundle)
        summary = det.summarize_against_labels(res, path, 1.0)
        self.assertEqual(summary["fn"], 0)
        named = res[res["suspect_reason"] == "count_zscore"]
        self.assertGreater(len(named), 0)
        self.assertTrue((named["suspect_can_id"] == "0x100").all())

    def test_unknown_id_attack_names_unknown_id(self):
        res = det.detect_csv(self.dir / "test" / "attack_unknown_id.csv", self.bundle)
        named = res[res["suspect_reason"] == "id_not_in_training_baseline"]
        self.assertGreater(len(named), 0)
        self.assertTrue((named["suspect_can_id"] == "0x7FF").all())

    def test_normal_windows_carry_no_suspect(self):
        res = det.detect_csv(self.dir / "test" / "attack_injection.csv", self.bundle)
        normal = res[res["status"] == "normal"]
        self.assertTrue((normal["suspect_can_id"].fillna("") == "").all())

    def test_training_refuses_attack_data(self):
        with self.assertRaisesRegex(det.DetectorError, "normal traffic only"):
            det.train_bundle(self.dir / "train" / "attack_injection.csv")

    def test_training_needs_enough_windows(self):
        short = self.dir / "short.csv"
        lines = (self.dir / "train" / "normal_traffic.csv").read_text().splitlines()[:40]
        short.write_text("\n".join(lines) + "\n")
        with self.assertRaisesRegex(det.DetectorError, "need at least"):
            det.train_bundle(short)

    def test_missing_and_bad_csv(self):
        with self.assertRaisesRegex(det.DetectorError, "not found"):
            det.detect_csv(self.dir / "nope.csv", self.bundle)
        bad = self.dir / "bad.csv"
        bad.write_text("a,b\n1,2\n")
        with self.assertRaises(det.DetectorError):
            det.detect_csv(bad, self.bundle)
        empty = self.dir / "empty.csv"
        empty.write_text("")
        with self.assertRaises(det.DetectorError):
            det.detect_csv(empty, self.bundle)

    def test_cli_train_detect_and_output_file(self):
        model = self.dir / "cli_model.joblib"
        out = self.dir / "cli_results.csv"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = det.main(["train", "--normal-csv", str(self.dir / "train" / "normal_traffic.csv"),
                             "--model", str(model)])
            self.assertEqual(code, 0)
            code = det.main(["detect", "--csv", str(self.dir / "test" / "attack_injection.csv"),
                             "--model", str(model), "--output", str(out), "--check-labels"])
        self.assertEqual(code, 0)
        self.assertIn("Label check", buf.getvalue())
        self.assertEqual(list(pd.read_csv(out).columns), det.RESULT_COLUMNS)

    def test_cli_errors_return_one(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = det.main(["detect", "--csv", str(self.dir / "test" / "normal_traffic.csv"),
                             "--model", str(self.dir / "absent.joblib")])
        self.assertEqual(code, 1)
        self.assertIn("model file not found", err.getvalue())
        with contextlib.redirect_stderr(io.StringIO()) as err2:
            code = det.main(["train", "--normal-csv", str(self.dir / "train" / "normal_traffic.csv"),
                             "--model", str(self.dir / "x.joblib"), "--contamination", "0.9"])
        self.assertEqual(code, 1)
        self.assertIn("contamination", err2.getvalue())


@unittest.skipUnless(shutil.which("bash"), "bash not available")
class RunDemoScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_script(self, *args, python=None):
        env = dict(os.environ)
        if python:
            env["PYTHON"] = python
        return subprocess.run(["bash", str(RUN_DEMO), *args], cwd=self.tmp.name, env=env,
                              capture_output=True, text=True, timeout=300)

    def fake_python(self, body):
        path = Path(self.tmp.name) / "fakepython"
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return str(path)

    def test_help_works_from_another_directory(self):
        res = self.run_script("--help")
        self.assertEqual(res.returncode, 0)
        self.assertIn("offline", res.stdout)

    def test_unknown_argument_exits_2(self):
        res = self.run_script("bogus")
        self.assertEqual(res.returncode, 2)

    def test_bad_option_values(self):
        self.assertNotEqual(self.run_script("offline", "--duration", "abc").returncode, 0)
        self.assertNotEqual(self.run_script("offline", "--model", "/no/such/model").returncode, 0)

    def test_missing_python_executable(self):
        res = self.run_script("offline", python="/no/such/python")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("not found", res.stderr)

    def test_missing_dependencies_explains_venv(self):
        res = self.run_script("offline", python=self.fake_python("exit 1"))
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("python3 -m venv", res.stderr)
        self.assertIn("pip install -r requirements.txt", res.stderr)

    def test_failed_step_fails_the_script(self):
        py = self.fake_python('if [ "$1" = "-c" ]; then exit 0; fi\necho boom >&2\nexit 3')
        res = self.run_script("offline", "--duration", "5", python=py)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("step failed", res.stderr)
        self.assertIn("boom", res.stderr)

    def test_offline_demo_end_to_end(self):
        res = self.run_script("offline", "--duration", "30", python=sys.executable)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("anomalous", res.stdout)
        self.assertIn("suspect ID 0x100", res.stdout)


if __name__ == "__main__":
    unittest.main()
