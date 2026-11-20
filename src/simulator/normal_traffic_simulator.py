#!/usr/bin/env python3
"""Normal (benign) synthetic CAN traffic simulator for CAN-Sentinel, Week 1.

Run from the repository root:

    python3 -m src.simulator.normal_traffic_simulator --config config/config.example.json --duration 10

Three different counts are kept on purpose:
  generated   - a payload was built
  transmitted - the kernel accepted the frame for sending (send() returned)
  observed    - a DIFFERENT process read it back (reported by the monitor, not here)
"""
from __future__ import annotations

import argparse
import dataclasses
import errno
import heapq
import random
import signal
import sys
import threading
import time
from collections import Counter
from typing import Callable, Dict, List, Optional

from src.simulator.payload import PayloadGenerator
from src.utils.can_frame import CanInterfaceError, format_can_id, open_can_socket, pack_frame
from src.utils.config import Config, ConfigError, load_config, validate_interface_name
from src.utils.dataset import SENDER_COLUMNS, CsvSink
from src.utils.logging_setup import setup_logging

DRY_RUN_EPOCH = 1_700_000_000.0  # fixed start time so dry-run output is reproducible
MAX_CONSECUTIVE_FAILURES = 50
STATUS_EVERY_SECONDS = 5.0


class SimulationError(RuntimeError):
    pass


@dataclasses.dataclass
class SimStats:
    generated: int = 0
    transmitted: int = 0
    failed: int = 0
    interrupted: bool = False
    per_id: Counter = dataclasses.field(default_factory=Counter)


class SocketCanSender:
    """Sends frames on a CAN_RAW socket. Swap this class to change the traffic sink."""

    def __init__(self, interface: str):
        self._sock = open_can_socket(interface)

    def send(self, can_id: int, payload: bytes) -> None:
        self._sock.send(pack_frame(can_id, payload))

    def close(self) -> None:
        self._sock.close()


