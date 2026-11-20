
#!/usr/bin/env python3
"""Batch dataset generator for CAN-Sentinel (Role B)."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import os
import sys
import threading

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.simulator.attack_traffic_simulator import (
    ATTACK_INJECTION,
    ATTACK_MISSING_MESSAGE,
    ATTACK_MIXED,
    ATTACK_NONE,
    ATTACK_PAYLOAD_TAMPERING,
    ATTACK_UNKNOWN_ID,
    DRY_RUN_EPOCH,
    build_attack_schedule,
    run_attack_simulation,
)
from src.utils.can_frame import format_can_id
from src.utils.config import load_config
from src.utils.dataset import ATTACK_SENDER_COLUMNS, CsvSink


DATASETS = [
    ("normal_traffic.csv", ATTACK_NONE, "Clean benign baseline"),
    ("attack_injection.csv", ATTACK_INJECTION, "DoS High-frequency Injection attack"),
    ("attack_unknown_id.csv", ATTACK_UNKNOWN_ID, "Unauthorized ID injection attack"),
    ("attack_payload_tampering.csv", ATTACK_PAYLOAD_TAMPERING, "Out-of-range payload tampering attack"),
    ("attack_missing_message.csv", ATTACK_MISSING_MESSAGE, "ECU suspension / missing message attack"),
    ("mixed_traffic.csv", ATTACK_MIXED, "Multi-attack mixed scenario"),
]


SUPPRESSED_COLUMNS = ["timestamp", "can_id", "can_id_hex", "label", "attack_type"]
WINDOW_COLUMNS = ["dataset", "attack_type", "start_s", "end_s", "start_timestamp", "end_timestamp", "target_can_id_hex"]


def write_attack_windows(path: str, rows: list) -> None:
    """Ground-truth attack windows (needed to evaluate missing_message, which has no attack rows)."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(WINDOW_COLUMNS)
        w.writerows(rows)


def generate_all(config_path: str, output_dir: str, duration: float, seed: int) -> None:
    os.makedirs(output_dir, exist_ok=True)

    cfg = load_config(config_path)
    cfg = dataclasses.replace(
        cfg,
        runtime_seconds=duration,
        random_seed=seed,
    )

    print("============================================================")
    print(" CAN-Sentinel Dataset Generation (Role B)")
    print(f" Target folder: {output_dir}")
    print(f" Duration: {duration}s per dataset | Seed: {seed}")
    print("============================================================\n")

    window_rows = []
    for filename, attack_type, description in DATASETS:

        out_path = os.path.join(output_dir, filename)

        # Define attack timing parameters
        attack_start = max(2.0, duration * 0.2)
        attack_duration = max(3.0, duration * 0.25)

        # Build the same attack schedule used by the simulator
        events = build_attack_schedule(
            attack_mode=attack_type,
            total_duration=duration,
            target_id=0x100,
            unknown_id=0x7FF,
            attack_start=attack_start,
            attack_duration=attack_duration,
        )

        # Save attack-event metadata alongside the CSV
        metadata_path = os.path.splitext(out_path)[0] + ".events.json"

        metadata = {
            "dataset": filename,
            "attack_mode": attack_type,
            "duration_seconds": duration,
            "seed": seed,
            "timestamp_origin": "DRY_RUN_EPOCH + elapsed simulation seconds",
            "events": [
                {
                    "attack_type": event.attack_type,
                    "start_time": event.start_time,
                    "end_time": event.end_time,
                    "target_id": event.target_id,
                    "extra": event.extra,
                }
                for event in events
            ],
        }

        with open(metadata_path, "w", encoding="utf-8") as metadata_file:
            json.dump(metadata, metadata_file, indent=4)

        for event in events:
            window_rows.append([
                filename,
                event.attack_type,
                f"{event.start_time:.3f}",
                f"{event.end_time:.3f}",
                f"{DRY_RUN_EPOCH + event.start_time:.6f}",
                f"{DRY_RUN_EPOCH + event.end_time:.6f}",
                format_can_id(event.target_id),
            ])

        print(f"-> Generating {filename:<32} [{description}]...")

        stop = threading.Event()
        supp_sink = None
        if attack_type in (ATTACK_MISSING_MESSAGE, ATTACK_MIXED):
            supp_sink = CsvSink(out_path[:-4] + "_suppressed.csv", SUPPRESSED_COLUMNS)
        with CsvSink(out_path, ATTACK_SENDER_COLUMNS) as sink:
            stats = run_attack_simulation(
                cfg=cfg,
                attack_mode=attack_type,
                stop=stop,
                sender=None,
                on_record=sink.write,
                dry_run=True,
                target_id=0x100,
                unknown_id=0x7FF,
                injection_interval_ms=5.0,
                attack_start=attack_start,
                attack_duration=attack_duration,
                on_suppressed=supp_sink.write if supp_sink else None,
            )
        if supp_sink:
            supp_sink.close()
        print(
            f"   Done: {stats.generated} frames "
            f"(Normal={stats.normal_count}, "
            f"Attack={stats.attack_count}, "
            f"Suppressed={stats.suppressed})"
        )

    write_attack_windows(os.path.join(output_dir, "attack_windows.csv"), window_rows)
    print("\n[SUCCESS] All datasets generated successfully!")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate all CAN-Sentinel labeled datasets."
    )

    parser.add_argument(
        "--config",
        default="config/config.example.json",
        help="Path to config file",
    )

    parser.add_argument(
        "--output-dir",
        default="data/generated",
        help="Directory to save datasets",
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Duration in seconds for each dataset",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )

    args = parser.parse_args()

    generate_all(
        args.config,
        args.output_dir,
        args.duration,
        args.seed,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
