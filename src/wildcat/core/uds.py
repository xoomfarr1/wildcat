"""UDS (ISO 14229) service helpers.

A protocol-service layer that maps UDS function codes (0x01-0x27) to domain
handlers.  This is the layer between the car model and the raw connector: the
car model asks *what* it wants (e.g. "read the DTCs"), and ``UDSService``
figures out *how* to ask the vehicle over the wire.

All service methods return plain Python data structures (lists of dicts or
:func:`dataclass` records) so the rest of the stack never needs to know the
UDS wire layout.

Wire conventions
----------------
* A UDS *request* is ``[SID, PS] + parameters``.
* A *positive* response begins with ``0x20 + SID`` (the requested SID with the
  0x40 bit set) followed by the PS byte; the payload starts at offset 2.
* A *negative* response begins with ``0x7F 0x70 + sub-function`` followed by an
  error code and optional data.
* The security seed / key exchange uses SID 0x27 (RequestSeed) and 0x29
  (ResponseSeed).  The seed/key payload is included verbatim in the request,
  and the 4-byte value is returned from the response.
"""
from __future__ import annotations

import struct

from wildcat.connectors.base import ConnectorError, ConnectorNotOpenError

__all__ = [
    "ClearDTCsError",
    "ClearDiagnosticInformationError",
    "ControlDTCsError",
    "DTCReaderError",
    "DiagnosticSessionControlError",
    "ECUIdentificationError",
    "InputOutputControlByIdentifierError",
    "LockBlockedError",
    "RawUDSConnector",
    "ReadDTCsByStatusMaskError",
    "ReadDataByIdentifierError",
    "ReadFreezeFrameDataError",
    "ReadIndicatorLocationError",
    "ReadMemoryByAddressError",
    "ReadOngoingDataByIdentifierError",
    "ReadScalingDataByIdentifierError",
    "ReadUnitControlError",
    "ResponseOnEventError",
    "RouteDiagnosticMessageError",
    "RoutineControlError",
    "SecurityAccessError",
    "TransferDataByIdentifierError",
    # --- exceptions ------------------------------------------------------- #
    "UDSError",
    # --- service / connector classes -------------------------------------- #
    "UDSService",
    "VirtualUDSConnector",
    "WakeUpError",
    "WriteMemoryByAddressError",
    "WriteMemoryByNumberError",
    "WriteRelativeDataByIdentifierError",
    "WriteScalingDataByIdentifierError",
]

# Service detection: the first byte of a positive UDS response (e.g. 0x21 for
# service 0x01) is the requested SID echoed with the 0x40 bit set.  The
# *_SERVICE* constants below mirror the real UDS function codes used in this
# module so the reading code stays self-documenting.
SF_READ_DTC_BY_STATUS_MASK = 0x01
SF_CLEAR_DTC = 0x04
SF_READ_DATA_BY_IDENTIFIER = 0x21
SF_READ_DATA_BY_IDENTIFIER_Echo = 0x50  # positive response to 0x10


class UDSError(Exception):
    """Base exception for all UDS (ISO 14229) service errors."""


# Service-specific errors.  Each names the UDS service that can fail, mirroring
# the ISO 14229-1 service catalogue so a caller can catch the exact failure
# mode instead of guessing from a generic exception.
class DTCReaderError(UDSError):
    """Raised when the DTC reader service fails."""


class ReadDataByIdentifierError(UDSError):
    """Raised when reading data by identifier fails."""


class DiagnosticSessionControlError(UDSError):
    """Raised when the diagnostic session control fails."""


class SecurityAccessError(UDSError):
    """Raised when a security-access (seed/key) exchange fails."""


class ECUIdentificationError(UDSError):
    """Raised when ECU identification fails."""


class ControlDTCsError(UDSError):
    """Raised when controlling DTCs fails."""


class ReadDTCsByStatusMaskError(UDSError):
    """Raised when reading DTCs by status mask fails."""


class ClearDTCsError(UDSError):
    """Raised when clearing DTCs fails."""


class RoutineControlError(UDSError):
    """Raised when a routine control fails."""


