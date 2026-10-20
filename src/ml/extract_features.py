import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev


def as_number(value):
    """Convert a CSV value to a number, or return None if it is empty/invalid."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_features(input_path, output_path, window_seconds):
    input_path = Path(input_path)

    if not input_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {input_path}")

    with input_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("The CSV does not have a header row.")

        timestamp_column = (
            "observed_timestamp"
            if "observed_timestamp" in reader.fieldnames
            else "timestamp"
        )
        can_id_column = (
            "can_id_hex"
            if "can_id_hex" in reader.fieldnames
            else "can_id"
        )

        if timestamp_column not in reader.fieldnames:
            raise ValueError("No recognized timestamp column was found.")
        if can_id_column not in reader.fieldnames:
            raise ValueError("No recognized CAN ID column was found.")

        frames = []
        skipped_rows = 0

        for row in reader:
            timestamp = as_number(row.get(timestamp_column))
            can_id = (row.get(can_id_column) or "").strip()

            if timestamp is None or not can_id:
                skipped_rows += 1
                continue

            frames.append({
                "timestamp": timestamp,
                "can_id": can_id,
                "payload": (row.get("payload_hex") or "").strip(),
                "interval": as_number(
                    row.get("inter_arrival_s") or row.get("interval_s")
                ),
            })

    if not frames:
        raise ValueError("No rows with valid timestamps and CAN IDs were found.")

    frames.sort(key=lambda frame: frame["timestamp"])
    first_time = frames[0]["timestamp"]
    start_time = (first_time // window_seconds) * window_seconds

    windows = defaultdict(
        lambda: {
            "frame_count": 0,
            "can_ids": set(),
            "intervals": [],
            "last_payload_by_id": {},
            "payload_comparisons": 0,
            "payload_changes": 0,
        }
    )
    previous_timestamp_by_id = {}

    for frame in frames:
        can_id = frame["can_id"]
        timestamp = frame["timestamp"]
        window_index = int((timestamp - start_time) // window_seconds)
        window = windows[window_index]

        window["frame_count"] += 1
        window["can_ids"].add(can_id)

        # Use the CSV interval when present. If it is empty, estimate it
        # from timestamps for this CAN ID. These timestamps are assumed
        # to be in seconds.
        interval = frame["interval"]
        if interval is None and can_id in previous_timestamp_by_id:
            interval = timestamp - previous_timestamp_by_id[can_id]

        if interval is not None and interval >= 0:
            window["intervals"].append(interval)

        previous_timestamp_by_id[can_id] = timestamp

        payload = frame["payload"]
        if payload:
            previous_payload = window["last_payload_by_id"].get(can_id)

            if previous_payload is not None:
                window["payload_comparisons"] += 1
                if payload != previous_payload:
                    window["payload_changes"] += 1

            window["last_payload_by_id"][can_id] = payload

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "window_start_s",
        "frame_count",
        "frames_per_second",
        "unique_id_count",
        "iat_mean",
        "iat_std",
        "payload_change_rate",
        "payload_comparisons",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for window_index in sorted(windows):
            window = windows[window_index]
            intervals = window["intervals"]
            comparisons = window["payload_comparisons"]

            writer.writerow({
                "window_start_s": start_time + window_index * window_seconds,
                "frame_count": window["frame_count"],
                "frames_per_second": window["frame_count"] / window_seconds,
                "unique_id_count": len(window["can_ids"]),
                "iat_mean": mean(intervals) if intervals else "",
                "iat_std": pstdev(intervals) if intervals else "",
                "payload_change_rate": (
                    window["payload_changes"] / comparisons
                    if comparisons
                    else ""
                ),
                "payload_comparisons": comparisons,
            })

    print(f"Read {len(frames)} valid frames; skipped {skipped_rows} rows.")
    print(f"Created feature CSV: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract simple traffic features from a CAN CSV."
    )
    parser.add_argument("input_csv", help="Path to the input CAN traffic CSV")
    parser.add_argument(
        "--output",
        help="Output path (default: data/features/<input-name>_features.csv)",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=1.0,
        help="Window size in seconds (default: 1.0)",
    )
    args = parser.parse_args()

    if args.window_seconds <= 0:
        parser.error("--window-seconds must be greater than zero")

    input_path = Path(args.input_csv)
    output_path = args.output or (
        Path("data/features") / f"{input_path.stem}_features.csv"
    )

    extract_features(input_path, output_path, args.window_seconds)


if __name__ == "__main__":
    main()