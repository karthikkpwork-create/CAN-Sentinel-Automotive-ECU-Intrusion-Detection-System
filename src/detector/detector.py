#!/usr/bin/env python3
"""CAN-Sentinel detector: scores traffic windows with an Isolation Forest.

Owner: Person A (Karthik).  This module is a DETECTOR only: it reports
suspicious windows. It never sends, blocks or modifies CAN traffic.

What it does (offline CSV mode)
-------------------------------
    CAN CSV --(src.ml.extract_features)--> window features
            --(Isolation Forest)--> status + anomaly score per window
            --(per-ID message counts)--> suspect CAN ID for anomalous windows

Live reading from ``vcan0`` is NOT implemented here yet.

Input schema
------------
* Raw CAN CSV: the format that ``src.ml.extract_features`` already accepts
  (timestamp column ``observed_timestamp`` or ``timestamp``; ID column
  ``can_id_hex`` or ``can_id``; optional ``payload_hex``).
* Feature table (output of the extractor), columns:
  ``window_start_s, frame_count, frames_per_second, unique_id_count,
  iat_mean, iat_std, payload_change_rate, payload_comparisons``.
  ``window_start_s`` is only an identifier; it is never a model input.

Output schema (DataFrame returned by ``detect_csv``; one row per window)
-----------------------------------------------------------------------
* ``window_start_s``  window start, seconds (same clock as the input CSV)
* ``status``          ``"normal"`` or ``"anomalous"``
* ``prediction``      scikit-learn label: ``1`` = inlier, ``-1`` = outlier
* ``anomaly_score``   ``decision_function`` value; LOWER = more anomalous
* ``suspect_can_id``  most deviating CAN ID (anomalous windows only), else ""
* ``suspect_reason``  ``count_zscore`` | ``id_not_in_training_baseline`` |
                      ``no_count_deviation`` | ``no_per_id_counts`` | ""
* ``suspect_zscore``  z-score of that ID's frame count (NaN if not applicable)
* ``blank_features_filled``  blank feature cells replaced by the fill value

Rules used (read before trusting the output)
--------------------------------------------
* ``status`` is ``anomalous`` when ``anomaly_score < threshold``. The default
  threshold 0.0 is scikit-learn's own boundary (``predict() == -1``), which is
  set by the ``contamination`` value used at training (default 0.05). It is NOT
  a validated threshold; tune it with separate validation data.
* Blank cells (``iat_mean``, ``iat_std``, ``payload_change_rate`` when a window
  has too little data) are filled with 0.0, as ``docs/ml_features.md`` says,
  and counted in ``blank_features_filled``. Training uses the same rule.
* The suspect ID names the MESSAGE that deviates, not the physical ECU that
  sent it: CAN frames carry no sender address. Anomalies in timing or payload
  only (no count deviation) get ``no_count_deviation``, not a guessed ID.
* Model files are pickled with joblib: only load files you trust.

Model file contract (joblib dict, ``schema_version`` 1)
------------------------------------------------------
``model`` (IsolationForest), ``feature_columns`` (ordered list), ``threshold``,
``window_seconds``, ``fill_value``, ``id_stats`` ({id: {"mean","std"}}),
``trained_on``, ``seed``, ``contamination``.  ``train`` below writes it; a
future ``src/ml/train.py`` can write the same dict.

Usage
-----
    python -m src.detector.detector train  --normal-csv data/generated/normal_traffic.csv --model models/detector.joblib
    python -m src.detector.detector detect --csv data/generated/mixed_traffic.csv --model models/detector.joblib --check-labels
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import logging
import math
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.ml.extract_features import extract_features

LOG = logging.getLogger(__name__)

BUNDLE_SCHEMA_VERSION = 1
WINDOW_COLUMN = "window_start_s"
FEATURE_COLUMNS: Tuple[str, ...] = (
    "frame_count",
    "frames_per_second",
    "unique_id_count",
    "iat_mean",
    "iat_std",
    "payload_change_rate",
    "payload_comparisons",
)
RESULT_COLUMNS = [
    WINDOW_COLUMN, "status", "prediction", "anomaly_score", "suspect_can_id",
    "suspect_reason", "suspect_zscore", "blank_features_filled",
]
BLANK_FILL_VALUE = 0.0       # matches docs/ml_features.md ("set to zero")
STD_FLOOR = 1.0              # avoids dividing by ~0 for very steady IDs
SUSPECT_Z_MIN = 3.0          # assumption, not validated
# 'auto' flagged ~28% of NORMAL windows on the simulator's very regular traffic
# (measured), so training defaults to 0.05. Still an assumption: tune it with
# separate validation data.
DEFAULT_CONTAMINATION = 0.05
MIN_TRAIN_WINDOWS = 10
STATUS_NORMAL, STATUS_ANOMALOUS = "normal", "anomalous"


class DetectorError(Exception):
    """Any problem with the data, the model file or the arguments."""


@dataclass
class ModelBundle:
    """Everything needed to score new traffic consistently with training."""
    model: IsolationForest
    feature_columns: List[str]
    threshold: float
    window_seconds: float
    fill_value: float
    id_stats: Dict[str, Dict[str, float]]
    trained_on: str = ""
    seed: Optional[int] = None
    contamination: object = "auto"


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def normalize_can_id(text: str) -> str:
    """'0x100' and '256' both become '0x100'. Raises ValueError if invalid."""
    value = int(str(text).strip(), 0)
    if value < 0:
        raise ValueError("negative CAN ID")
    return f"0x{value:X}"


def window_key(timestamp: float, window_seconds: float) -> float:
    """Window start for a timestamp, same anchoring as the feature extractor."""
    return round(math.floor(timestamp / window_seconds) * window_seconds, 6)


def _read_columns(path: Path):
    """Return (reader, timestamp_col, id_col) using the extractor's rules."""
    handle = path.open("r", newline="", encoding="utf-8-sig")
    reader = csv.DictReader(handle)
    names = reader.fieldnames or []
    ts_col = "observed_timestamp" if "observed_timestamp" in names else "timestamp"
    id_col = "can_id_hex" if "can_id_hex" in names else "can_id"
    if ts_col not in names or id_col not in names:
        handle.close()
        raise DetectorError(f"{path}: no recognised timestamp/CAN ID columns")
    return handle, reader, ts_col, id_col


