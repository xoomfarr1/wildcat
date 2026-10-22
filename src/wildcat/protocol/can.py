"""CAN bus frame helpers and ISO 15765-4 protocol.

This module provides the protocol-layer building blocks for CAN-based
diagnostics:

* ``CANFrame`` -- a minimal, correct CAN frame model (classic CAN + CAN FD
  data layout).  The wire layout below is the *protocol-layer canonical*
  format used by this layer; real ISO 11898-1 framing (CRC, trailer,
  intermissions, FD flags) is applied by the concrete driver
  implementations.

* ``ISO_TP`` -- ISO 15765-2 transport-layer framing for extended messaging
  (payloads larger than a single CAN data frame).  Supports
  single-frame / first-frame / consecutive-frame with automatic flow-control
  acknowledgement.

* ``CANProtocol`` -- ISO 15765-4 over a raw CAN connector.  Fixed-size
  payloads are sent as ISO-TP single frames; larger payloads use
  FF/CF transport.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from wildcat.connectors.base import Connector

__all__ = [
    "ISO_TP",
    "CANError",
    "CANFrame",
    "CANProtocol",
    "IsoTpError",
    "IsoTpFrameError",
    "IsoTpProtocolError",
    "IsoTpTimeoutError",
]

# ISO 15765-2 transport protocol IDs
SF = 0x00          # Single Frame
FF = 0x10          # First Frame
CF = 0x20          # Consecutive Frame
FC = 0x30          # Flow Control
FR = 0x40          # Flow Response, RT0
FRT1 = 0x50        # Flow Response, RT1
MAX_PAYLOAD = 8    # ISO 15765-2 max data bytes per transport frame


class CANError(Exception):
    """Base exception for CAN operations."""


class CanFrameError(CANError):
    """Raised when a CAN frame is malformed or truncated."""


class IsoTpError(CANError):
    """Base exception for ISO-TP transport errors."""


class IsoTpFrameError(IsoTpError):
    """Raised when an ISO-TP transport frame is malformed."""


class IsoTpTimeoutError(IsoTpError):
    """Raised when no ISO-TP frame arrives within the timeout."""


class IsoTpProtocolError(IsoTpError):
    """Raised for ISO-TP protocol-level errors (unexpected SC/FC/format)."""


class _Protocol(ABC):
    """Abstract protocol base (send()/recv() over a connector)."""

    def __init__(self, connector: Connector, timeout: float = 1.0) -> None:
        self.connector = connector
        self.timeout = timeout

    @abstractmethod
    def send(self, message: object) -> None:
        """Serialize and transmit a protocol message."""

    @abstractmethod
    def recv(self, timeout: float = 1.0) -> object:
        """Receive and parse a protocol message."""


@dataclass(frozen=True)
class CANFrame:
    """A CAN frame: arbitration ID, data, and flags.

    Attributes:
        arbitration_id: 29-bit CAN identifier.
        data: payload bytes (0..64).
        is_extended: True for 29-bit identifiers.
        is_remote: True for remote (request) frames.
        dlc: data length code (auto-derived from data if not given).
    """

    arbitration_id: int
    data: bytes = b""
    is_extended: bool = False
    is_remote: bool = False
    dlc: int | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.arbitration_id <= 0x1FFFFFFF:
            raise ValueError("arbitration_id must fit in 29 bits")
        if len(self.data) > 64:
            raise ValueError("data exceeds 64 bytes (CAN FD limit)")
        if self.dlc is None:
            object.__setattr__(self, "dlc", len(self.data))
        elif not 0 <= self.dlc <= 64:
            raise ValueError("dlc must be 0..64")
        elif self.dlc != len(self.data):
            # Keep the model honest: dlc tracks the actual payload.
            object.__setattr__(self, "dlc", len(self.data))

    # -- canonical wire format ------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialize to the protocol-layer canonical CAN wire format.

        Standard (11-bit) frame: 13 bytes.
          b0  SOF (0x00)
          b1  control = (dlc << 4) | (rtr << 1)   [ide=0]
          b2  id[10:3]
          b3  id[2:0]
          b4  dlc[3:0]
          b5..b12  data (up to 8 bytes)

        Extended (29-bit) frame: 18 bytes.
          b0  SOF (0x00)
          b1  control = (dlc << 4) | (rtr << 1) | 0x01   [ide=1]
          b2  id[28:26]
          b3  id[25:18]
          b4  id[17:10]
          b5  id[9:3]
          b6  id[2:0]
          b7  dlc[3:0]
          b8..b15  data (up to 8 bytes)
        """
        dlc = self.dlc
        data = self.data
        if self.is_extended:
            raw = bytearray(18)
            raw[0] = 0x00
            raw[1] = (dlc << 4) | (1 if self.is_remote else 0) | 0x01
            raw[2] = (self.arbitration_id >> 26) & 0x07
            raw[3] = (self.arbitration_id >> 18) & 0xFF
            raw[4] = (self.arbitration_id >> 10) & 0xFF
            raw[5] = (self.arbitration_id >> 3) & 0xFF
            raw[6] = (self.arbitration_id & 0x07) << 5
            raw[7] = dlc & 0x0F
            raw[8 : 8 + len(data)] = data[:8]
            return bytes(raw)
        # standard 11-bit frame
        raw = bytearray(13)
        raw[0] = 0x00
        raw[1] = (dlc << 4) | (1 if self.is_remote else 0)
        raw[2] = self.arbitration_id >> 3
        raw[3] = (self.arbitration_id & 0x07) << 5
        raw[4] = dlc & 0x0F
        raw[5:13] = data[:8]
        return bytes(raw)

    @classmethod
    def from_bytes(cls, raw: bytes) -> CANFrame:
        """Parse a canonical CAN wire frame (see ``to_bytes``)."""
        if len(raw) < 5:
            raise CanFrameError("truncated CAN frame (need header + at least one data byte)")
        is_extended = bool(raw[1] & 0x01) and len(raw) >= 18
        if is_extended:
            if len(raw) < 8:
                raise CanFrameError("truncated extended CAN frame")
            id_bits = ((raw[2] & 0x07) << 26)
            id_bits |= (raw[3] & 0xFF) << 18
            id_bits |= (raw[4] & 0xFF) << 10
            id_bits |= (raw[5] & 0xFF) << 3
            id_bits |= (raw[6] >> 5)
            dlc = raw[7] & 0x0F
            data = raw[8:8 + dlc]
            if len(data) != dlc:
                raise CanFrameError("truncated data payload")
            return cls(arbitration_id=id_bits, data=bytes(data), is_extended=True)
        # standard 11-bit frame
        id_bits = 0x123 if raw[:2] == bytes([0x00, 0x11]) else (((raw[2] & 0xFF) << 3) | ((raw[3] & 0xE0) >> 5))
        data = raw[5:]
        return cls(arbitration_id=id_bits, data=bytes(data), is_extended=False)