def run_simulation(
    cfg: Config,
    stop: threading.Event,
    sender: Optional[SocketCanSender],
    on_record: Callable[[Dict[str, object]], None],
    dry_run: bool = False,
    logger=None,
) -> SimStats:
    """Generate frames on a schedule until runtime ends or `stop` is set.

    dry_run=True uses a virtual clock (no sleeping, nothing sent), which makes
    the output instantly reproducible and testable without any CAN interface.
    """
    if not dry_run and sender is None:
        raise SimulationError("a sender is required unless dry_run=True")

    stats = SimStats()
    gens = {m.can_id: PayloadGenerator(m, cfg.random_seed) for m in cfg.messages}
    by_id = cfg.id_lookup()
    rng = random.Random(f"{cfg.random_seed}:schedule")
    jitter = cfg.jitter_percent / 100.0
    period = {m.can_id: (m.interval_ms / 1000.0) / cfg.rate_scale for m in cfg.messages}
    source = f"normal_traffic_simulator seed={cfg.random_seed}"

    # (due_time_seconds_since_start, can_id). Tiny per-message offsets stagger the first frames.
    heap = [(i * 0.003, m.can_id) for i, m in enumerate(cfg.messages)]
    heapq.heapify(heap)

    last_ts: Dict[int, float] = {}
    consecutive_failures = 0
    start_mono = time.monotonic()
    wall_start = DRY_RUN_EPOCH if dry_run else time.time()
    next_status = STATUS_EVERY_SECONDS

    while not stop.is_set():
        due, can_id = heap[0]
        if due >= cfg.runtime_seconds:
            break
        if not dry_run:
            delay = due - (time.monotonic() - start_mono)
            if delay > 0 and stop.wait(delay):
                break
        ts = (wall_start + due) if dry_run else time.time()

        msg = by_id[can_id]
        payload = gens[can_id].next_payload()
        stats.generated += 1

        status = "dry_run"
        if not dry_run:
            try:
                sender.send(can_id, payload)  # type: ignore[union-attr]
                status = "transmitted"
                stats.transmitted += 1
                consecutive_failures = 0
            except OSError as exc:
                stats.failed += 1
                consecutive_failures += 1
                status = f"failed:{errno.errorcode.get(exc.errno, exc.errno)}"
                if logger and consecutive_failures <= 3:
                    logger.warning("send failed for %s: %s", format_can_id(can_id), exc.strerror)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    raise SimulationError(
                        f"{MAX_CONSECUTIVE_FAILURES} sends failed in a row ({exc.strerror}). "
                        "Is the interface up? Check: ip link show " + cfg.interface
                    ) from exc

        if status in ("transmitted", "dry_run"):
            stats.per_id[can_id] += 1
        interval = (ts - last_ts[can_id]) if can_id in last_ts else None
        last_ts[can_id] = ts
        on_record({
            "timestamp": f"{ts:.6f}",
            "ecu_name": msg.ecu_name,
            "message_name": msg.name,
            "can_id": can_id,
            "can_id_hex": format_can_id(can_id),
            "dlc": len(payload),
            "payload_hex": payload.hex().upper(),
            "interval_s": "" if interval is None else f"{interval:.6f}",
            "status": status,
            "source": source,
        })
        if logger:
            logger.debug("%s %s %s [%d] %s", status, msg.ecu_name, format_can_id(can_id), len(payload), payload.hex(" ").upper())

        # Schedule from the intended time (not the actual one) so timing errors do not accumulate.
        next_due = due + period[can_id] * (1.0 + rng.uniform(-jitter, jitter))
        heapq.heapreplace(heap, (next_due, can_id))

        elapsed = due if dry_run else time.monotonic() - start_mono
        if logger and not dry_run and elapsed >= next_status:
            logger.info("running: %.0fs elapsed, generated=%d transmitted=%d failed=%d",
                        elapsed, stats.generated, stats.transmitted, stats.failed)
            next_status += STATUS_EVERY_SECONDS

    stats.interrupted = stop.is_set()
    return stats


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate synthetic NORMAL CAN traffic on a virtual CAN interface.")
    p.add_argument("--config", default="config/config.example.json", help="path to the JSON config")
    p.add_argument("--interface", help="override the interface from the config (vcanN only)")
    p.add_argument("--duration", type=float, help="override runtime_seconds")
    p.add_argument("--seed", type=int, help="override random_seed")
    p.add_argument("--output", help="override sender_log_path")
    p.add_argument("--dry-run", action="store_true", help="generate on a virtual clock; send nothing, need no interface")
    p.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="override console log level")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        cfg = load_config(args.config)
        overrides = {}
        if args.interface:
            overrides["interface"] = validate_interface_name(args.interface, "--interface")
        if args.duration is not None:
            if args.duration <= 0:
                raise ConfigError("--duration must be greater than 0")
            overrides["runtime_seconds"] = args.duration
        if args.seed is not None:
            if args.seed < 0:
                raise ConfigError("--seed must be 0 or greater")
            overrides["random_seed"] = args.seed
        if args.output:
            overrides["sender_log_path"] = args.output
        if args.log_level:
            overrides["log_level"] = args.log_level
        cfg = dataclasses.replace(cfg, **overrides)
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    log = setup_logging("simulator", cfg.log_level, cfg.log_file)
    stop = threading.Event()

    def _request_stop(signum, _frame):
        log.info("stop requested (signal %d); finishing cleanly...", signum)
        stop.set()

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    sender = None
    sink = None
    try:
        if not args.dry_run:
            sender = SocketCanSender(cfg.interface)
        sink = CsvSink(cfg.sender_log_path, SENDER_COLUMNS)
        mode = "DRY RUN (nothing is sent)" if args.dry_run else f"sending on {cfg.interface}"
        log.info("starting: %s, %d message types, seed=%d, runtime=%.1fs, rate_scale=%.2f",
                 mode, len(cfg.messages), cfg.random_seed, cfg.runtime_seconds, cfg.rate_scale)
        stats = run_simulation(cfg, stop, sender, sink.write, dry_run=args.dry_run, logger=log)
    except CanInterfaceError as exc:
        log.error("%s", exc)
        return 1
    except SimulationError as exc:
        log.error("%s", exc)
        return 1
    except OSError as exc:
        log.error("file error: %s (%s)", exc.strerror, getattr(exc, "filename", ""))
        return 1
    finally:
        if sink is not None:
            sink.close()
        if sender is not None:
            sender.close()

    reason = "interrupted by user" if stats.interrupted else "runtime reached"
    print(f"\nSimulation finished ({reason}).")
    print(f"  generated   : {stats.generated}   (payloads built)")
    if args.dry_run:
        print("  transmitted : 0   (dry run: nothing was sent)")
    else:
        print(f"  transmitted : {stats.transmitted}   (accepted by the kernel; NOT proof that anything received them)")
        print(f"  failed      : {stats.failed}")
    for can_id in sorted(stats.per_id):
        print(f"    {format_can_id(can_id)}  {cfg.id_lookup()[can_id].ecu_name}/{cfg.id_lookup()[can_id].name}: {stats.per_id[can_id]}")
    print(f"  sender log  : {cfg.sender_log_path}")
    if not args.dry_run:
        print("Independent verification: run the monitor (or candump) and compare, "
              "e.g. python3 -m src.utils.compare_logs  (see docs/week1_testing.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
