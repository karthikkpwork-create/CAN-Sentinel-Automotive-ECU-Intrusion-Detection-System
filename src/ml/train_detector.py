
import argparse
import csv
import json
import math
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest


FEATURES = [
    "frames_per_second",
    "unique_id_count",
    "iat_mean",
    "iat_std",
    "payload_change_rate",
]


def load_features(path):
    """Load and validate the numerical feature columns in a CSV."""
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(f"{path}: CSV has no header.")

        missing = [name for name in FEATURES if name not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path}: missing required columns: {missing}")

        rows = list(reader)

    if not rows:
        raise ValueError(f"{path}: CSV has no data rows.")

    values = []
    for row_number, row in enumerate(rows, start=2):
        converted = []
        for name in FEATURES:
            raw = row.get(name, "")
            try:
                value = float(raw)
            except (TypeError, ValueError):
                raise ValueError(
                    f"{path}, row {row_number}: invalid {name}={raw!r}"
                )

            if not math.isfinite(value):
                raise ValueError(
                    f"{path}, row {row_number}: {name} is not finite"
                )
            converted.append(value)

        if converted[0] < 0 or converted[1] < 0:
            raise ValueError(
                f"{path}, row {row_number}: rate and ID count cannot be negative"
            )

        if not 0 <= converted[4] <= 1:
            raise ValueError(
                f"{path}, row {row_number}: payload_change_rate must be 0 to 1"
            )

        values.append(converted)

    return rows, np.asarray(values, dtype=float)


def write_predictions(path, rows, anomaly_scores, threshold):
    """Save scores and threshold-based predictions."""
    output_columns = list(rows[0].keys()) + [
        "anomaly_score",
        "threshold",
        "prediction",
    ]

    with Path(path).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=output_columns)
        writer.writeheader()

        for row, score in zip(rows, anomaly_scores):
            result = dict(row)
            result["anomaly_score"] = f"{score:.10f}"
            result["threshold"] = f"{threshold:.10f}"
            result["prediction"] = (
                "ANOMALY" if score > threshold else "NORMAL"
            )
            writer.writerow(result)


def main():
    parser = argparse.ArgumentParser(
        description="Train CAN-Sentinel's Isolation Forest detector."
    )
    parser.add_argument("--train", required=True, help="Normal training features CSV")
    parser.add_argument("--validation", required=True, help="Normal validation features CSV")
    parser.add_argument("--test", help="Separate test features CSV, optionally labelled")
    parser.add_argument("--output-dir", default="models", help="Output directory")
    parser.add_argument("--contamination", type=float, default=0.01)
    parser.add_argument("--threshold-quantile", type=float, default=0.99)
    args = parser.parse_args()

    if not 0 < args.contamination <= 0.5:
        parser.error("--contamination must be greater than 0 and at most 0.5")

    if not 0 < args.threshold_quantile < 1:
        parser.error("--threshold-quantile must be between 0 and 1")

    # Both input files must contain normal-only windows.
    _, X_train = load_features(args.train)
    _, X_validation = load_features(args.validation)

    if len(X_train) < 10:
        raise ValueError("Use at least 10 training windows for this prototype.")
    if len(X_validation) < 5:
        raise ValueError("Use at least 5 normal validation windows.")

    model = IsolationForest(
        n_estimators=200,
        contamination=args.contamination,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train)

    # Higher values mean more anomalous in our output convention.
    validation_scores = -model.score_samples(X_validation)

    # Threshold is selected from normal validation data, not the test set.
    threshold = float(
        np.quantile(validation_scores, args.threshold_quantile)
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / "can_sentinel_isolation_forest.joblib"
    config_path = output_dir / "detector_config.json"

    joblib.dump(model, model_path)

    config = {
        "features": FEATURES,
        "threshold": threshold,
        "threshold_quantile": args.threshold_quantile,
        "contamination_parameter": args.contamination,
        "n_estimators": 200,
        "random_state": 42,
        "training_rows": len(X_train),
        "validation_rows": len(X_validation),
        "sklearn_version": sklearn.__version__,
        "score_definition": "anomaly_score = -IsolationForest.score_samples(X)",
        "alert_rule": "ANOMALY if anomaly_score > threshold, otherwise NORMAL",
    }

    config_path.write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )

    print(f"Training windows: {len(X_train)}")
    print(f"Validation windows: {len(X_validation)}")
    print(f"Selected threshold: {threshold:.10f}")
    print(f"Saved model: {model_path}")
    print(f"Saved config: {config_path}")

    if args.test:
        test_rows, X_test = load_features(args.test)
        test_scores = -model.score_samples(X_test)

        predictions_path = output_dir / "test_predictions.csv"
        write_predictions(
            predictions_path, test_rows, test_scores, threshold
        )
        print(f"Test windows: {len(test_rows)}")
        print(f"Saved predictions: {predictions_path}")


if __name__ == "__main__":
    main()