class InputOutputControlByIdentifierError(UDSError):
    """Raised when I/O control by identifier fails."""


class ReadMemoryByAddressError(UDSError):
    """Raised when reading memory by address fails."""


class WriteMemoryByAddressError(UDSError):
    """Raised when writing memory by address fails."""


class TransferDataByIdentifierError(UDSError):
    """Raised when transferring data by identifier fails."""


class WriteMemoryByNumberError(UDSError):
    """Raised when writing memory by number fails."""


class ResponseOnEventError(UDSError):
    """Raised when a response-on-event times out."""


class ReadScalingDataByIdentifierError(UDSError):
    """Raised when reading scaling data by identifier fails."""


class ReadIndicatorLocationError(UDSError):
    """Raised when reading the indicator location fails."""


class ReadUnitControlError(UDSError):
    """Raised when reading the unit control fails."""


class WriteScalingDataByIdentifierError(UDSError):
    """Raised when writing scaling data by identifier fails."""


class WriteRelativeDataByIdentifierError(UDSError):
    """Raised when writing relative data by identifier fails."""


class ClearDiagnosticInformationError(UDSError):
    """Raised when clearing diagnostic information fails."""


class ReadOngoingDataByIdentifierError(UDSError):
    """Raised when reading ongoing data by identifier fails."""


class LockBlockedError(UDSError):
    """Raised when the ECU reports a lock block (e.g. security access locked)."""


class RouteDiagnosticMessageError(UDSError):
    """Raised when routing a diagnostic message fails."""


class ReadFreezeFrameDataError(UDSError):
    """Raised when reading freeze frame data fails."""


class WakeUpError(UDSError):
    """Raised when waking up the ECU fails."""


# --------------------------------------------------------------------------- #
# Connectors
# --------------------------------------------------------------------------- #


class RawUDSConnector:
    """Minimal raw UDS connector (byte pipe).

    A plain FIFO byte pipe with no protocol framing.  It is the minimal
    building block for tests that only need to verify a service sends the
    expected bytes and can read an injected response.  It has no echo,
    no ``inject`` and no ``reset`` so it stays truly minimal.

    Attributes:
        bytes_sent: Total bytes written via :meth:`send`.
        bytes_received: Total bytes read via :meth:`recv`.
    """

    def __init__(self) -> None:
        self._rx: list[bytes] = []
        self.bytes_sent = 0
        self.bytes_received = 0
        self._opened = False

    def open(self) -> None:
        """Open the connector (no hardware involved)."""
        self._opened = True
        self.bytes_sent = 0
        self.bytes_received = 0

    def close(self) -> None:
        """Close the connector."""
        self._opened = False

    def send(self, data: bytes) -> None:
        """Write bytes toward the hardware."""
        if not self._opened:
            raise ConnectorNotOpenError("connector is not open")
        data = bytes(data)
        # Stack order: the most recently sent bytes are returned first, which
        # is fine for single-request tests.
        self._rx.insert(0, data)
        self.bytes_sent += len(data)

    def recv(self, timeout: float = 1.0) -> bytes:
        """Read bytes arriving from the hardware; ``b''`` on timeout."""
        if not self._opened:
            raise ConnectorNotOpenError("connector is not open")
        if not self._rx:
            return b""
        data = self._rx.pop()
        self.bytes_received += len(data)
        return data

    def is_open(self) -> bool:
        """Return True if the connector is open."""
        return self._opened


