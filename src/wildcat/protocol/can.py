"""CAN bus frame helpers.

Provides a minimal, correct CAN frame model (classic CAN + CAN FD data layout)
used by the protocol layer. Real framing per ISO 11898-1 is applied by the
driver implementations.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class CANFrame:
    """A CAN frame: arbitration ID, data, and flags."""

    arbitration_id: int
    data: bytes
    is_extended: bool = False
    is_remote: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.arbitration_id <= 0x1FFFFFFF:
            raise ValueError("arbitration_id must fit in 29 bits")
        if len(self.data) > 64:
            raise ValueError("data exceeds 64 bytes (CAN FD limit)")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CANFrame":
        """Parse a raw CAN frame (8-byte layout)."""
        if len(raw) < 8:
            raise ValueError("truncated CAN frame")
        is_extended = bool(raw[0] & 0x80)
        id_bits = raw[0] & 0x1FFFFFFF
        payload = raw[1:9]
        return cls(arbitration_id=id_bits, data=payload, is_extended=is_extended)

    def to_bytes(self) -> bytes:
        """Serialize to the 8-byte CAN frame layout."""
        raw = bytearray(8)
        if self.is_extended:
            raw[0] = 0xCF  # extended frame marker
            struct.pack_into(">I", raw, 1, self.arbitration_id & 0x1FFFFFFF)
        else:
            raw[0] = 0x9F  # standard frame marker
            struct.pack_into(">H", raw, 1, self.arbitration_id & 0x1FFF)
        raw[5:9] = self.data[:4]
        return bytes(raw)


class CANError(Exception):
    """Base exception for CAN operations."""
