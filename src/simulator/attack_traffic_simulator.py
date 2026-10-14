#!/usr/bin/env python3
"""Synthetic CAN attack traffic simulator for CAN-Sentinel, Role B (Week 2).

Generates normal background traffic and controlled cyber-attacks on SocketCAN
or in hardware-free dry-run mode for labeled dataset creation.

Supported Attack Types:
  1. injection         - Flood bus with high-frequency frames for a known ID (e.g. 0x100 every 5ms)
  2. unknown_id        - Inject frames with unauthorized/unknown arbitration IDs (e.g. 0x7FF)
  3. payload_tampering - Inject legitimate IDs with corrupted/out-of-bounds signal values
  4. missing_message   - Suppress/halt transmission of an expected recurring ID for several seconds
  5. mixed             - Schedule multiple attack types across the simulation run
  6. none              - Pure normal baseline traffic

Usage:
  # Dry-run generation on Windows or Linux (no CAN interface needed):
  python -m src.simulator.attack_traffic_simulator --dry-run --attack mixed --duration 30 --output data/generated/mixed_traffic.csv

  # Live transmission on Linux vcan0:
  python -m src.simulator.attack_traffic_simulator --interface vcan0 --attack injection --duration 10
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
from typing import Callable, Dict, List, Optional, Set, Tuple

from src.simulator.normal_traffic_simulator import SocketCanSender
from src.simulator.payload import PayloadGenerator
from src.utils.can_frame import CanInterfaceError, format_can_id
from src.utils.config import Config, ConfigError, MessageDef, load_config, validate_interface_name
from src.utils.dataset import ATTACK_SENDER_COLUMNS, CsvSink
from src.utils.logging_setup import setup_logging

DRY_RUN_EPOCH = 1_700_000_000.0
STATUS_EVERY_SECONDS = 5.0
MAX_CONSECUTIVE_FAILURES = 50

# Attack type constants
ATTACK_NONE = "none"
ATTACK_INJECTION = "injection"
ATTACK_UNKNOWN_ID = "unknown_id"
ATTACK_PAYLOAD_TAMPERING = "payload_tampering"
ATTACK_MISSING_MESSAGE = "missing_message"
ATTACK_MIXED = "mixed"

ALL_ATTACKS = [
    ATTACK_NONE,
    ATTACK_INJECTION,
    ATTACK_UNKNOWN_ID,
    ATTACK_PAYLOAD_TAMPERING,
    ATTACK_MISSING_MESSAGE,
    ATTACK_MIXED,
]


@dataclasses.dataclass
class AttackEvent:
    attack_type: str
    start_time: float
    end_time: float
    target_id: Optional[int] = None
    extra: Dict[str, object] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class AttackSimStats:
    generated: int = 0
    transmitted: int = 0
    failed: int = 0
    suppressed: int = 0
    normal_count: int = 0
    attack_count: int = 0
    interrupted: bool = False
    per_attack_type: Counter = dataclasses.field(default_factory=Counter)
    per_id: Counter = dataclasses.field(default_factory=Counter)


def build_tampered_payload(msg: MessageDef, rng: random.Random) -> bytes:
    """Generate a payload for msg with out-of-range / anomalous signal values."""
    buf = bytearray(msg.dlc)
    for sig in msg.signals:
        max_possible = (1 << (8 * sig.size)) - 1
        # Create an extreme value outside [sig.minimum, sig.maximum]
        if rng.random() < 0.5 and sig.maximum * 2 < max_possible:
            tampered_val = min(max_possible, int(sig.maximum * 1.8 + 50))
        else:
            tampered_val = max(0, int(sig.minimum * 0.2 - 20)) if sig.minimum > 20 else max_possible
        # Clip to representation width
        tampered_val = max(0, min(max_possible, tampered_val))
        buf[sig.start_byte:sig.start_byte + sig.size] = tampered_val.to_bytes(sig.size, "big")
    if msg.counter_byte is not None:
        buf[msg.counter_byte] = rng.randint(0, 255)
    return bytes(buf)


def build_attack_schedule(
    attack_mode: str,
    total_duration: float,
    target_id: int,
    unknown_id: int,
    attack_start: float = 5.0,
    attack_duration: float = 5.0,
) -> List[AttackEvent]:
    """Create the timeline of attack events for this simulation."""
    events: List[AttackEvent] = []

    if attack_mode == ATTACK_NONE:
        return events

    if attack_mode == ATTACK_INJECTION:
        events.append(AttackEvent(
            attack_type=ATTACK_INJECTION,
            start_time=attack_start,
            end_time=min(total_duration, attack_start + attack_duration),
            target_id=target_id,
            extra={"interval_ms": 5.0},
        ))
    elif attack_mode == ATTACK_UNKNOWN_ID:
        events.append(AttackEvent(
            attack_type=ATTACK_UNKNOWN_ID,
            start_time=attack_start,
            end_time=min(total_duration, attack_start + attack_duration),
            target_id=unknown_id,
            extra={"interval_ms": 50.0},
        ))
    elif attack_mode == ATTACK_PAYLOAD_TAMPERING:
        events.append(AttackEvent(
            attack_type=ATTACK_PAYLOAD_TAMPERING,
            start_time=attack_start,
            end_time=min(total_duration, attack_start + attack_duration),
            target_id=target_id,
        ))
    elif attack_mode == ATTACK_MISSING_MESSAGE:
        events.append(AttackEvent(
            attack_type=ATTACK_MISSING_MESSAGE,
            start_time=attack_start,
            end_time=min(total_duration, attack_start + attack_duration),
            target_id=target_id,
        ))
    elif attack_mode == ATTACK_MIXED:
        # Realistic schedule: space attacks across the duration with clean baseline gaps
        slot_len = max(0.5, total_duration / 8.0)
        t = slot_len
        if t + slot_len <= total_duration:
            events.append(AttackEvent(ATTACK_INJECTION, t, t + slot_len, target_id, {"interval_ms": 5.0}))
            t += slot_len * 1.5
        if t + slot_len <= total_duration:
            events.append(AttackEvent(ATTACK_UNKNOWN_ID, t, t + slot_len, unknown_id, {"interval_ms": 50.0}))
            t += slot_len * 1.5
        if t + slot_len <= total_duration:
            events.append(AttackEvent(ATTACK_PAYLOAD_TAMPERING, t, t + slot_len, target_id))
            t += slot_len * 1.5
        if t + slot_len * 0.8 <= total_duration:
            events.append(AttackEvent(ATTACK_MISSING_MESSAGE, t, min(total_duration - 0.1, t + slot_len), target_id))

    return events


def run_attack_simulation(
    cfg: Config,
    attack_mode: str,
    stop: threading.Event,
    sender: Optional[SocketCanSender],
    on_record: Callable[[Dict[str, object]], None],
    dry_run: bool = False,
    target_id: int = 0x100,
    unknown_id: int = 0x7FF,
    injection_interval_ms: float = 5.0,
    attack_start: float = 5.0,
    attack_duration: float = 5.0,
    logger=None,
) -> AttackSimStats:
    """Run normal traffic interleaved with configured attack behaviors."""
    if not dry_run and sender is None:
        raise RuntimeError("A sender is required unless dry_run=True")

    stats = AttackSimStats()
    gens = {m.can_id: PayloadGenerator(m, cfg.random_seed) for m in cfg.messages}
    by_id = cfg.id_lookup()
    rng = random.Random(f"{cfg.random_seed}:attacks")
    schedule_rng = random.Random(f"{cfg.random_seed}:schedule")
    jitter = cfg.jitter_percent / 100.0
    period = {m.can_id: (m.interval_ms / 1000.0) / cfg.rate_scale for m in cfg.messages}
    source = f"attack_traffic_simulator mode={attack_mode} seed={cfg.random_seed}"

    # Plan attack schedule
    events = build_attack_schedule(
        attack_mode=attack_mode,
        total_duration=cfg.runtime_seconds,
        target_id=target_id,
        unknown_id=unknown_id,
        attack_start=attack_start,
        attack_duration=attack_duration,
    )

    if logger:
        logger.info("Planned %d attack events for mode '%s':", len(events), attack_mode)
        for ev in events:
            logger.info("  [%5.1fs - %5.1fs] %s (target=%s)",
                        ev.start_time, ev.end_time, ev.attack_type,
                        format_can_id(ev.target_id) if ev.target_id is not None else "any")

    # Min-heap entries: (due_time, stream_id, is_normal, metadata)
    # stream_id helps keep distinct schedulers in order
    heap: List[Tuple[float, int, bool, Dict[str, object]]] = []

    # 1. Schedule normal periodic message streams
    for i, m in enumerate(cfg.messages):
        initial_due = i * 0.003
        heapq.heappush(heap, (initial_due, m.can_id, True, {}))

    # 2. Schedule standalone attack streams (injection and unknown_id)
    stream_counter = 1000
    for ev in events:
        if ev.attack_type == ATTACK_INJECTION:
            burst_dt = float(ev.extra.get("interval_ms", injection_interval_ms)) / 1000.0
            heapq.heappush(heap, (ev.start_time, ev.target_id or target_id, False, {
                "attack_type": ATTACK_INJECTION,
                "end_time": ev.end_time,
                "interval_s": burst_dt,
            }))
        elif ev.attack_type == ATTACK_UNKNOWN_ID:
            unk_dt = float(ev.extra.get("interval_ms", 50.0)) / 1000.0
            heapq.heappush(heap, (ev.start_time, ev.target_id or unknown_id, False, {
                "attack_type": ATTACK_UNKNOWN_ID,
                "end_time": ev.end_time,
                "interval_s": unk_dt,
            }))

    last_ts: Dict[int, float] = {}
    consecutive_failures = 0
    start_mono = time.monotonic()
    wall_start = DRY_RUN_EPOCH if dry_run else time.time()
    next_status = STATUS_EVERY_SECONDS

    while not stop.is_set() and heap:
        due, can_id, is_normal_stream, meta = heapq.heappop(heap)
        if due >= cfg.runtime_seconds:
            break

        # Check sleep delay if running live
        if not dry_run:
            delay = due - (time.monotonic() - start_mono)
            if delay > 0 and stop.wait(delay):
                break

        ts = (wall_start + due) if dry_run else time.time()
        curr_sim_time = due

        # Determine if any attack event is currently active for this message
        active_attacks = [
            ev for ev in events
            if ev.start_time <= curr_sim_time < ev.end_time
            and (ev.target_id is None or ev.target_id == can_id)
        ]
        active_types: Set[str] = {ev.attack_type for ev in active_attacks}

        # Handling Attack 4: Missing message suppression
        if is_normal_stream and ATTACK_MISSING_MESSAGE in active_types:
            stats.suppressed += 1
            # Re-schedule normal message for next period without sending
            next_due = due + period[can_id] * (1.0 + schedule_rng.uniform(-jitter, jitter))
            heapq.heappush(heap, (next_due, can_id, True, meta))
            continue

        label = 0
        attack_type_label = "normal"
        ecu_name = "unknown"
        msg_name = "unknown_frame"
        payload = b""

        if is_normal_stream:
            msg = by_id[can_id]
            ecu_name = msg.ecu_name
            msg_name = msg.name

            # Handling Attack 3: Payload tampering
            if ATTACK_PAYLOAD_TAMPERING in active_types:
                payload = build_tampered_payload(msg, rng)
                label = 1
                attack_type_label = ATTACK_PAYLOAD_TAMPERING
            else:
                payload = gens[can_id].next_payload()

            # Schedule next normal occurrence
            next_due = due + period[can_id] * (1.0 + schedule_rng.uniform(-jitter, jitter))
            heapq.heappush(heap, (next_due, can_id, True, meta))

        else:
            # Dedicated attack stream
            attack_type = meta.get("attack_type", "attack")
            label = 1
            attack_type_label = str(attack_type)

            if attack_type == ATTACK_INJECTION:
                msg = by_id.get(can_id)
                ecu_name = msg.ecu_name if msg else "injected_ecu"
                msg_name = (msg.name + "_burst") if msg else "injected_message"
                # Injected payload: either valid or rapid static/replay payload
                payload = gens[can_id].next_payload() if can_id in gens else b"\xDE\xAD\xBE\xEF\x00\x00\x00\x00"

            elif attack_type == ATTACK_UNKNOWN_ID:
                ecu_name = "rogue_device"
                msg_name = "unauthorized_frame"
                # 8 bytes anomalous payload
                payload = bytes([0xAA, 0x55, 0xDE, 0xAD, rng.randint(0, 255), rng.randint(0, 255), 0x00, 0x01])

            # Re-schedule next burst frame if still within attack window
            end_t = float(meta.get("end_time", 0.0))
            int_s = float(meta.get("interval_s", 0.01))
            next_due = due + int_s
            if next_due < end_t and next_due < cfg.runtime_seconds:
                heapq.heappush(heap, (next_due, can_id, False, meta))

        stats.generated += 1
        if label == 0:
            stats.normal_count += 1
        else:
            stats.attack_count += 1
            stats.per_attack_type[attack_type_label] += 1

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
                    raise RuntimeError(
                        f"{MAX_CONSECUTIVE_FAILURES} sends failed in a row ({exc.strerror})."
                    ) from exc

        if status in ("transmitted", "dry_run"):
            stats.per_id[can_id] += 1

        interval = (ts - last_ts[can_id]) if can_id in last_ts else None
        last_ts[can_id] = ts

        on_record({
            "timestamp": f"{ts:.6f}",
            "ecu_name": ecu_name,
            "message_name": msg_name,
            "can_id": can_id,
            "can_id_hex": format_can_id(can_id),
            "dlc": len(payload),
            "payload_hex": payload.hex().upper(),
            "interval_s": "" if interval is None else f"{interval:.6f}",
            "status": status,
            "source": source,
            "label": label,
            "attack_type": attack_type_label,
        })

        elapsed = due if dry_run else time.monotonic() - start_mono
        if logger and not dry_run and elapsed >= next_status:
            logger.info("running: %.0fs, gen=%d (normal=%d, attack=%d) failed=%d",
                        elapsed, stats.generated, stats.normal_count, stats.attack_count, stats.failed)
            next_status += STATUS_EVERY_SECONDS

    stats.interrupted = stop.is_set()
    return stats


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CAN-Sentinel Attack Traffic Simulator (Role B)")
    p.add_argument("--config", default="config/config.example.json", help="path to the JSON config")
    p.add_argument("--interface", help="vcan interface to send on (e.g. vcan0)")
    p.add_argument("--duration", type=float, help="simulation runtime in seconds")
    p.add_argument("--seed", type=int, help="random seed for reproducibility")
    p.add_argument("--output", help="output CSV dataset path")
    p.add_argument("--dry-run", action="store_true", help="generate dataset on virtual clock; no CAN interface needed")
    p.add_argument("--attack", choices=ALL_ATTACKS, default=ATTACK_MIXED,
                   help="attack mode to simulate (default: mixed)")
    p.add_argument("--attack-start", type=float, default=5.0, help="start time in seconds for single attack (default: 5.0)")
    p.add_argument("--attack-duration", type=float, default=5.0, help="duration in seconds for single attack (default: 5.0)")
    p.add_argument("--target-id", default="0x100", help="target CAN ID for injection/tampering/missing (default: 0x100)")
    p.add_argument("--unknown-id", default="0x7FF", help="unauthorized CAN ID for unknown_id attack (default: 0x7FF)")
    p.add_argument("--injection-interval-ms", type=float, default=5.0,
                   help="interval in ms between injection attack frames (default: 5.0)")
    p.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="console log level")
    return p.parse_args(argv)


def parse_id(val: str) -> int:
    val = val.strip()
    return int(val, 16) if val.lower().startswith("0x") else int(val)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        cfg = load_config(args.config)
        overrides = {}
        if args.interface:
            overrides["interface"] = validate_interface_name(args.interface, "--interface")
        if args.duration is not None:
            if args.duration <= 0:
                raise ConfigError("--duration must be > 0")
            overrides["runtime_seconds"] = args.duration
        if args.seed is not None:
            if args.seed < 0:
                raise ConfigError("--seed must be >= 0")
            overrides["random_seed"] = args.seed
        if args.output:
            overrides["sender_log_path"] = args.output
        if args.log_level:
            overrides["log_level"] = args.log_level
        cfg = dataclasses.replace(cfg, **overrides)
        target_id = parse_id(args.target_id)
        unknown_id = parse_id(args.unknown_id)
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ID PARSING ERROR: {exc}", file=sys.stderr)
        return 2

    log = setup_logging("attack_simulator", cfg.log_level, cfg.log_file)
    stop = threading.Event()

    def _request_stop(signum, _frame):
        log.info("stop requested (signal %d); finishing cleanly...", signum)
        stop.set()

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    sender = None
    sink = None
    out_path = args.output or "data/generated/attack_dataset.csv"

    try:
        if not args.dry_run:
            sender = SocketCanSender(cfg.interface)
        sink = CsvSink(out_path, ATTACK_SENDER_COLUMNS)
        mode_str = "DRY RUN (virtual clock)" if args.dry_run else f"transmitting on {cfg.interface}"
        log.info("Starting Attack Simulator: mode=%s, attack=%s, runtime=%.1fs, seed=%d",
                 mode_str, args.attack, cfg.runtime_seconds, cfg.random_seed)

        stats = run_attack_simulation(
            cfg=cfg,
            attack_mode=args.attack,
            stop=stop,
            sender=sender,
            on_record=sink.write,
            dry_run=args.dry_run,
            target_id=target_id,
            unknown_id=unknown_id,
            injection_interval_ms=args.injection_interval_ms,
            attack_start=args.attack_start,
            attack_duration=args.attack_duration,
            logger=log,
        )
    except CanInterfaceError as exc:
        log.error("Interface error: %s", exc)
        return 1
    except Exception as exc:
        log.error("Error running simulation: %s", exc)
        return 1
    finally:
        if sink is not None:
            sink.close()
        if sender is not None:
            sender.close()

    reason = "interrupted by user" if stats.interrupted else "runtime reached"
    print(f"\nAttack Simulation Finished ({reason}).")
    print(f"  Total frames generated : {stats.generated}")
    print(f"  Normal frames (label=0): {stats.normal_count}")
    print(f"  Attack frames (label=1): {stats.attack_count}")
    if stats.suppressed > 0:
        print(f"  Suppressed / missing   : {stats.suppressed} (missing_message attack)")
    if stats.per_attack_type:
        print("  Breakdown by attack type:")
        for atk, count in stats.per_attack_type.items():
            print(f"    - {atk:<20}: {count} frames")
    print(f"  Dataset saved to       : {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