class VirtualUDSConnector:
    """Minimal virtual UDS connector (FIFO echo pipe).

    Everything written to :meth:`send` is stored for later replay; by default
    nothing is echoed back automatically.  :meth:`inject` pushes arbitrary
    bytes into the receive pipe so a test can simulate a complete UDS
    round-trip (``send_seed`` -> ``seed_response`` -> ``read_dtc`` -> data)
    without any hardware.

    This deliberately mirrors the ``VirtualConnection`` pattern used by the
    physical connector drivers so the service layer can be exercised with a
    drop-in replacement.

    Attributes:
        bytes_sent: Total bytes written via :meth:`send`.
        bytes_received: Total bytes read via :meth:`recv`.
    """

    def __init__(self, *, echo: bool = False) -> None:
        self.echo = echo
        self._rx: list[bytes] = []
        self.bytes_sent = 0
        self.bytes_received = 0
        self._opened = False

    # ------------------------------------------------------------------ life #
    def open(self) -> None:
        """Open the virtual connector (no hardware involved)."""
        self._opened = True
        self.bytes_sent = 0
        self.bytes_received = 0

    def close(self) -> None:
        """Close the virtual connector."""
        self._opened = False

    # --------------------------------------------------------------- I/O core
    def send(self, data: bytes) -> None:
        """Write bytes toward the hardware (FIFO enqueue)."""
        if not self._opened:
            raise ConnectorNotOpenError("connector is not open")
        data = bytes(data)
        self._rx.append(data)
        self.bytes_sent += len(data)
        # Echo is opt-in and, when enabled, is enqueued at the front so a
        # consecutive ``recv`` immediately after a ``send`` sees the echo.
        if self.echo:
            self._rx.insert(0, data)

    def recv(self, timeout: float = 1.0) -> bytes:
        """Read bytes arriving from the hardware; ``b\"\"`` on timeout."""
        if not self._opened:
            raise ConnectorNotOpenError("connector is not open")
        try:
            data = self._rx.pop(0)
        except IndexError:
            return b""
        self.bytes_received += len(data)
        return data

    def inject(self, data: bytes) -> None:
        """Push bytes into the receive pipe, simulating a hardware response."""
        if not self._opened:
            raise ConnectorNotOpenError("connector is not open")
        self._rx.insert(0, bytes(data))

    def is_open(self) -> bool:
        """Return True if the connector is open."""
        return self._opened

    def reset(self) -> None:
        """Reset the connector: keep the pipe but flush pending data."""
        self._rx.clear()


# --------------------------------------------------------------------------- #
# Service handlers
# --------------------------------------------------------------------------- #


