#!/usr/bin/env python3
"""Attach ground-truth labels to an OBSERVED capture using the attack SENDER log.

    python3 -m src.utils.label_observed --sent data/generated/attack_sender_mixed.csv \
        --observed data/generated/observed_attack_mixed.csv --output data/generated/observed_attack_mixed_labeled.csv

Each observed frame is matched to a sender row with the same (CAN ID, payload), oldest first,
and inherits that row's `label` and `attack_type`. An observed frame with no sender match is
labeled 1 / `unmatched` (it was not sent by the simulator). Sender rows that were never
observed are reported on stdout (e.g. frames lost) and are not added.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict, deque
from typing import Dict, Iterable, List, Tuple


def label_rows(sent: Iterable[Dict[str, str]], observed: Iterable[Dict[str, str]]) -> Tuple[List[Dict[str, str]], int]:
    """Return (labeled observed rows, number of sender rows never observed)."""
    pending: Dict[Tuple[str, str], deque] = defaultdict(deque)
    for r in sent:
        if str(r.get("status", "")).startswith("failed"):
            continue
        pending[(str(r["can_id"]), r["payload_hex"].upper())].append(r)
    out: List[Dict[str, str]] = []
    for o in observed:
        q = pending.get((str(o["can_id"]), o["payload_hex"].upper()))
        row = dict(o)
        if q:
            m = q.popleft()
            row["label"], row["attack_type"] = m["label"], m["attack_type"]
        else:
            row["label"], row["attack_type"] = "1", "unmatched"
        out.append(row)
    return out, sum(len(q) for q in pending.values())


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Label an observed CAN capture from the attack sender log.")
    p.add_argument("--sent", required=True)
    p.add_argument("--observed", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args(argv)
    try:
        with open(a.sent, newline="", encoding="utf-8") as f:
            sent = list(csv.DictReader(f))
        with open(a.observed, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            fields = list(rd.fieldnames or [])
            observed = list(rd)
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    rows, never_seen = label_rows(sent, observed)
    with open(a.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields + ["label", "attack_type"])
        w.writeheader()
        w.writerows(rows)
    n_att = sum(1 for r in rows if r["label"] == "1")
    print(f"observed={len(rows)} attack={n_att} normal={len(rows) - n_att} sent_but_not_observed={never_seen}")
    print(f"saved: {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
