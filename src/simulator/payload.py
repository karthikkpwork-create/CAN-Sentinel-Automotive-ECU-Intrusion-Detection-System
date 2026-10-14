"""Deterministic synthetic payload generation (no CAN or socket code here)."""
from __future__ import annotations

import random

from src.utils.config import MessageDef


class PayloadGenerator:
    """Produces the payload bytes for ONE message definition.

    Each signal does a small bounded random walk (value changes by at most
    `max_step` per message) and is stored big-endian. An optional rolling
    counter byte increments 0..255. Every message gets its own random stream
    seeded from (global seed, CAN ID), so adding or removing another message
    never changes this message's values.
    """

    def __init__(self, message: MessageDef, seed: int):
        self._msg = message
        self._rng = random.Random(f"{seed}:{message.can_id}")
        self._values = {s.name: s.initial for s in message.signals}
        self._counter = 0
        self._first = True

    def next_payload(self) -> bytes:
        buf = bytearray(self._msg.dlc)
        for sig in self._msg.signals:
            if not self._first:
                step = self._rng.randint(-sig.max_step, sig.max_step)
                value = self._values[sig.name] + step
                value = max(sig.minimum, min(sig.maximum, value))
                self._values[sig.name] = value
            buf[sig.start_byte:sig.start_byte + sig.size] = self._values[sig.name].to_bytes(sig.size, "big")
        if self._msg.counter_byte is not None:
            buf[self._msg.counter_byte] = self._counter % 256
            self._counter += 1
        self._first = False
        return bytes(buf)