class UDSService:
    """ISO 14229 (UDS) service handlers built on top of a raw connector.

    This class sits between the car model and the hardware connector.  The
    car model asks *what* it wants (read DTCs, read live data, ...), and this
    class figures out *how* to ask the vehicle over the wire.

    Requests are built as UDS services: ``[SID, PS] + parameters``.  Positive
    responses begin with ``0x20 + SID`` (the requested SID echoed with the
    0x40 bit set); negative responses begin with ``0x7F 0x70 + sub-function``.

    Attributes:
        connector: Raw-connector implementation (see ``wildcat.connectors``).
        timeout: Default receive timeout in seconds.
    """

    #: Default target ECU identifier (0x3E = read-data-by-identifier on many
    #: platforms).  The identifier is determined *per car definition*; override
    #: it for the target ECU if the vehicle uses a different one (e.g. 0x2E,
    #: 0x2F, 0x10, 0x22).
    DEFAULT_ECU_ID = 0x3E

    def __init__(
        self,
        connector,
        timeout: float = 1.0,
        ecu_id: int = DEFAULT_ECU_ID,
        security_access: bool = True,
    ) -> None:
        """Store the connector and timeout; reject a closed connector.

        Args:
            connector: Raw-connector implementation (see ``wildcat.connectors``).
            timeout: Default receive timeout in seconds.
            ecu_id: Target ECU identifier; determined per the car definition.
            security_access: Whether the vehicle requires security access.

        Raises:
            ConnectorError: If the connector is not open.
        """
        if not connector.is_open():
            raise ConnectorError("connector is not open")
        self.connector = connector
        self.timeout = timeout
        self._ecu_id = ecu_id
        self._security_access = security_access

    # ------------------------------------------------------------- generic --- #
    def send(self, message) -> None:
        """Send a raw payload to the connector.

        Accepts bytes or bytearray (and anything that satisfies the
        :class:`bytes` protocol) so callers can pass either; the payload is
        normalised to ``bytes`` before it is handed to the connector.

        Args:
            message: The payload to transmit.
        """
        self.connector.send(bytes(message))

    def recv(self, timeout: float | None = None) -> bytes:
        """Receive raw bytes from the connector.

        Returns ``b""`` when nothing is available (instead of raising), so a
        caller can poll without blocking.  The supplied ``timeout`` (or, failing
        that, the service's default) is forwarded to the connector's ``recv``.

        Args:
            timeout: Receive timeout in seconds; ``None`` falls back to the
                service default.

        Returns:
            The bytes received, or ``b""`` if nothing was available.
        """
        conn_timeout = self.timeout if timeout is None else timeout
        return self.connector.recv(conn_timeout)

    # ------------------------------------------------------- security access #
    def send_seed(self, seed: bytes) -> bytes:
        """Ask the ECU for a security seed (SBC SID 0x27).

        The request is the UDS ``RequestSeed``: ``[0x27, PS, key_id...]`` where
        ``PS`` is the seed length.  The ECU replies with the 4-byte seed; this
        method returns those 4 bytes.

        Args:
            seed: 4-byte key ID used to request the seed.

        Returns:
            The 4-byte seed returned by the vehicle.

        Raises:
            SecurityAccessError: If the response is not a positive seed
                response (e.g. the ECU locked the security session).
        """
        request = bytes([0x27, len(seed)]) + bytes(seed)
        self.send(request)
        response = self.recv(self.timeout)
        if len(response) < 6 or response[0] != 0x27:
            raise SecurityAccessError(f"unexpected seed response: {response!r}")
        return response[2:6]

    def send_key(self, key: bytes) -> bytes:
        """Send a seed response to the ECU (SID 0x29).

        The request is the UDS ``ResponseSeed``: ``[0x29, PS, key...]`` where
        ``PS`` is the key length.  The vehicle replies with the 4-byte session
        key; this method returns those 4 bytes.

        Args:
            key: 4-byte seed returned by the vehicle.

        Returns:
            The 4-byte session key contained in the vehicle's response.

        Raises:
            SecurityAccessError: If the response is not a positive key
                response.
        """
        request = bytes([0x29, len(key)]) + bytes(key)
        self.send(request)
        response = self.recv(self.timeout)
        if len(response) < 6 or response[0] != 0x29:
            raise SecurityAccessError(f"unexpected key response: {response!r}")
        return response[2:6]

    # ------------------------------------------------------------- DTCs -------- #
    def read_dtc(self) -> list[dict]:
        """Read stored fault codes from the vehicle.

        Sends UDS service 0x01 (ReadDTCByStatusMask) with the "all DTCs"
        status mask (0x0001) and decodes the response payload into a list of
        ``{"code": str, "description": str}`` records.

        Returns:
            A list of DTC records read from the vehicle.
        """
        request = bytes([SF_READ_DTC_BY_STATUS_MASK, 0x01, 0x00, 0x01])
        self.send(request)
        response = self.recv(self.timeout)
        if len(response) < 2 or response[0] != 0x21:
            raise ReadDTCsByStatusMaskError(f"unexpected response: {response!r}")
        return self._parse_dtcs(response[2:])

    def _parse_dtcs(self, payload: bytes) -> list[dict]:
        """Decode the ReadDTCByStatusMask payload into a list of DTC dicts.

        Each DTC record in the payload is 7 bytes:
          - present flag (0x00 = present)
          - 2-byte DTC code
          - flags byte
          - count byte
          - 2 reserved bytes (zero)

        Only records whose present flag is 0x00 are returned.  The description
        comes from a small built-in table of common codes; unknown codes get an
        empty description.

        Args:
            payload: The response payload (after the 3-byte header).

        Returns:
            A list of ``{"code": str, "description": str}`` records.
        """
        descriptions = {
            0x0001: "Powertrain — cylinder misfire detected",
            0x0002: "Powertrain — cylinder misfire continued",
            0x003C: "Powertrain — coolant temperature below regulator",
            0x0171: "Powertrain — system too lean (bank 1)",
            0x0420: "Catalyst efficiency below threshold (bank 1)",
            0x0455: "Evaporative leak detected (large leak)",
            0x0500: "Chassis — vehicle speed sensor (default)",
            0x5100: "Network — lost communication with ECM",
        }
        dtcs: list[dict] = []
        i = 0
        while i + 7 <= len(payload):
            if payload[i] != 0x00:
                break
            code = payload[i + 1 : i + 3]
            i += 7
            code_int = int.from_bytes(code, "big")
            dtcs.append(
                {
                    "code": format(code_int, "04X"),
                    "description": descriptions.get(code_int, ""),
                }
            )
        return dtcs

    def clear_dtc(self) -> None:
        """Clear all currently stored fault codes.

        Sends UDS service 0x04 (ClearDTCs).  A positive response (0x24) confirms
        the clear; anything else raises ``ClearDTCsError``.

        Returns:
            None
        """
        request = bytes([SF_CLEAR_DTC, 0x01])
        self.send(request)
        response = self.recv(self.timeout)
        if len(response) < 2 or response[0] != 0x24:
            raise ClearDTCsError(f"unexpected response: {response!r}")

    # ----------------------------------------------------------- live data --- #
    def read_live_data(self, keys: list[int]) -> list[dict]:
        """Read live data from the vehicle via UDS service 0x21.

        Sends UDS service 0x21 (ReadDataByIdentifier) for each requested
        identifier and decodes the response payload into a list of
        ``{"name": str, "value": float, "unit": str}`` records.

        Args:
            keys: Identifiers to read (2-byte values).

        Returns:
            A list of live data records.
        """
        payload = b""
        for key in keys:
            payload += int(key).to_bytes(2, "big")
        request = bytes([SF_READ_DATA_BY_IDENTIFIER, 0x01]) + payload
        self.send(request)
        response = self.recv(self.timeout)
        if len(response) < 2 or response[0] != 0x21:
            raise ReadDataByIdentifierError(f"unexpected response: {response!r}")
        return self._parse_live_data(response[2:])

    def _parse_live_data(self, payload: bytes) -> list[dict]:
        """Decode the ReadDataByIdentifier payload into live-data dicts.

        Each record in the payload is variable-length; the present flag
        terminates the sequence:
          - present flag (0x00 = present)
          - name length (1 byte) + UTF-8 name
          - identifier (2 bytes, echoed)
          - value (4 bytes, IEEE 754 big-endian float)
          - unit length (1 byte) + UTF-8 unit string

        Args:
            payload: The response payload (after the 3-byte header).

        Returns:
            A list of ``{"name": str, "value": float, "unit": str}`` records.
        """
        out: list[dict] = []
        data = payload
        while data:
            if data[0] != 0x00:
                break
            data = data[1:]
            if not data:
                break  # End-of-payload present flag with no data following
            name_len = data[0]
            data = data[1:]
            name = data[:name_len].decode("utf-8", errors="replace")
            data = data[name_len:]
            int.from_bytes(data[:2], "big")
            data = data[2:]
            value = struct.unpack(">f", data[:4])[0]
            data = data[4:]
            unit_len = data[0]
            data = data[1:]
            unit = data[:unit_len].decode("utf-8", errors="replace")
            data = data[unit_len:]
            out.append({"name": name, "value": value, "unit": unit})
        return out

    # --------------------------------------------------------------- helper -- #
    def get_dtc_reader(self) -> list[dict]:
        """Return the DTC reader handler.

        Wraps :meth:`read_dtc` so callers get the stored fault codes as a plain
        list of dicts without touching the UDS service directly.

        Returns:
            A list of DTC records.
        """
        return self.read_dtc()

    # --------------------------------------------------------------- identity -- #
    def ecu_id(self) -> int:
        """Return the ECU identifier for this vehicle.

        The identifier is determined per the car definition (e.g. 0x2E/0x2F or
        0x10/0x22) and is stored on the service at construction time.

        Returns:
            The target ECU identifier.
        """
        return self._ecu_id

    def security_access(self) -> bool:
        """Return whether this vehicle requires security access.

        Security access is a property of the car (e.g. Mercedes SBC vehicles
        require it for programming; most OBD-II Ford ECUs do not).

        Returns:
            True if the vehicle requires security access.
        """
        return self._security_access


# --------------------------------------------------------------------------- #
# Module-level error helpers (kept small so each service error is unambiguous)
# --------------------------------------------------------------------------- #