def per_window_id_counts(csv_path, window_seconds: float) -> Dict[float, Counter]:
    """Frame count per CAN ID inside each window (invalid rows are skipped)."""
    path = Path(csv_path)
    handle, reader, ts_col, id_col = _read_columns(path)
    counts: Dict[float, Counter] = defaultdict(Counter)
    skipped = 0
    with handle:
        for row in reader:
            try:
                ts = float(row[ts_col])
                can_id = normalize_can_id(row[id_col])
            except (TypeError, ValueError):
                skipped += 1
                continue
            if not math.isfinite(ts):
                skipped += 1
                continue
            counts[window_key(ts, window_seconds)][can_id] += 1
    if skipped:
        LOG.warning("%s: %d rows skipped when counting frames per ID", path, skipped)
    return counts


def compute_features(csv_path, window_seconds: float) -> pd.DataFrame:
    """Run the EXISTING extractor (no second implementation) and load its CSV."""
    path = Path(csv_path)
    if not path.is_file():
        raise DetectorError(f"CAN CSV not found: {path}")
    if window_seconds <= 0:
        raise DetectorError("window_seconds must be greater than zero")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "features.csv"
        captured = io.StringIO()
        try:
            with contextlib.redirect_stdout(captured):
                extract_features(path, out, window_seconds)
        except (ValueError, OSError) as exc:
            raise DetectorError(f"feature extraction failed for {path}: {exc}") from exc
        LOG.debug(captured.getvalue().strip())
        return pd.read_csv(out)


def prepare_features(
    features: pd.DataFrame, columns: Sequence[str], fill_value: float
) -> Tuple[np.ndarray, np.ndarray]:
    """Validate and order features; return (matrix, blanks_filled_per_row).

    The matrix columns follow ``columns`` exactly, whatever order or extra
    columns the input DataFrame has.
    """
    if features is None or len(features) == 0:
        raise DetectorError("no feature rows to score (empty input)")
    missing = [c for c in columns if c not in features.columns]
    if missing:
        raise DetectorError(f"missing feature columns: {missing}")
    selected = features.loc[:, list(columns)]
    try:
        numeric = selected.apply(pd.to_numeric, errors="raise")
    except (ValueError, TypeError) as exc:
        raise DetectorError(f"non-numeric value in feature columns: {exc}") from exc
    values = numeric.to_numpy(dtype=float)
    if np.isinf(values).any():
        raise DetectorError("feature columns contain infinite values")
    blanks = np.isnan(values)
    values = np.where(blanks, fill_value, values)
    return values, blanks.sum(axis=1)


