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


if __name__ == "__main__":
    unittest.main()