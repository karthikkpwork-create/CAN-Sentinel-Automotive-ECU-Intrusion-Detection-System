#!/usr/bin/env python3
"""Batch dataset generator for CAN-Sentinel (Role B).

Generates the complete set of required labeled datasets for Person C (Machine Learning):
  1. data/generated/normal_traffic.csv           (Pure normal baseline)
  2. data/generated/attack_injection.csv         (DoS / High-frequency burst)
  3. data/generated/attack_unknown_id.csv        (Unauthorized / rogue CAN IDs)
  4. data/generated/attack_payload_tampering.csv (Corrupted / out-of-range sensor readings)
  5. data/generated/attack_missing_message.csv   (ECU silence / message suppression)
  6. data/generated/mixed_traffic.csv            (Interleaved multi-attack scenario)

Usage:
    python scripts/generate_datasets.py
    python scripts/generate_datasets.py --duration 60 --seed 42
"""
from __future__ import annotations

import argparse
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
    run_attack_simulation,
)
from src.simulator.attack_traffic_simulator import DRY_RUN_EPOCH, build_attack_schedule
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
    import csv
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(WINDOW_COLUMNS)
        w.writerows(rows)


def generate_all(config_path: str, output_dir: str, duration: float, seed: int) -> None:
    os.makedirs(output_dir, exist_ok=True)
    cfg = load_config(config_path)

    import dataclasses
    cfg = dataclasses.replace(cfg, runtime_seconds=duration, random_seed=seed)

    print(f"============================================================")
    print(f" CAN-Sentinel Dataset Generation (Role B)")
    print(f" Target folder: {output_dir}")
    print(f" Duration: {duration}s per dataset | Seed: {seed}")
    print(f"============================================================\n")

    window_rows = []
    for filename, attack_type, description in DATASETS:
        out_path = os.path.join(output_dir, filename)
        print(f"-> Generating {filename:<32} [{description}]...")
        stop = threading.Event()
        supp_sink = None
        if attack_type in (ATTACK_MISSING_MESSAGE, ATTACK_MIXED):
            supp_sink = CsvSink(out_path[:-4] + "_suppressed.csv", SUPPRESSED_COLUMNS)
        a_start, a_dur = max(2.0, duration * 0.2), max(3.0, duration * 0.25)
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
                attack_start=a_start,
                attack_duration=a_dur,
                on_suppressed=supp_sink.write if supp_sink else None,
            )
        if supp_sink:
            supp_sink.close()
        for ev in build_attack_schedule(attack_type, duration, 0x100, 0x7FF, a_start, a_dur):
            window_rows.append([filename, ev.attack_type, f"{ev.start_time:.3f}", f"{ev.end_time:.3f}",
                                f"{DRY_RUN_EPOCH + ev.start_time:.6f}", f"{DRY_RUN_EPOCH + ev.end_time:.6f}",
                                format_can_id(ev.target_id)])
        print(f"   Done: {stats.generated} frames (Normal={stats.normal_count}, Attack={stats.attack_count}, Suppressed={stats.suppressed})")

    write_attack_windows(os.path.join(output_dir, "attack_windows.csv"), window_rows)
    print("\n[SUCCESS] All datasets generated successfully!")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate all CAN-Sentinel labeled datasets.")
    parser.add_argument("--config", default="config/config.example.json", help="Path to config file")
    parser.add_argument("--output-dir", default="data/generated", help="Directory to save datasets")
    parser.add_argument("--duration", type=float, default=60.0, help="Duration in seconds for each dataset")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    generate_all(args.config, args.output_dir, args.duration, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
