"""CSV schemas and a small writer shared by the simulator and the monitors.

Two different files exist on purpose:

* SENDER log   - written by the simulator: what it *generated* and *sent*.
* OBSERVED set - written by a monitor: what an independent process *saw* on the bus.

Week 2 should learn from the OBSERVED file, never from the sender log.
"""
from __future__ import annotations

import csv
import os
from typing import Dict, IO, List, Optional

SENDER_COLUMNS: List[str] = [
    "timestamp",      # simulator wall clock (epoch seconds) when the frame was sent
    "ecu_name",       # synthetic ECU identity
    "message_name",   # synthetic message name
    "can_id",         # decimal ID
    "can_id_hex",     # e.g. 0x100
    "dlc",            # data length (0-8)
    "payload_hex",    # payload as uppercase hex, no spaces
    "interval_s",     # seconds since the previous frame with the same ID (blank for the first)
    "status",         # transmitted | failed:<reason> | dry_run
    "source",         # simulator id + seed
]

OBSERVED_COLUMNS: List[str] = [
    "observed_timestamp",  # monitor's own clock (epoch seconds) when the frame was read
    "can_id",
    "can_id_hex",
    "ecu_name",            # looked up from the config by CAN ID (blank/unknown if not configured)
    "message_name",
    "dlc",
    "payload_hex",
    "inter_arrival_s",     # seconds since the previous OBSERVED frame with the same ID
    "frame_flags",         # blank for a normal frame, otherwise EXT and/or RTR
    "source",              # observed:<interface> (<monitor implementation>)
]

ATTACK_SENDER_COLUMNS: List[str] = SENDER_COLUMNS + [
    "label",          # 0 = normal, 1 = anomalous / attack
    "attack_type",    # normal | injection | unknown_id | payload_tampering | missing_message
]

LABELLED_OBSERVED_COLUMNS: List[str] = OBSERVED_COLUMNS + [
    "label",          # 0 = normal, 1 = anomalous / attack
    "attack_type",    # normal | injection | unknown_id | payload_tampering | missing_message
]


class CsvSink:
    """Append rows to a CSV file, writing the header once. Safe to close twice."""

    def __init__(self, path: str, columns: List[str]):
        self._columns = columns
        self._pending = 0
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self._fh: Optional[IO[str]] = open(path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=columns, extrasaction="raise")
        self._writer.writeheader()
        self._fh.flush()

    def write(self, row: Dict[str, object]) -> None:
        if self._fh is None:
            return
        self._writer.writerow(row)
        self._pending += 1
        if self._pending >= 20:
            self._fh.flush()
            self._pending = 0

    def close(self) -> None:
        if self._fh is not None:
            self._fh.flush()
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "CsvSink":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