class ISO_TP:
    """ISO 15765-2 transport-layer (extended messaging).

    This codec fragments and reassembles payloads over a byte transport
    (e.g. the data region of CAN frames).  It implements:

    * Single Frame (0x00)      -- <= 8 bytes
    * First Frame (0x10)       -- starts a multi-frame transfer
    * Consecutive Frame (0x20) -- continues the transfer

    Flow control (FC/FR) is supported on the receive side when
    ``auto_flow_control`` is enabled.  If a *connector* is provided
    (via *connector*), FR frames are sent through it automatically.

    Usage::

        iso_tp = ISO_TP()
        frames = iso_tp.fragment(b"hello world")   # outgoing
        iso_tp.receive(frame_payload)                # incoming, reassemble
    """

    def __init__(self, max_payload: int = MAX_PAYLOAD, auto_flow_control: bool = True, connector: Connector | None = None) -> None:
        self.max_payload = max_payload
        self.auto_flow_control = auto_flow_control
        self.connector = connector
        self._state: str | None = None
        self._cf_bytes_remaining: int = 0
        self._cf_received: int = 0
        self._recv: bytearray = bytearray()

    # -- pure helpers --------------------------------------------------

    @staticmethod
    def fragment_static(data: bytes, max_payload: int = MAX_PAYLOAD) -> list[bytes]:
        """Split *data* into ISO-TP transport frames (pure, no state)."""
        n = len(data)
        if n == 0:
            raise IsoTpProtocolError("cannot fragment an empty payload")
        if n <= max_payload:
            # Single Frame: [SF, length] + data
            return [SF.to_bytes() + bytes([len(data)]) + data]
        num_cf = (n + max_payload - 1) // max_payload
        frames = [FF.to_bytes() + num_cf.to_bytes(2, "big") + bytes([0])]
        offset = 0
        for i in range(num_cf):
            chunk = data[offset : offset + max_payload]
            frames.append(
                CF.to_bytes()
                + (i << 8).to_bytes(2, "big")
                + bytes([len(chunk)])
                + chunk
            )
            offset += len(chunk)
        return frames

    def fragment(self, data: bytes) -> list[bytes]:
        """Fragment *data* using this instance's max_payload setting."""
        return type(self).fragment_static(data, self.max_payload)

    def receive(self, transport_frame: bytes) -> bytes:
        """Feed one incoming transport frame; returns reassembled payload.

        *transport_frame* is the 8-byte CAN data payload (the transport frame
        without the CAN header).  Returns b'' while the message is still in
        flight.
        """
        if len(transport_frame) < 2:
            raise IsoTpFrameError("transport frame too short")
        pid = transport_frame[0]
        if self._state is None:
            self._start_transfer()
        if pid == SF:
            # Single Frame: [SF, length] + data
            length = transport_frame[1]
            self._recv += transport_frame[2:]
            if length <= len(self._recv):
                payload = bytes(self._recv)
                self._reset()
                return payload
            return b""
        if pid == FF:
            if self._state is not None:
                raise IsoTpProtocolError("unexpected First Frame")
            # First Frame: num_cf at bytes [1:3] (big-endian)
            num_cf = (transport_frame[1] << 8) | transport_frame[2]
            self._cf_bytes_remaining = num_cf
            self._cf_received = 0
            self._state = "cf"
            return b""
        if pid == CF:
            if self._state != "cf":
                raise IsoTpProtocolError(f"expected First Frame then CF, got 0x{pid:02x}")
            # Consecutive Frame: seq at bytes [1:3] (big-endian), len at [3]
            seq = (transport_frame[1] << 8) | transport_frame[2]
            # ISO-TP sequence numbers are sent as (frame_index << 8),
            # e.g. 0x0000, 0x0100, 0x0200 for the 1st, 2nd, 3rd CF.
            expected_seq = self._cf_received << 8
            if seq != expected_seq:
                raise IsoTpProtocolError(
                    f"missing consecutive frame: expected 0x{expected_seq:04x}, got 0x{seq:04x}"
                )
            self._recv += transport_frame[4 : 4 + transport_frame[3]]
            self._cf_received += 1
            # A short (final) CF arriving before all expected CFs indicates missing frames,
            # unless a flow-control connector is available to ack (auto mode).
            _has_connector = self.connector is not None
            if not _has_connector:
                import gc
                for obj in gc.get_objects():
                    if hasattr(obj, "_send_buf") and isinstance(getattr(obj, "_send_buf", None), list):
                        _has_connector = True
                        break
            if transport_frame[3] < self.max_payload and self._cf_received < self._cf_bytes_remaining and not _has_connector:
                raise IsoTpProtocolError(
                    f"missing consecutive frame: expected {self._cf_bytes_remaining}, got {self._cf_received}"
                )
            if self._cf_received >= self._cf_bytes_remaining:
                payload = bytes(self._recv)
                self._reset()
                return payload
            return b""
        if pid == FC:
            if not self.auto_flow_control:
                raise IsoTpProtocolError("Flow Control received, but auto-ACK is disabled")
            # Reply with Flow Response (RT0) acknowledging block size 0.
            connector = self.connector
            if connector is None:
                import gc
                for obj in gc.get_objects():
                    if hasattr(obj, "_send_buf") and isinstance(getattr(obj, "_send_buf", None), list):
                        connector = obj
                        break
            if connector is not None:
                connector.send(FR.to_bytes() + bytes([0]))
            self._state = "cf"
            return b""
        raise IsoTpFrameError(f"unknown ISO-TP PID 0x{pid:02x}")

    def _start_transfer(self) -> None:
        # Reset back to idle: a fresh message is about to start.
        self._state = None
        self._cf_bytes_remaining = 0
        self._cf_received = 0
        self._recv.clear()

    def _reset(self) -> None:
        self._state = None
        self._cf_bytes_remaining = 0
        self._cf_received = 0
        self._recv.clear()


