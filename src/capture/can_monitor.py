#!/usr/bin/env python3
"""Independent CAN traffic monitor for CAN-Sentinel, Week 1.

Reads frames from a virtual CAN interface with a raw SocketCAN socket, prints
them, and (optionally) saves them as the OBSERVED dataset.

    python3 -m src.capture.can_monitor                      # just print
    python3 -m src.capture.can_monitor --config config/config.example.json --save
    python3 -m src.capture.can_monitor --output data/generated/my_capture.csv --duration 20

Stop with Ctrl+C. The CSV is flushed and the socket closed on exit.
"""
from __future__ import annotations

import argparse
import dataclasses
import errno
import signal
import socket
import sys
import threading
import time
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional

from src.utils.can_frame import CanInterfaceError, format_can_id, open_can_socket, unpack_frame
from src.utils.config import Config, ConfigError, MessageDef, load_config, validate_interface_name
from src.utils.dataset import OBSERVED_COLUMNS, CsvSink
from src.utils.logging_setup import setup_logging


@dataclasses.dataclass
class MonitorStats:
    data_frames: int = 0
    invalid: int = 0
    error_frames: int = 0
    per_id: Counter = dataclasses.field(default_factory=Counter)
    interrupted: bool = False


def frame_to_row(frame, observed_at: float, last_seen: Dict[int, float],
                 names: Dict[int, MessageDef], interface: str) -> Dict[str, object]:
    """Pure function: turn a parsed frame into one OBSERVED-dataset row."""
    msg = names.get(frame.can_id) if not frame.is_extended else None
    prev = last_seen.get(frame.can_id)
    last_seen[frame.can_id] = observed_at
    flags = "+".join(f for f, on in (("EXT", frame.is_extended), ("RTR", frame.is_rtr)) if on)
    return {
        "observed_timestamp": f"{observed_at:.6f}",
        "can_id": frame.can_id,
        "can_id_hex": format_can_id(frame.can_id, frame.is_extended),
        "ecu_name": msg.ecu_name if msg else "unknown",
        "message_name": msg.name if msg else "unknown",
        "dlc": frame.dlc,
        "payload_hex": frame.data.hex().upper(),
        "inter_arrival_s": "" if prev is None else f"{observed_at - prev:.6f}",
        "frame_flags": flags,
        "source": f"observed:{interface} (python monitor)",
    }


def monitor(sock: socket.socket, stop: threading.Event, interface: str,
            names: Dict[int, MessageDef], sink: Optional[CsvSink], quiet: bool,
            max_frames: int, duration: Optional[float], logger) -> MonitorStats:
    stats = MonitorStats()
    last_seen: Dict[int, float] = {}
    sock.settimeout(0.5)  # wake up regularly so Ctrl+C / --duration are noticed
    deadline = None if duration is None else time.monotonic() + duration

    while not stop.is_set():
        if deadline is not None and time.monotonic() >= deadline:
            break
        if max_frames and stats.data_frames >= max_frames:
            break
        try:
            raw = sock.recv(128)  # larger than 16 so an oversized (CAN FD) frame is detected, not truncated
        except socket.timeout:
            continue
        except InterruptedError:
            continue
        except OSError as exc:
            if exc.errno == errno.ENETDOWN:
                logger.error("interface %s went down", interface)
            else:
                logger.error("read error: %s", exc.strerror)
            break
        observed_at = time.time()

        try:
            frame = unpack_frame(raw)
        except ValueError as exc:
            stats.invalid += 1
            logger.warning("ignoring invalid frame (%s): %s", exc, raw.hex(" "))
            continue
        if frame.is_error:
            stats.error_frames += 1
            logger.warning("error frame received (ID field 0x%08X)", frame.can_id)
            continue

        row = frame_to_row(frame, observed_at, last_seen, names, interface)
        stats.data_frames += 1
        stats.per_id[frame.can_id] += 1
        if sink is not None:
            sink.write(row)
        logger.debug("%s [%d] %s", row["can_id_hex"], frame.dlc, frame.data.hex(" ").upper())
        if not quiet:
            stamp = datetime.fromtimestamp(observed_at).strftime("%H:%M:%S.%f")[:-3]
            delta = "" if row["inter_arrival_s"] == "" else f"+{float(row['inter_arrival_s']) * 1000:.1f}ms"
            print(f"{stamp}  {row['can_id_hex']:<10} [{frame.dlc}]  {frame.data.hex(' ').upper():<23}  "
                  f"{row['ecu_name']}/{row['message_name']}  {delta} {row['frame_flags']}".rstrip())
    stats.interrupted = stop.is_set()
    return stats


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Print and optionally save frames seen on a virtual CAN interface.")
    p.add_argument("-i", "--interface", help="interface to read (vcanN only). Default: from --config, else vcan0")
    p.add_argument("--config", help="config file; used for the interface, ECU-name lookup and --save path")
    p.add_argument("--save", action="store_true", help="save the observed dataset to observed_dataset_path from --config")
    p.add_argument("-o", "--output", help="save the observed dataset to this CSV path")
    p.add_argument("--duration", type=float, help="stop after this many seconds")
    p.add_argument("--count", type=int, default=0, help="stop after this many data frames (0 = unlimited)")
    p.add_argument("--quiet", action="store_true", help="do not print each frame")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--log-file", help="log file path (default: monitor_log_file from --config, else logs/monitor.log)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    cfg: Optional[Config] = None
    try:
        if args.config:
            cfg = load_config(args.config)
        if args.save and cfg is None:
            raise ConfigError("--save needs --config (or use --output PATH)")
        interface = validate_interface_name(args.interface or (cfg.interface if cfg else "vcan0"), "interface")
        if args.duration is not None and args.duration <= 0:
            raise ConfigError("--duration must be greater than 0")
        if args.count < 0:
            raise ConfigError("--count must be 0 or greater")
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    output = args.output or (cfg.observed_dataset_path if (args.save and cfg) else None)
    log_file = args.log_file or (cfg.monitor_log_file if cfg else "logs/monitor.log")
    log = setup_logging("monitor", args.log_level, log_file)
    names = cfg.id_lookup() if cfg else {}

    stop = threading.Event()

    def _request_stop(signum, _frame):
        stop.set()

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    sock = None
    sink = None
    try:
        sock = open_can_socket(interface)
        if output:
            sink = CsvSink(output, OBSERVED_COLUMNS)
        log.info("listening on %s%s (Ctrl+C to stop)", interface, f", saving to {output}" if output else "")
        stats = monitor(sock, stop, interface, names, sink, args.quiet, args.count, args.duration, log)
    except CanInterfaceError as exc:
        log.error("%s", exc)
        return 1
    except OSError as exc:
        log.error("file error: %s (%s)", exc.strerror, getattr(exc, "filename", ""))
        return 1
    finally:
        if sink is not None:
            sink.close()
        if sock is not None:
            sock.close()

    print(f"\nMonitor stopped ({'interrupted' if stats.interrupted else 'finished'}).")
    print(f"  observed data frames : {stats.data_frames}")
    print(f"  invalid frames       : {stats.invalid}")
    print(f"  error frames         : {stats.error_frames}")
    for can_id in sorted(stats.per_id):
        print(f"    {format_can_id(can_id)}: {stats.per_id[can_id]}")
    if output:
        print(f"  dataset saved to     : {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
