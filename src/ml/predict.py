import argparse
import json
from pathlib import Path

import joblib
import numpy as np

from train_detector import FEATURES, load_features, write_predictions


def main():
    parser = argparse.ArgumentParser(
        description="Score CAN traffic with a trained CAN-Sentinel model."
    )
    parser.add_argument("--input", required=True, help="Feature CSV to score")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--output", default="reports/predictions.csv")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    model_path = model_dir / "can_sentinel_isolation_forest.joblib"
    config_path = model_dir / "detector_config.json"

    if not model_path.is_file() or not config_path.is_file():
        parser.error("Model or detector configuration not found. Train first.")

    config = json.loads(config_path.read_text(encoding="utf-8"))

    if config.get("features") != FEATURES:
        parser.error("Configured feature order does not match this script.")

    # Only load model artefacts created by your trusted project.
    model = joblib.load(model_path)

    if model.n_features_in_ != len(FEATURES):
        parser.error("Saved model feature count does not match the configuration.")

    rows, X = load_features(args.input)
    scores = -model.score_samples(X)
    threshold = float(config["threshold"])

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_predictions(output, rows, scores, threshold)

    alerts = int(np.sum(scores > threshold))
    print(f"Scored windows: {len(rows)}")
    print(f"Anomaly alerts: {alerts}")
    print(f"Predictions saved to: {output.resolve()}")


if __name__ == "__main__":
    main()