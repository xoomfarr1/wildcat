"""J1850 protocol (ISO 16848) — VPW and PWM variants."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from wildcat.connectors.base import Connector
from wildcat.protocol.can import _Protocol

__all__ = [
    "J1850Encoder",
    "J1850Error",
    "J1850Frame",
    "J1850Protocol",
    "J1850TimeoutError",
]

_J1850_MODES = {"pwm": 0, "vpw": 1}


def _even_parity(byte: int) -> int:
    """Return *byte* with an even-parity LSB appended."""
    return byte | ((byte).bit_count() & 1)


class J1850Error(Exception):
    """Base exception for J1850 operations."""


class J1850FrameError(J1850Error):
    """Raised when a J1850 frame is malformed."""


class J1850ProtocolError(J1850Error):
    """Raised for J1850 protocol-level errors."""


class J1850TimeoutError(J1850Error):
    """Raised when no frame arrives within the timeout."""


@dataclass(frozen=True)
class J1850Frame:
    """A J1850 frame.

    Attributes:
        arbitration_id: identifier (11-bit for PWM, byte for VPW).
        data: payload bytes (0..8).
        mode: ``"pwm"`` or ``"vpw"``.
        is_extended: True if the identifier is 29-bit (extended).
        is_remote: True for a remote frame.
    """

    arbitration_id: int
    data: bytes = b""
    is_extended: bool = False
    is_remote: bool = False
    mode: str = "pwm"

    def __post_init__(self) -> None:
        if self.mode not in _J1850_MODES:
            raise J1850FrameError(f"mode must be one of {sorted(_J1850_MODES)}")
        if not 0 <= self.arbitration_id <= 0x1FFFFFFF:
            raise J1850FrameError("arbitration_id must fit in 29 bits")
        if len(self.data) > 64:
            raise J1850FrameError("data exceeds 64 bytes")

    @property
    def mode_byte(self) -> int:
        """0 for PWM, 1 for VPW."""
        return _J1850_MODES[self.mode]

    @property
    def dlc(self) -> int:
        return len(self.data)

    # -- canonical wire format -------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialize to the protocol-layer canonical J1850 wire format.

        Byte 0: ``(dlc << 1) | mode``
        Bytes 1..: identifier + data (per variant).
        """
        data = self.data
        if self.is_extended and self.mode == "pwm":
            # Extended PWM: identifier occupies up to 4 bytes (29-bit).
            raw = bytearray(1 + 4 + len(data))
            raw[0] = (len(data) << 1) | self.mode_byte
            raw[1] = (self.arbitration_id >> 24) & 0xFF
            raw[2] = (self.arbitration_id >> 16) & 0xFF
            raw[3] = (self.arbitration_id >> 8) & 0xFF
            raw[4] = self.arbitration_id & 0xFF
            raw[5:] = data[:8]
            return bytes(raw[: 5 + len(data)])
        # standard PWM or any VPW: 1 header byte + data
        raw = bytearray(1 + len(data))
        raw[0] = (len(data) << 1) | self.mode_byte
        raw[1:] = data[:8]
        return bytes(raw)

    @classmethod
    def from_bytes(cls, raw: bytes) -> J1850Frame:
        """Parse a canonical J1850 wire frame."""
        if len(raw) < 1:
            raise J1850FrameError("truncated J1850 frame")
        mode = raw[0] & 1
        dlc = (raw[0] >> 1) & 0x0F
        mode_str = "pwm" if mode == 0 else "vpw"
        if dlc == 0 and len(raw) > 1:
            dlc = len(raw) - 1
        if len(raw) < 1 + dlc:
            raise J1850FrameError("truncated J1850 data payload")
        data = raw[1:1 + dlc]
        return cls(
            arbitration_id=0,
            data=data,
            mode=mode_str,
            is_extended=False,
            is_remote=False,
        )


