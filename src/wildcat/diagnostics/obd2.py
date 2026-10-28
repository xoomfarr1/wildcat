"""SAE J1979 (OBD-II) reader over an ELM327 serial adapter.

This module talks the standard OBD-II command language to an
:class:`~wildcat.connectors.elm327.Elm327Connector` and decodes the
responses into :class:`~wildcat.cars.base.DTC` / :class:`LiveData`
records.  It is the *real-data* path for the FTDI/ELM327 cable: when a
physical adapter is connected, the reads below return what the vehicle
actually reports; in virtual (echo) mode the adapter echoes the command
back, parsing fails, and the result is an empty list (honest — no
fabricated data).

Transport note: ELM327 is a serial (UART) device, so it works with the
FTDI cables the user has.  A bare FTDI cable is NOT a CAN transceiver;
for raw CAN (slcan/USB-CAN) use the ``UsbCANConnector`` instead.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from wildcat.cars.base import DTC, LiveData
from wildcat.connectors.base import Connector

# OBD-II Mode 01 PIDs we request for live data: (pid, name, unit, decoder).
# decoder takes the response data bytes (after the "41 PID" header) and
# returns a float.
_LIVE_PIDS: list[tuple[int, str, str, Callable[[list[int]], float]]] = [
    (0x0C, "EngineRPM", "rpm", lambda b: ((b[0] * 256) + b[1]) / 4.0),
    (0x05, "CoolantTemp", "°C", lambda b: b[0] - 40.0),
    (0x0D, "VehicleSpeed", "km/h", lambda b: float(b[0])),
    (0x11, "ThrottlePosition", "%", lambda b: b[0] * 100.0 / 255.0),
    (0x0F, "IntakeAirTemp", "°C", lambda b: b[0] - 40.0),
    (0x42, "ControlModuleVoltage", "V", lambda b: ((b[0] * 256) + b[1]) / 1000.0),
    (0x0B, "IntakeManifoldPressure", "kPa", lambda b: float(b[0])),
    (0x04, "EngineLoad", "%", lambda b: b[0] * 100.0 / 255.0),
]


def _query(connector: Connector, cmd: str, timeout: float = 1.0) -> str:
    """Send an OBD-II command and return the hex payload (spaces stripped).

    Returns an empty string on timeout or unparseable response.  The ELM327
    echoes the command and terminates responses with ``>``; both are stripped.
    """
    try:
        connector.send((cmd + "\r").encode("ascii"))
    except (OSError, ValueError, UnicodeEncodeError):
        return ""
    buf = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            chunk = connector.recv(timeout=0.1)
        except (OSError, ValueError, UnicodeDecodeError):
            chunk = b""
        if chunk:
            buf += chunk
            if b">" in buf:
                break
        else:
            # no data this tick; small pause to avoid busy-spin
            time.sleep(0.02)
    text = buf.decode("ascii", errors="replace")
    # strip the echoed command and the prompt
    text = text.replace(cmd, "")
    text = text.replace(">", "")
    # keep only hex digits
    hexstr = "".join(ch for ch in text if ch in "0123456789abcdefABCDEF")
    return hexstr


def _decode_dtc(word: int) -> str:
    """Decode a 16-bit OBD-II DTC word into a code like 'P0301'."""
    type_char = "PCBU"[(word >> 14) & 0x03]
    d1 = (word >> 12) & 0x03
    d2 = (word >> 8) & 0x0F
    d3 = (word >> 4) & 0x0F
    d4 = word & 0x0F
    return f"{type_char}{d1}{d2:X}{d3:X}{d4:X}"


def read_dtcs(connector: Connector) -> list[DTC]:
    """Read stored DTCs via OBD-II Mode 03.  Returns [] on no data / error."""
    hexstr = _query(connector, "03")
    if not hexstr or not hexstr.startswith("43"):
        return []
    # skip the "43" mode-response byte
    payload = hexstr[2:]
    out: list[DTC] = []
    # each DTC is 4 hex chars (2 bytes)
    for i in range(0, len(payload) - 3, 4):
        word = int(payload[i : i + 4], 16)
        if word == 0:
            continue
        code = _decode_dtc(word)
        out.append(DTC(code=code, description="", severity="Warning", is_temporary=False))
    return out


def clear_dtcs(connector: Connector) -> None:
    """Clear stored DTCs via OBD-II Mode 04."""
    _query(connector, "04")


def read_vin(connector: Connector) -> str | None:
    """Read the VIN via OBD-II Mode 09 PID 02.  Returns None on failure."""
    hexstr = _query(connector, "0902")
    if not hexstr or not hexstr.startswith("4902"):
        return None
    payload = hexstr[4:]  # skip "4902"
    # first byte is the number of data items; skip it
    if len(payload) < 2:
        return None
    payload = payload[2:]
    chars = []
    for i in range(0, len(payload) - 1, 2):
        try:
            b = int(payload[i : i + 2], 16)
        except ValueError:
            break
        if 32 <= b < 127:
            chars.append(chr(b))
    vin = "".join(chars).strip()
    return vin if len(vin) == 17 else None


def read_live_data(connector: Connector) -> list[LiveData]:
    """Read a standard set of live PIDs via OBD-II Mode 01."""
    out: list[LiveData] = []
    for pid, name, unit, decoder in _LIVE_PIDS:
        hexstr = _query(connector, f"01{pid:02X}")
        expected_header = f"41{pid:02X}"
        if not hexstr or not hexstr.startswith(expected_header):
            continue
        payload = hexstr[len(expected_header) :]
        # need at least 1 byte
        if len(payload) < 2:
            continue
        data_bytes = [int(payload[i : i + 2], 16) for i in range(0, len(payload), 2)]
        try:
            value = float(decoder(data_bytes))
        except (IndexError, ValueError, TypeError, ZeroDivisionError):
            continue
        out.append(LiveData(name=name, value=round(value, 2), unit=unit))
    return out
