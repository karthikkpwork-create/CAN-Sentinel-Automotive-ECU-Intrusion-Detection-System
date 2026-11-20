import argparse
import csv
import json
import math
from pathlib import Path

import joblib
import numpy as np
import sklearn

from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)


FEATURES = [
    "frames_per_second",
    "unique_id_count",
    "iat_mean",
    "iat_std",
    "payload_change_rate",
]
OPTIONAL_FEATURES = {"iat_mean", "iat_std", "payload_change_rate"}


def load_features(path, require_labels=False):
    """Load, validate and return feature values and optional labels."""
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

        if require_labels and "label" not in reader.fieldnames:
            raise ValueError(f"{path}: required label column is missing.")

        rows = list(reader)

    if not rows:
        raise ValueError(f"{path}: CSV has no data rows.")

    values = []
    labels = []

    for row_number, row in enumerate(rows, start=2):
        converted = []

        for name in FEATURES:
            raw = (row.get(name) or "").strip()
            if name in OPTIONAL_FEATURES and not raw:
                value = 0.0
            else:
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"{path}, row {row_number}: invalid {name}={raw!r}"
                    )

            if not math.isfinite(value):
                raise ValueError(
                    f"{path}, row {row_number}: {name} is not finite."
                )

            if value < 0:
                raise ValueError(
                    f"{path}, row {row_number}: {name} cannot be negative."
                )

            if name == "payload_change_rate" and value > 1:
                raise ValueError(
                    f"{path}, row {row_number}: "
                    "payload_change_rate must be between 0 and 1."
                )

            converted.append(value)

        values.append(converted)

        if require_labels:
            raw_label = row.get("label", "")

            try:
                label = int(raw_label)
            except (TypeError, ValueError):
                raise ValueError(
                    f"{path}, row {row_number}: invalid label={raw_label!r}"
                )

            if label not in (0, 1):
                raise ValueError(
                    f"{path}, row {row_number}: label must be 0 or 1."
                )

            labels.append(label)

    X = np.asarray(values, dtype=float)
    y = np.asarray(labels, dtype=int) if require_labels else None

    if require_labels:
        return rows, X, y
    return rows, X


def validate_normal_only(y, path, description):
    """Reject attack-labelled data in training or validation."""
    if not np.all(y == 0):
        attack_count = int(np.sum(y == 1))

        raise ValueError(
            f"{description} dataset must contain only normal windows. "
            f"Found {attack_count} attack-labelled windows in {path}."
        )


def write_predictions(path, rows, anomaly_scores, threshold):
    """Save original rows with anomaly scores and predictions."""
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


def evaluate_predictions(y_true, y_pred):
    """Calculate binary anomaly-detection evaluation metrics."""
    tn, fp, fn, tp = confusion_matrix(
        y_true,
        y_pred,
        labels=[0, 1],
    ).ravel()

    false_positive_rate = (
        fp / (fp + tn)
        if (fp + tn) > 0
        else 0.0
    )

    return {
        "total_test_windows": int(len(y_true)),
        "normal_windows": int(np.sum(y_true == 0)),
        "attack_windows": int(np.sum(y_true == 1)),
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
        "precision": float(
            precision_score(y_true, y_pred, zero_division=0)
        ),
        "recall": float(
            recall_score(y_true, y_pred, zero_division=0)
        ),
        "f1_score": float(
            f1_score(y_true, y_pred, zero_division=0)
        ),
        "false_positive_rate": float(false_positive_rate),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Train CAN-Sentinel's Isolation Forest detector."
    )

    parser.add_argument(
        "--train",
        required=True,
        help="Normal-only training features CSV.",
    )

    parser.add_argument(
        "--validation",
        required=True,
        help="Normal-only validation features CSV.",
    )

    parser.add_argument(
        "--test",
        help="Separate labelled test features CSV.",
    )

    parser.add_argument(
        "--output-dir",
        default="models",
        help="Directory for model and evaluation outputs.",
    )

    parser.add_argument(
        "--threshold-quantile",
        type=float,
        default=0.95,
        help="Normal validation score quantile used as the threshold.",
    )

    args = parser.parse_args()

    if not 0 < args.threshold_quantile < 1:
        parser.error("--threshold-quantile must be between 0 and 1.")

    # Load and validate training data.
    train_rows, X_train, y_train = load_features(
        args.train,
        require_labels=True,
    )
    validate_normal_only(y_train, args.train, "Training")

    # Load and validate normal validation data.
    validation_rows, X_validation, y_validation = load_features(
        args.validation,
        require_labels=True,
    )
    validate_normal_only(y_validation, args.validation, "Validation")

    if len(X_train) < 10:
        raise ValueError("Use at least 10 training windows.")

    if len(X_validation) < 5:
        raise ValueError("Use at least 5 normal validation windows.")

    print("Training and validation data checks passed.")

    # Train Isolation Forest.
    model = IsolationForest(
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_train)

    # Convert scores so that higher means more anomalous.
    validation_scores = -model.score_samples(X_validation)

    # Calibrate threshold using normal validation traffic only.
    threshold = float(
        np.quantile(
            validation_scores,
            args.threshold_quantile,
        )
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
        "n_estimators": 200,
        "random_state": 42,
        "training_rows": len(X_train),
        "validation_rows": len(X_validation),
        "sklearn_version": sklearn.__version__,
        "score_definition": (
            "anomaly_score = -IsolationForest.score_samples(X)"
        ),
        "alert_rule": (
            "ANOMALY if anomaly_score > threshold, otherwise NORMAL"
        ),
    }

    config_path.write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )

    print("\n========== TRAINING RESULTS ==========")
    print(f"Training windows: {len(X_train)}")
    print(f"Validation windows: {len(X_validation)}")
    print(f"Threshold quantile: {args.threshold_quantile}")
    print(f"Selected threshold: {threshold:.10f}")
    print(f"Saved model: {model_path}")
    print(f"Saved config: {config_path}")

    # Evaluate against a separate labelled test dataset, if supplied.
    if args.test:
        test_rows, X_test, y_test = load_features(
            args.test,
            require_labels=True,
        )

        test_scores = -model.score_samples(X_test)
        y_pred = (test_scores > threshold).astype(int)

        metrics = evaluate_predictions(y_test, y_pred)

        test_name = Path(args.test).stem

        predictions_path = (
            output_dir / f"{test_name}_predictions.csv"
        )

        evaluation_path = (
            output_dir / f"{test_name}_evaluation.json"
        )

        write_predictions(
            predictions_path,
            test_rows,
            test_scores,
            threshold,
        )

        evaluation = {
            "test_dataset": str(args.test),
            "threshold": threshold,
            "metrics": metrics,
        }

        evaluation_path.write_text(
            json.dumps(evaluation, indent=2),
            encoding="utf-8",
        )

        print("\n========== TEST EVALUATION ==========")
        print(f"Test dataset: {args.test}")
        print(f"Test windows: {len(test_rows)}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall: {metrics['recall']:.4f}")
        print(f"F1-score: {metrics['f1_score']:.4f}")
        print(
            "False-positive rate: "
            f"{metrics['false_positive_rate']:.4f}"
        )
        print(
            "Confusion matrix (TN, FP, FN, TP): "
            f"({metrics['true_negatives']}, "
            f"{metrics['false_positives']}, "
            f"{metrics['false_negatives']}, "
            f"{metrics['true_positives']})"
        )

        print(f"Saved predictions: {predictions_path}")
        print(f"Saved evaluation: {evaluation_path}")


if __name__ == "__main__":
    main()