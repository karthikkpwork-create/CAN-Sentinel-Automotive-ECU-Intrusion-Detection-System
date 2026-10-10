#!/usr/bin/env python3
"""Compare what the simulator TRANSMITTED with what a monitor OBSERVED.

This is the evidence that frames really crossed the (virtual) bus and were
read by an independent process.

    python3 -m src.utils.compare_logs --config config/config.example.json
    python3 -m src.utils.compare_logs --sent data/generated/sender_log.csv --observed data/generated/observed_normal_traffic.csv

Frames are matched as (CAN ID, payload) pairs, counted per CAN ID.
Exit code: 0 = every transmitted frame was observed, 1 = some missing, 2 = bad input.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from typing import Counter as CounterT, List, Optional, Tuple

from src.utils.config import ConfigError, load_config

Key = Tuple[str, str]


def _read(path: str, id_col: str, payload_col: str, status_col: Optional[str]) -> CounterT[Key]:
    counts: CounterT[Key] = Counter()
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            needed = {id_col, payload_col} | ({status_col} if status_col else set())
            missing = needed - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{path}: missing column(s) {sorted(missing)}")
            for row in reader:
                if status_col and row[status_col] != "transmitted":
                    continue
                counts[(row[id_col], row[payload_col])] += 1
    except FileNotFoundError:
        raise ValueError(f"file not found: {path}") from None
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc.strerror}") from exc
    return counts


def compare(sent: CounterT[Key], observed: CounterT[Key]) -> dict:
    ids = sorted({k[0] for k in sent} | {k[0] for k in observed})
    per_id = {}
    for can_id in ids:
        s = {k: v for k, v in sent.items() if k[0] == can_id}
        o = {k: v for k, v in observed.items() if k[0] == can_id}
        matched = sum(min(v, o.get(k, 0)) for k, v in s.items())
        per_id[can_id] = {
            "transmitted": sum(s.values()),
            "observed": sum(o.values()),
            "matched": matched,
            "missing": sum(s.values()) - matched,
            "unexpected": sum(o.values()) - matched,
        }
    totals = {k: sum(d[k] for d in per_id.values()) for k in ("transmitted", "observed", "matched", "missing", "unexpected")}
    return {"per_id": per_id, "totals": totals}


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Compare the simulator sender log with an observed dataset.")
    p.add_argument("--config", help="read both file paths from this config")
    p.add_argument("--sent", help="sender log CSV")
    p.add_argument("--observed", help="observed dataset CSV")
    args = p.parse_args(argv)

    sent_path, obs_path = args.sent, args.observed
    if args.config:
        try:
            cfg = load_config(args.config)
        except ConfigError as exc:
            print(f"CONFIG ERROR: {exc}", file=sys.stderr)
            return 2
        sent_path = sent_path or cfg.sender_log_path
        obs_path = obs_path or cfg.observed_dataset_path
    if not sent_path or not obs_path:
        print("ERROR: give --config, or both --sent and --observed", file=sys.stderr)
        return 2

    try:
        sent = _read(sent_path, "can_id_hex", "payload_hex", "status")
        observed = _read(obs_path, "can_id_hex", "payload_hex", None)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    result = compare(sent, observed)
    print(f"{'CAN ID':<8} {'transmitted':>11} {'observed':>9} {'matched':>8} {'missing':>8} {'unexpected':>11}")
    for can_id, d in result["per_id"].items():
        print(f"{can_id:<8} {d['transmitted']:>11} {d['observed']:>9} {d['matched']:>8} {d['missing']:>8} {d['unexpected']:>11}")
    t = result["totals"]
    print(f"{'TOTAL':<8} {t['transmitted']:>11} {t['observed']:>9} {t['matched']:>8} {t['missing']:>8} {t['unexpected']:>11}")
    if t["transmitted"] == 0:
        print("\nRESULT: nothing to compare (the sender log has no transmitted frames).")
        return 2
    if t["missing"] == 0:
        print("\nRESULT: every transmitted frame was independently observed.")
        return 0
    print(f"\nRESULT: {t['missing']} transmitted frame(s) were NOT observed (was the monitor started first?).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
