"""Configuration loading and validation for CAN-Sentinel (Week 1).

All validation happens here, before any socket is opened, so a bad config
fails fast with a message that says exactly which setting is wrong.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class ConfigError(ValueError):
    """Raised when the configuration is missing, unreadable, or invalid."""


VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
# Week 1 is deliberately limited to *virtual* interfaces so the project can
# never be pointed at a physical CAN device by accident.
VIRTUAL_IFACE_RE = re.compile(r"^vcan[0-9]{1,3}$")
MAX_STD_ID = 0x7FF  # 11-bit identifier (Classical CAN, standard frame)
MAX_DLC = 8  # Classical CAN payload limit

TOP_LEVEL_KEYS = {
    "description", "interface", "runtime_seconds", "random_seed", "rate_scale",
    "jitter_percent", "log_level", "log_file", "monitor_log_file",
    "sender_log_path", "observed_dataset_path", "ecus",
}
ECU_KEYS = {"name", "messages"}
MESSAGE_KEYS = {"name", "can_id", "interval_ms", "dlc", "signals", "counter_byte"}
SIGNAL_KEYS = {"name", "start_byte", "size", "initial", "min", "max", "max_step"}


@dataclass(frozen=True)
class SignalDef:
    name: str
    start_byte: int
    size: int  # bytes: 1 or 2 (big-endian, unsigned)
    initial: int
    minimum: int
    maximum: int
    max_step: int  # largest change between two successive messages


@dataclass(frozen=True)
class MessageDef:
    ecu_name: str
    name: str
    can_id: int
    interval_ms: int
    dlc: int
    signals: Tuple[SignalDef, ...]
    counter_byte: Optional[int]


@dataclass(frozen=True)
class Config:
    interface: str
    runtime_seconds: float
    random_seed: int
    rate_scale: float
    jitter_percent: float
    log_level: str
    log_file: str
    monitor_log_file: str
    sender_log_path: str
    observed_dataset_path: str
    messages: Tuple[MessageDef, ...]

    def id_lookup(self) -> Dict[int, MessageDef]:
        return {m.can_id: m for m in self.messages}


# ---------------------------------------------------------------- helpers
def validate_interface_name(name: Any, where: str = "interface") -> str:
    if not isinstance(name, str) or not VIRTUAL_IFACE_RE.match(name):
        raise ConfigError(
            f"{where}: {name!r} is not allowed. Week 1 only supports virtual "
            "CAN interfaces named vcan0, vcan1, ... (never a physical device)."
        )
    return name


def _as_int(value: Any, where: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{where}: expected an integer, got {value!r}")
    if not lo <= value <= hi:
        raise ConfigError(f"{where}: {value} is out of range [{lo}, {hi}]")
    return value


def _as_float(value: Any, where: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{where}: expected a number, got {value!r}")
    if not lo <= value <= hi:
        raise ConfigError(f"{where}: {value} is out of range [{lo}, {hi}]")
    return float(value)


def _as_str(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}: expected a non-empty string, got {value!r}")
    return value


def _as_can_id(value: Any, where: str) -> int:
    if isinstance(value, str):
        try:
            value = int(value, 0)  # accepts "0x100" or "256"
        except ValueError:
            raise ConfigError(f"{where}: {value!r} is not a valid number") from None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{where}: expected a CAN ID, got {value!r}")
    if not 0 <= value <= MAX_STD_ID:
        raise ConfigError(
            f"{where}: CAN ID 0x{value:X} is outside the 11-bit range 0x000-0x7FF"
        )
    return value


def _check_keys(d: Any, allowed: set, where: str) -> Dict[str, Any]:
    if not isinstance(d, dict):
        raise ConfigError(f"{where}: expected an object, got {type(d).__name__}")
    unknown = sorted(set(d) - allowed)
    if unknown:
        raise ConfigError(
            f"{where}: unknown setting(s) {unknown}. Allowed: {sorted(allowed)}"
        )
    return d


def _parse_signal(raw: Any, where: str, dlc: int) -> SignalDef:
    raw = _check_keys(raw, SIGNAL_KEYS, where)
    for key in ("name", "start_byte", "size", "initial", "min", "max"):
        if key not in raw:
            raise ConfigError(f"{where}: missing required setting '{key}'")
    name = _as_str(raw["name"], f"{where}.name")
    size = _as_int(raw["size"], f"{where}.size", 1, 2)
    start = _as_int(raw["start_byte"], f"{where}.start_byte", 0, MAX_DLC - 1)
    if start + size > dlc:
        raise ConfigError(
            f"{where}: signal '{name}' needs bytes {start}..{start + size - 1} "
            f"but the message dlc is only {dlc}"
        )
    type_max = 256 ** size - 1
    minimum = _as_int(raw["min"], f"{where}.min", 0, type_max)
    maximum = _as_int(raw["max"], f"{where}.max", 0, type_max)
    if minimum > maximum:
        raise ConfigError(f"{where}: min ({minimum}) is greater than max ({maximum})")
    initial = _as_int(raw["initial"], f"{where}.initial", minimum, maximum)
    max_step = _as_int(raw.get("max_step", 1), f"{where}.max_step", 0, 65535)
    return SignalDef(name, start, size, initial, minimum, maximum, max_step)


def _parse_message(raw: Any, where: str, ecu_name: str) -> MessageDef:
    raw = _check_keys(raw, MESSAGE_KEYS, where)
    for key in ("name", "can_id", "interval_ms", "dlc"):
        if key not in raw:
            raise ConfigError(f"{where}: missing required setting '{key}'")
    name = _as_str(raw["name"], f"{where}.name")
    can_id = _as_can_id(raw["can_id"], f"{where}.can_id")
    interval_ms = _as_int(raw["interval_ms"], f"{where}.interval_ms", 1, 60000)
    dlc = _as_int(raw["dlc"], f"{where}.dlc", 0, MAX_DLC)

    signals_raw = raw.get("signals", [])
    if not isinstance(signals_raw, list):
        raise ConfigError(f"{where}.signals: expected a list")
    signals = tuple(
        _parse_signal(s, f"{where}.signals[{i}]", dlc) for i, s in enumerate(signals_raw)
    )

    counter_byte = raw.get("counter_byte")
    if counter_byte is not None:
        counter_byte = _as_int(counter_byte, f"{where}.counter_byte", 0, MAX_DLC - 1)
        if counter_byte >= dlc:
            raise ConfigError(
                f"{where}.counter_byte: byte {counter_byte} is outside dlc {dlc}"
            )

    used = set()
    claims = [(s.name, range(s.start_byte, s.start_byte + s.size)) for s in signals]
    if counter_byte is not None:
        claims.append(("counter_byte", range(counter_byte, counter_byte + 1)))
    for label, byte_range in claims:
        for b in byte_range:
            if b in used:
                raise ConfigError(f"{where}: byte {b} is used twice (see '{label}')")
            used.add(b)
    return MessageDef(ecu_name, name, can_id, interval_ms, dlc, signals, counter_byte)


# ------------------------------------------------------------------ public
def parse_config(raw: Any) -> Config:
    raw = _check_keys(raw, TOP_LEVEL_KEYS, "config")
    for key in ("interface", "ecus"):
        if key not in raw:
            raise ConfigError(f"config: missing required setting '{key}'")

    interface = validate_interface_name(raw["interface"])
    log_level = _as_str(raw.get("log_level", "INFO"), "log_level").upper()
    if log_level not in VALID_LOG_LEVELS:
        raise ConfigError(f"log_level: {log_level!r} must be one of {VALID_LOG_LEVELS}")

    ecus = raw["ecus"]
    if not isinstance(ecus, list) or not ecus:
        raise ConfigError("ecus: expected a non-empty list")

    messages = []
    seen_ids: Dict[int, str] = {}
    seen_names = set()
    for i, ecu in enumerate(ecus):
        where = f"ecus[{i}]"
        ecu = _check_keys(ecu, ECU_KEYS, where)
        ecu_name = _as_str(ecu.get("name"), f"{where}.name")
        if ecu_name in seen_names:
            raise ConfigError(f"{where}.name: duplicate ECU name {ecu_name!r}")
        seen_names.add(ecu_name)
        msgs = ecu.get("messages")
        if not isinstance(msgs, list) or not msgs:
            raise ConfigError(f"{where}.messages: expected a non-empty list")
        for j, m in enumerate(msgs):
            msg = _parse_message(m, f"{where}.messages[{j}]", ecu_name)
            if msg.can_id in seen_ids:
                raise ConfigError(
                    f"{where}.messages[{j}].can_id: 0x{msg.can_id:03X} already used "
                    f"by '{seen_ids[msg.can_id]}'"
                )
            seen_ids[msg.can_id] = f"{ecu_name}/{msg.name}"
            messages.append(msg)

    return Config(
        interface=interface,
        runtime_seconds=_as_float(raw.get("runtime_seconds", 30), "runtime_seconds", 0.1, 86400),
        random_seed=_as_int(raw.get("random_seed", 42), "random_seed", 0, 2**32 - 1),
        rate_scale=_as_float(raw.get("rate_scale", 1.0), "rate_scale", 0.1, 10.0),
        jitter_percent=_as_float(raw.get("jitter_percent", 2.0), "jitter_percent", 0.0, 20.0),
        log_level=log_level,
        log_file=_as_str(raw.get("log_file", "logs/simulator.log"), "log_file"),
        monitor_log_file=_as_str(raw.get("monitor_log_file", "logs/monitor.log"), "monitor_log_file"),
        sender_log_path=_as_str(raw.get("sender_log_path", "data/generated/sender_log.csv"), "sender_log_path"),
        observed_dataset_path=_as_str(
            raw.get("observed_dataset_path", "data/generated/observed_normal_traffic.csv"),
            "observed_dataset_path",
        ),
        messages=tuple(messages),
    )


def load_config(path: str) -> Config:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except OSError as exc:
        raise ConfigError(f"cannot read config file {path}: {exc.strerror}") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"{path} is not valid JSON (line {exc.lineno}, column {exc.colno}): {exc.msg}"
        ) from exc
    return parse_config(raw)