class J1850Encoder:
    """Voltage-level (PWM/VPW) encoding and decoding.

    The physical-layer voltage coding is driver-owned; this class provides
    the protocol-layer bitstream representations for testing and
    interoperability:

    * PWM -- Manchester encoded.  Each bit occupies two half-bits; a ``1``
      rises then falls, a ``0`` falls then rises.
    * VPW -- dominant/recessive.  Each bit is a single level (0=dominant,
      1=recessive, MSB-first).
    """

    @staticmethod
    def encode_pwm(data: bytes) -> bytearray:
        """Manchester-encode *data* into a voltage-level stream (1=high)."""
        levels = bytearray()
        for byte in data:
            for i in range(7, -1, -1):
                bit = (byte >> i) & 1
                levels.append(bit)      # rising
                levels.append(1 - bit)  # falling
        return levels

    @staticmethod
    def decode_pwm(levels: Iterable[int]) -> bytes:
        """Demodulate a Manchester level stream into bytes (MSB-first)."""
        levels = list(levels)
        if len(levels) % 2:
            raise J1850FrameError("PWM stream length must be even")
        out = bytearray()
        for high, low in zip(levels[0::2], levels[1::2]):
            bit = 0
            if low == 1 and high == 0:
                bit = 0
            elif high == 1 and low == 0:
                bit = 1
            else:
                raise J1850FrameError("invalid PWM cell (level must transition once)")
            out.append(bit)
        # NOTE: the bits above are collected LSB-first per byte; convert.
        return J1850Encoder._bits_to_bytes(out)

    @staticmethod
    def _bits_to_bytes(bits: Iterable[int]) -> bytes:
        out = bytearray()
        value = 0
        count = 0
        for b in bits:
            value = (value << 1) | b
            count += 1
            if count == 8:
                out.append(value)
                value = 0
                count = 0
        if count:
            out.append(value << (8 - count))
        return bytes(out)

    @staticmethod
    def encode_vpw(data: bytes) -> bytearray:
        """VPW-encode *data* into a dominant/recessive level stream."""
        levels = bytearray()
        for byte in data:
            for i in range(7, -1, -1):
                bit = (byte >> i) & 1
                levels.append(bit)  # 1 = recessive, 0 = dominant
        return levels

    @staticmethod
    def decode_vpw(levels: Iterable[int]) -> bytes:
        """Demodulate a VPW level stream into bytes (MSB-first)."""
        return J1850Encoder._bits_to_bytes(list(levels))

    @classmethod
    def encode(cls, frame: J1850Frame) -> bytearray:
        """Encode a ``J1850Frame`` to a voltage-level stream."""
        return cls.encode_pwm(frame.data) if frame.mode == "pwm" else cls.encode_vpw(frame.data)

    @classmethod
    def decode(cls, levels: Iterable[int]) -> bytes:
        """Best-effort demodulate a level stream (PWM preferred, VPW fallback)."""
        try:
            return cls.decode_pwm(levels)
        except J1850FrameError:
            return cls.decode_vpw(levels)


class J1850Protocol(_Protocol):
    """J1850 protocol (ISO 16848) over a single-wire/paired-wire connector.

    :class:`J1850Protocol` is the command/response layer.  The physical
    voltage coding (PWM Manchester / VPW pulse width) is produced by
    :class:`J1850Encoder` and consumed by an underlying driver.  The
    protocol layer provides frame parsing, error handling, and a bitstream
    interface for both variants.
    """

    def __init__(self, connector: Connector, timeout: float = 1.0, mode: str = "pwm") -> None:
        super().__init__(connector, timeout)
        if mode not in _J1850_MODES:
            raise J1850FrameError(f"mode must be one of {sorted(_J1850_MODES)}")
        self.mode = mode

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if value not in _J1850_MODES:
            raise J1850FrameError(f"mode must be one of {sorted(_J1850_MODES)}")
        self._mode = value

    def send(self, frame: J1850Frame) -> None:
        """Serialize and transmit a J1850 frame."""
        if not isinstance(frame, J1850Frame):
            raise J1850Error("expected a J1850Frame")
        if self.mode != frame.mode:
            raise J1850Error(f"expected mode '{self.mode}', got '{frame.mode}'")
        self.connector.send(frame.to_bytes())

    def recv(self, timeout: float = 1.0) -> J1850Frame:
        """Receive and parse a J1850 frame."""
        raw = self._read(timeout)
        if not raw:
            raise J1850TimeoutError("no J1850 frame received")
        return J1850Frame.from_bytes(raw)

    def send_bitstream(self, levels: bytes) -> None:
        """Transmit a voltage-level stream directly (encoder output)."""
        self.connector.send(bytes(levels))

    def recv_bitstream(self, timeout: float = 1.0) -> bytes:
        """Receive raw voltage levels and demodulate to bytes."""
        raw = self._read(timeout)
        if not raw:
            raise J1850TimeoutError("no J1850 frame received")
        return J1850Encoder.decode(raw)

    def _read(self, timeout: float) -> bytes:
        chunks = []
        try:
            while True:
                chunk = self.connector.recv(timeout)
                if not chunk:
                    break
                chunks.append(chunk)
        except (OSError, TypeError, ValueError) as exc:
            raise J1850Error(f"J1850 read failed: {exc}") from exc
        return b"".join(chunks)
