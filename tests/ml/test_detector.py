import csv
import tempfile
import unittest
from pathlib import Path

from src.ml.train_detector import load_features


class TestCanSentinelFeatureInput(unittest.TestCase):
    def write_csv(self, path, rows):
        columns = [
            "frames_per_second",
            "unique_id_count",
            "iat_mean",
            "iat_std",
            "payload_change_rate",
        ]
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def test_valid_feature_row(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "normal.csv"
            self.write_csv(path, [{
                "frames_per_second": 100,
                "unique_id_count": 5,
                "iat_mean": 0.01,
                "iat_std": 0.002,
                "payload_change_rate": 0.25,
            }])

            rows, values = load_features(path)

            self.assertEqual(len(rows), 1)
            self.assertEqual(values.shape, (1, 5))

    def test_invalid_numeric_feature_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.csv"
            self.write_csv(path, [{
                "frames_per_second": "abc",
                "unique_id_count": 5,
                "iat_mean": 0.01,
                "iat_std": 0.002,
                "payload_change_rate": 0.25,
            }])

            with self.assertRaises(ValueError):
                load_features(path)

    def test_optional_feature_blanks_are_zero_filled(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sparse.csv"
            self.write_csv(path, [{
                "frames_per_second": 100,
                "unique_id_count": 5,
                "iat_mean": "",
                "iat_std": "",
                "payload_change_rate": "",
            }])

            _, values = load_features(path)

            self.assertEqual(values.tolist(), [[100, 5, 0, 0, 0]])

    def test_required_feature_blank_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "incomplete.csv"
            self.write_csv(path, [{
                "frames_per_second": "",
                "unique_id_count": 5,
                "iat_mean": 0.01,
                "iat_std": 0.002,
                "payload_change_rate": 0.25,
            }])

            with self.assertRaisesRegex(ValueError, "frames_per_second"):
                load_features(path)

    def test_training_data_requires_labels_when_requested(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "unlabeled.csv"
            self.write_csv(path, [{
                "frames_per_second": 100,
                "unique_id_count": 5,
                "iat_mean": 0.01,
                "iat_std": 0.002,
                "payload_change_rate": 0.25,
            }])

            with self.assertRaisesRegex(ValueError, "label column"):
                load_features(path, require_labels=True)


if __name__ == "__main__":
    unittest.main()