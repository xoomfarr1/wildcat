"""KWP2000 protocol (ISO 9141-2) over a serial/LowSpeed connector."""

from __future__ import annotations

from dataclasses import dataclass

from wildcat.connectors.base import Connector
from wildcat.protocol.can import _Protocol

__all__ = [
    "KWP2000Error",
    "KWP2000Frame",
    "KWP2000Protocol",
    "KWP2000TimeoutError",
]

# ISO 9141-2 PIDs
PID_SOF = 0x30        # Start of Frame
PID_ADDRESS = 0x31    # Address frame (wait response)
PID_PID = 0x32        # Protocol ID frame
PID_DATA = 0x33       # Data frame
PID_STATUS1 = 0x34    # Single-byte status
PID_STATUS2 = 0x35    # Multi-byte status / error frame
PID_END = 0x36        # End of frame

_KWP2000_FRAME_TYPES = {
    "start": PID_SOF,
    "address": PID_ADDRESS,
    "pid": PID_PID,
    "data": PID_DATA,
    "status": PID_STATUS1,
    "end": PID_END,
}

# Status byte encodings (single-byte status, SS)
STATUS_OK = 0x00
STATUS_NOT_READY = 0x11
STATUS_ERROR = 0x14
STATUS_NO_CONNECTION = 0x15
STATUS_PROTECTION = 0x17
STATUS_BAD_BLOCK = 0x19


def _even_parity(byte: int) -> int:
    """Return *byte* with an even-parity LSB appended.

    ISO 9141-2 KWP2000 characters carry eight data bits plus a parity LSB.
    The stored ECC byte is the identifier byte with its LSB as the parity
    bit.  For identifiers carrying an even number of 1 bits the LSB is
    cleared, so the transmitted character keeps an odd count of 1 bits.
    """
    count = (byte).bit_count()
    return byte ^ ((count & 1) ^ 1)


class KWP2000Error(Exception):
    """Base exception for KWP2000 operations."""


class Kwp2000FrameError(KWP2000Error):
    """Raised when a KWP2000 frame is malformed."""


class Kwp2000ProtocolError(KWP2000Error):
    """Raised for KWP2000 protocol-level errors (status responses)."""


class KWP2000TimeoutError(KWP2000Error):
    """Raised when no frame arrives within the timeout."""


@dataclass(frozen=True)
class KWP2000Frame:
    """A KWP2000 (ISO 9141-2) frame.

    ``frame_type`` is one of the PID constants.  ``wire`` is the raw byte
    sequence (without the 9-bit start-of-frame) that is transmitted.
    """

    frame_type: int
    data: bytes = b""
    checksum: int | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KWP2000Frame):
            return NotImplemented
        return self.frame_type == other.frame_type and self.data == other.data

    def __hash__(self) -> int:
        return hash((self.frame_type, self.data))

    def __post_init__(self) -> None:
        if self.frame_type not in _KWP2000_FRAME_TYPES.values():
            raise Kwp2000FrameError(f"unknown frame type 0x{self.frame_type:02x}")
        if len(self.data) > 255:
            raise Kwp2000FrameError("data exceeds 255 bytes")

    @property
    def frame_type_name(self) -> str:
        for name, pid in _KWP2000_FRAME_TYPES.items():
            if pid == self.frame_type:
                return name
        return "unknown"

    def to_bytes(self) -> bytes:
        """Serialize to the byte payload transmitted on the serial line."""
        pid = self.frame_type
        ecc = _even_parity(pid)
        check = pid ^ ecc
        for b in self.data:
            check ^= b
        check = _even_parity(check)
        return bytes([pid, ecc, *self.data, check])

    @classmethod
    def parse(cls, wire: bytes) -> KWP2000Frame:
        """Parse a raw KWP2000 byte payload into a frame."""
        if len(wire) < 3:
            raise Kwp2000FrameError("truncated KWP2000 frame")
        pid, ecc = wire[0], wire[1]
        data = wire[2:-1]
        checksum = wire[-1]
        if not (ecc == _even_parity(pid)):
            raise Kwp2000FrameError("invalid ECC parity in KWP2000 frame")
        # Recompute expected checksum from data
        expected = pid ^ ecc
        for b in data:
            expected ^= b
        expected = _even_parity(expected)
        if checksum != expected:
            raise KWP2000TimeoutError("invalid checksum in KWP2000 frame")
        return cls(frame_type=pid, data=data, checksum=checksum)


class KWP2000Protocol(_Protocol):
    """KWP2000 (ISO 9141-2) protocol over a serial connector.

    Operates on a state machine that targets the standard sequence of
    frames: start -> address -> pid -> data -> status.

    Usage::

        proto = KWP2000Protocol(connector)
        proto.send(KWP2000Frame(pid=PID_DATA, data=b"\x02\x01\x00"))
        frame = proto.recv()
    """

    def __init__(self, connector: Connector, timeout: float = 1.0) -> None:
        super().__init__(connector, timeout)
        self._pending: KWP2000Frame | None = None

    def send(self, frame: KWP2000Frame) -> None:
        """Serialize and transmit a single KWP2000 frame."""
        if not isinstance(frame, KWP2000Frame):
            raise KWP2000Error("expected a KWP2000Frame")
        self.connector.send(frame.to_bytes())

    def recv(self, timeout: float = 1.0) -> KWP2000Frame:
        """Receive and parse a single KWP2000 frame."""
        buf = bytearray()
        while True:
            raw = self._read(timeout)
            if not raw:
                raise KWP2000TimeoutError("no KWP2000 frame received")
            buf.extend(raw)
            try:
                return KWP2000Frame.parse(bytes(buf))
            except KWP2000TimeoutError:
                raise
            except Kwp2000FrameError:
                # Truncated or malformed frame; keep waiting for more bytes.
                continue

    def _read(self, timeout: float) -> bytes:
        try:
            return self.connector.recv(timeout)
        except (OSError, TypeError, ValueError) as exc:
            raise KWP2000Error(f"KWP2000 read failed: {exc}") from exc

    # -- frame builders ---------------------------------------------------

    @staticmethod
    def start_frame() -> KWP2000Frame:
        """Build a start-of-frame (SOF) frame."""
        return KWP2000Frame(frame_type=PID_SOF)

    @staticmethod
    def address_frame(address: int = 0x20) -> KWP2000Frame:
        """Build an address frame (SSD)."""
        if not 0x20 <= address <= 0x3F:
            raise ValueError("address must be in the 0x20..0x3F range")
        return KWP2000Frame(frame_type=PID_ADDRESS, data=bytes([address]))

    @staticmethod
    def pid_frame(pid: int = 0x20) -> KWP2000Frame:
        """Build a PID frame."""
        if not 0x20 <= pid <= 0x3F:
            raise ValueError("PID must be in the 0x20..0x3F range")
        return KWP2000Frame(frame_type=PID_PID, data=bytes([pid]))

    @staticmethod
    def data_frame(data: bytes) -> KWP2000Frame:
        """Build a data frame."""
        return KWP2000Frame(frame_type=PID_DATA, data=data)

    @staticmethod
    def status_frame(status: int = STATUS_OK) -> KWP2000Frame:
        """Build a single-byte status frame."""
        if not 0x00 <= status <= 0xFF:
            raise ValueError("status must be 0x00..0xFF")
        return KWP2000Frame(frame_type=PID_STATUS1, data=bytes([status]))