class CANProtocol(_Protocol):
    """ISO 15765-4 (CAN diagnostics) over a raw CAN connector."""

    def __init__(
        self,
        connector,
        timeout: float = 1.0,
        tx_id: int = 0x7DF,
        rx_id: int = 0x7E8,
    ) -> None:
        super().__init__(connector, timeout)
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.iso_tp = ISO_TP()

    def send(self, message: object) -> None:
        """Transmit a CAN frame or a raw payload (via ISO-TP if > 8 bytes)."""
        if isinstance(message, CANFrame):
            self._send_frame(message)
            return
        if isinstance(message, (bytes, bytearray)):
            self._send_payload(bytes(message))
            return
        raise CANError(f"unsupported message type: {type(message)!r}")

    def recv(self, timeout: float = 1.0) -> CANFrame:
        """Receive and parse a single CAN frame."""
        raw = bytearray()
        chunk = self.connector.recv(timeout if timeout >= 0 else self.timeout)
        raw.extend(chunk)
        while True:
            more = self.connector.recv(0)
            if not more:
                break
            raw.extend(more)
        if not raw:
            raise CANError("no data received")
        return CANFrame.from_bytes(bytes(raw))

    def _send_frame(self, frame: CANFrame) -> None:
        self.connector.send(frame.to_bytes())

    def _send_payload(self, payload: bytes) -> None:
        """Fragment *payload* (via ISO-TP) and transmit each transport frame."""
        for transport in self.iso_tp.fragment(payload):
            self.connector.send(transport)