# --------------------------------------------------------------------------
# Model file handling
# --------------------------------------------------------------------------
def save_bundle(bundle: ModelBundle, path) -> Path:
    """Write the model file (creates the folder; refuses to overwrite a dir)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "model": bundle.model,
        "feature_columns": list(bundle.feature_columns),
        "threshold": float(bundle.threshold),
        "window_seconds": float(bundle.window_seconds),
        "fill_value": float(bundle.fill_value),
        "id_stats": bundle.id_stats,
        "trained_on": bundle.trained_on,
        "seed": bundle.seed,
        "contamination": bundle.contamination,
    }, target)
    return target


def load_bundle(path) -> ModelBundle:
    """Load and validate a model file with clear errors."""
    target = Path(path)
    if not target.is_file():
        raise DetectorError(f"model file not found: {target} (train one first)")
    try:
        raw = joblib.load(target)
    except Exception as exc:  # joblib/pickle raise many different types
        raise DetectorError(f"model file is unreadable or corrupted: {target} ({exc})") from exc
    if not isinstance(raw, dict):
        raise DetectorError(f"{target}: expected a dict model file, got {type(raw).__name__}")
    needed = ["schema_version", "model", "feature_columns", "threshold",
              "window_seconds", "fill_value", "id_stats"]
    absent = [k for k in needed if k not in raw]
    if absent:
        raise DetectorError(f"{target}: model file is missing keys {absent}")
    if raw["schema_version"] != BUNDLE_SCHEMA_VERSION:
        raise DetectorError(
            f"{target}: schema_version {raw['schema_version']} not supported "
            f"(expected {BUNDLE_SCHEMA_VERSION})")
    model = raw["model"]
    if not hasattr(model, "decision_function") or not hasattr(model, "predict"):
        raise DetectorError(f"{target}: 'model' has no decision_function/predict")
    columns = list(raw["feature_columns"])
    expected_n = getattr(model, "n_features_in_", len(columns))
    if len(columns) != expected_n:
        raise DetectorError(
            f"{target}: model expects {expected_n} features but file lists {len(columns)}")
    return ModelBundle(
        model=model, feature_columns=columns, threshold=float(raw["threshold"]),
        window_seconds=float(raw["window_seconds"]), fill_value=float(raw["fill_value"]),
        id_stats=dict(raw["id_stats"]), trained_on=str(raw.get("trained_on", "")),
        seed=raw.get("seed"), contamination=raw.get("contamination", "auto"))


# --------------------------------------------------------------------------
# Training (interim helper until src/ml/train.py exists)
# --------------------------------------------------------------------------
def _assert_normal_only(csv_path: Path) -> None:
    """Refuse to train on a CSV that has attack labels."""
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            label = (row.get("label") or "").strip()
            kind = (row.get("attack_type") or "").strip().lower()
            if label not in ("", "0") or kind not in ("", "normal"):
                raise DetectorError(
                    f"{csv_path} contains attack-labelled frames; "
                    "training must use normal traffic only")


def train_bundle(
    normal_csv, window_seconds: float = 1.0, contamination=DEFAULT_CONTAMINATION,
    seed: int = 42, n_estimators: int = 100,
) -> ModelBundle:
    """Fit an Isolation Forest on NORMAL traffic windows only."""
    path = Path(normal_csv)
    if not path.is_file():
        raise DetectorError(f"normal-traffic CSV not found: {path}")
    _assert_normal_only(path)
    features = compute_features(path, window_seconds)
    if len(features) < MIN_TRAIN_WINDOWS:
        raise DetectorError(
            f"only {len(features)} windows in {path}; need at least {MIN_TRAIN_WINDOWS}")
    matrix, _ = prepare_features(features, FEATURE_COLUMNS, BLANK_FILL_VALUE)
    model = IsolationForest(
        n_estimators=n_estimators, contamination=contamination, random_state=seed)
    model.fit(matrix)

    # Per-ID baseline of "frames per window", used only to name a suspect ID.
    counts = per_window_id_counts(path, window_seconds)
    window_keys = [round(float(w), 6) for w in features[WINDOW_COLUMN]]
    all_ids = sorted({cid for w in window_keys for cid in counts.get(w, {})})
    id_stats: Dict[str, Dict[str, float]] = {}
    for cid in all_ids:
        series = np.array([counts.get(w, Counter()).get(cid, 0) for w in window_keys], float)
        id_stats[cid] = {"mean": float(series.mean()), "std": float(series.std())}
    return ModelBundle(
        model=model, feature_columns=list(FEATURE_COLUMNS), threshold=0.0,
        window_seconds=window_seconds, fill_value=BLANK_FILL_VALUE, id_stats=id_stats,
        trained_on=str(path), seed=seed, contamination=contamination)


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------
def find_suspect(
    window_counts: Mapping[str, int], id_stats: Mapping[str, Mapping[str, float]],
    z_min: float = SUSPECT_Z_MIN,
) -> Tuple[str, str, float]:
    """Pick the CAN ID whose frame count deviates most from its baseline.

    Returns (can_id, reason, z). IDs never seen in training win first, because
    "not in the baseline" is an unambiguous signal. This names a MESSAGE ID,
    not a physical sender.
    """
    if not window_counts and not id_stats:
        return "", "no_per_id_counts", float("nan")
    unknown = [cid for cid in window_counts if cid not in id_stats]
    if unknown:
        worst = max(unknown, key=lambda cid: window_counts[cid])
        return worst, "id_not_in_training_baseline", float("nan")
    best_id, best_z = "", 0.0
    for cid, stats in id_stats.items():
        spread = max(float(stats["std"]), STD_FLOOR)
        z = (window_counts.get(cid, 0) - float(stats["mean"])) / spread
        if abs(z) > abs(best_z):
            best_id, best_z = cid, z
    if abs(best_z) < z_min:
        return "", "no_count_deviation", best_z
    return best_id, "count_zscore", best_z


def score_features(
    features: pd.DataFrame, bundle: ModelBundle, threshold: Optional[float] = None
) -> pd.DataFrame:
    """Score a feature table. Suspect columns are left blank (see detect_csv)."""
    limit = bundle.threshold if threshold is None else float(threshold)
    if WINDOW_COLUMN not in features.columns:
        raise DetectorError(f"feature table needs a '{WINDOW_COLUMN}' column")
    matrix, filled = prepare_features(features, bundle.feature_columns, bundle.fill_value)
    try:
        scores = bundle.model.decision_function(matrix)
        labels = bundle.model.predict(matrix)
    except ValueError as exc:
        raise DetectorError(f"model rejected the features: {exc}") from exc
    anomalous = scores < limit
    return pd.DataFrame({
        WINDOW_COLUMN: features[WINDOW_COLUMN].to_numpy(),
        "status": np.where(anomalous, STATUS_ANOMALOUS, STATUS_NORMAL),
        "prediction": labels.astype(int),
        "anomaly_score": scores,
        "suspect_can_id": "",
        "suspect_reason": "",
        "suspect_zscore": np.nan,
        "blank_features_filled": filled.astype(int),
    }, columns=RESULT_COLUMNS)


def detect_csv(csv_path, bundle: ModelBundle, threshold: Optional[float] = None) -> pd.DataFrame:
    """Raw CAN CSV -> per-window results (see the output schema above)."""
    features = compute_features(csv_path, bundle.window_seconds)
    results = score_features(features, bundle, threshold)
    counts = per_window_id_counts(csv_path, bundle.window_seconds)
    for idx in results.index[results["status"] == STATUS_ANOMALOUS]:
        key = round(float(results.at[idx, WINDOW_COLUMN]), 6)
        window_counts = counts.get(key)
        if not window_counts:
            results.at[idx, "suspect_reason"] = "no_per_id_counts"
            continue
        cid, reason, z = find_suspect(window_counts, bundle.id_stats)
        results.at[idx, "suspect_can_id"] = cid
        results.at[idx, "suspect_reason"] = reason
        results.at[idx, "suspect_zscore"] = z
    return results


def summarize_against_labels(results: pd.DataFrame, csv_path, window_seconds: float) -> Dict[str, float]:
    """Sanity check only: a window counts as attack if any frame in it is labelled attack."""
    path = Path(csv_path)
    handle, reader, ts_col, _ = _read_columns(path)
    attack_windows: set = set()
    seen_label = False
    with handle:
        names = reader.fieldnames or []
        if "label" not in names and "attack_type" not in names:
            raise DetectorError(f"{path} has no 'label' or 'attack_type' column")
        for row in reader:
            try:
                ts = float(row[ts_col])
            except (TypeError, ValueError):
                continue
            label = (row.get("label") or "").strip()
            kind = (row.get("attack_type") or "").strip().lower()
            seen_label = seen_label or bool(label or kind)
            if label not in ("", "0") or kind not in ("", "normal"):
                attack_windows.add(window_key(ts, window_seconds))
    if not seen_label:
        raise DetectorError(f"{path}: label columns are empty")
    tp = fn = fp = tn = 0
    for _, row in results.iterrows():
        is_attack = round(float(row[WINDOW_COLUMN]), 6) in attack_windows
        flagged = row["status"] == STATUS_ANOMALOUS
        tp += is_attack and flagged
        fn += is_attack and not flagged
        fp += (not is_attack) and flagged
        tn += (not is_attack) and not flagged
    attack_total, normal_total = tp + fn, fp + tn
    return {
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "recall": tp / attack_total if attack_total else float("nan"),
        "false_alarm_rate": fp / normal_total if normal_total else float("nan"),
    }


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CAN-Sentinel Isolation Forest detector (offline CSV mode).")
    parser.add_argument("--log-level", default="WARNING",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    sub = parser.add_subparsers(dest="command", required=True)

    train = sub.add_parser("train", help="fit on a NORMAL-only CSV and save a model file")
    train.add_argument("--normal-csv", required=True)
    train.add_argument("--model", required=True, help="where to write the model file")
    train.add_argument("--window-seconds", type=float, default=1.0)
    train.add_argument("--seed", type=int, default=42)
    train.add_argument("--contamination", default=str(DEFAULT_CONTAMINATION),
                       help="'auto' or a fraction in (0, 0.5]; default %(default)s")

    detect = sub.add_parser("detect", help="score a CAN CSV with a saved model")
    detect.add_argument("--csv", required=True)
    detect.add_argument("--model", required=True)
    detect.add_argument("--threshold", type=float, help="override the model's threshold")
    detect.add_argument("--output", help="write per-window results to this CSV")
    detect.add_argument("--max-alerts", type=int, default=20, help="alert lines to print")
    detect.add_argument("--check-labels", action="store_true",
                        help="if the CSV has labels, print a window-level sanity check")
    return parser


def _parse_contamination(text: str):
    if text == "auto":
        return "auto"
    try:
        value = float(text)
    except ValueError as exc:
        raise DetectorError(f"--contamination must be 'auto' or a number, got {text!r}") from exc
    if not 0.0 < value <= 0.5:
        raise DetectorError("--contamination must be in (0, 0.5]")
    return value


def _run_train(args) -> int:
    bundle = train_bundle(args.normal_csv, args.window_seconds,
                          _parse_contamination(args.contamination), args.seed)
    target = save_bundle(bundle, args.model)
    print(f"Trained on {args.normal_csv}: {len(bundle.id_stats)} CAN IDs in baseline.")
    print(f"Model saved to {target}")
    return 0


def _run_detect(args) -> int:
    bundle = load_bundle(args.model)
    results = detect_csv(args.csv, bundle, args.threshold)
    alerts = results[results["status"] == STATUS_ANOMALOUS]
    print(f"{len(results)} windows scored, {len(alerts)} anomalous "
          f"(threshold {bundle.threshold if args.threshold is None else args.threshold}).")
    for _, row in alerts.head(args.max_alerts).iterrows():
        suspect = row["suspect_can_id"] or "-"
        print(f"  ALERT window {row[WINDOW_COLUMN]:.0f}  score {row['anomaly_score']:+.3f}  "
              f"suspect ID {suspect} ({row['suspect_reason']})")
    if len(alerts) > args.max_alerts:
        print(f"  ... {len(alerts) - args.max_alerts} more (use --output to save all)")
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"Results written to {args.output}")
    if args.check_labels:
        s = summarize_against_labels(results, args.csv, bundle.window_seconds)
        print("Label check (windows): "
              f"attack windows caught {s['tp']}/{s['tp'] + s['fn']}, "
              f"false alarms {s['fp']}/{s['fp'] + s['tn']} normal windows "
              f"(recall {s['recall']:.2f}, false-alarm rate {s['false_alarm_rate']:.2f}). "
              "Sanity check only, not a final evaluation.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(message)s")
    try:
        return _run_train(args) if args.command == "train" else _run_detect(args)
    except DetectorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
