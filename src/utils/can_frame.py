"""Low-level SocketCAN helpers shared by the simulator and the monitor.

Python's standard library already speaks SocketCAN (socket.AF_CAN), so Week 1
needs no third-party CAN package.

A Classical CAN frame as the Linux kernel hands it to user space
(struct can_frame in <linux/can.h>) is always 16 bytes:

    bytes 0-3   can_id  (11-bit ID in the low bits, plus EFF/RTR/ERR flag bits)
    byte  4     data length (0-8)
    bytes 5-7   padding
    bytes 8-15  payload, zero-padded to 8 bytes
"""
from __future__ import annotations

import errno
import socket
import struct
from typing import NamedTuple

CAN_FRAME_FMT = "=IB3x8s"
CAN_FRAME_SIZE = struct.calcsize(CAN_FRAME_FMT)  # 16

CAN_EFF_FLAG = 0x80000000  # extended (29-bit) identifier
CAN_RTR_FLAG = 0x40000000  # remote transmission request
CAN_ERR_FLAG = 0x20000000  # error frame
CAN_SFF_MASK = 0x000007FF
CAN_EFF_MASK = 0x1FFFFFFF
MAX_STD_ID = CAN_SFF_MASK
MAX_DLC = 8


class CanInterfaceError(RuntimeError):
    """Raised with a human-readable explanation when a CAN socket cannot be used."""


class CanFrame(NamedTuple):
    can_id: int
    is_extended: bool
    is_rtr: bool
    is_error: bool
    dlc: int
    data: bytes


def format_can_id(can_id: int, extended: bool = False) -> str:
    return f"0x{can_id:08X}" if extended else f"0x{can_id:03X}"


def pack_frame(can_id: int, data: bytes) -> bytes:
    """Build the 16-byte kernel representation of a standard data frame."""
    if isinstance(can_id, bool) or not isinstance(can_id, int) or not 0 <= can_id <= MAX_STD_ID:
        raise ValueError(f"CAN ID {can_id!r} must be an integer in 0x000-0x7FF")
    if len(data) > MAX_DLC:
        raise ValueError(f"payload is {len(data)} bytes; Classical CAN allows at most 8")
    return struct.pack(CAN_FRAME_FMT, can_id, len(data), bytes(data).ljust(8, b"\x00"))


def unpack_frame(raw: bytes) -> CanFrame:
    """Parse and validate a frame read from a CAN_RAW socket."""
    if len(raw) != CAN_FRAME_SIZE:
        raise ValueError(
            f"unexpected frame size {len(raw)} bytes (expected {CAN_FRAME_SIZE}; "
            "CAN FD frames are not supported in Week 1)"
        )
    raw_id, dlc, data = struct.unpack(CAN_FRAME_FMT, raw)
    if dlc > MAX_DLC:
        raise ValueError(f"invalid data length {dlc} (Classical CAN maximum is 8)")
    is_ext = bool(raw_id & CAN_EFF_FLAG)
    is_rtr = bool(raw_id & CAN_RTR_FLAG)
    is_err = bool(raw_id & CAN_ERR_FLAG)
    can_id = raw_id & (CAN_EFF_MASK if (is_ext or is_err) else CAN_SFF_MASK)
    payload = b"" if is_rtr else data[:dlc]
    return CanFrame(can_id, is_ext, is_rtr, is_err, dlc, payload)


def open_can_socket(interface: str) -> socket.socket:
    """Open a raw SocketCAN socket bound to `interface`, with clear errors."""
    if not hasattr(socket, "AF_CAN"):
        raise CanInterfaceError(
            "this Python build has no SocketCAN support (socket.AF_CAN). "
            "SocketCAN is Linux-only; use Ubuntu, an Ubuntu VM, or a WSL2 kernel with CAN."
        )
    try:
        sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    except OSError as exc:
        raise CanInterfaceError(
            f"cannot create a CAN socket: {exc.strerror}. The kernel may lack CAN support "
            "(containers and some VMs/WSL kernels do). See docs/week1_troubleshooting.md."
        ) from exc
    try:
        sock.bind((interface,))
    except OSError as exc:
        sock.close()
        if exc.errno == errno.ENODEV:
            hint = f"interface '{interface}' does not exist. Create it with: sudo scripts/setup_vcan.sh up"
        elif exc.errno in (errno.EPERM, errno.EACCES):
            hint = f"permission denied binding to '{interface}'. Try running with sudo."
        else:
            hint = f"cannot bind to '{interface}': {exc.strerror}"
        raise CanInterfaceError(hint) from exc
    return sock
