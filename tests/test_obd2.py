"""Tests for the OBD-II (SAE J1979) reader over ELM327.

Uses an in-memory mock connector so parsing can be exercised without
hardware.  Virtual (echo) mode is covered to assert the honest
"no fake data" behaviour.
"""
from __future__ import annotations

from wildcat.cars.base import DTC, LiveData
from wildcat.connectors.base import Connector
from wildcat.connectors.elm327 import Elm327Connector
from wildcat.diagnostics import obd2


class _MockConnector(Connector):
    """Connector that returns a canned ELM327 response for every query."""

    def __init__(self, response: str) -> None:
        self._response = response.encode("ascii")
        self._open = False
        self.sent: bytes = b""

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def send(self, data: bytes) -> None:
        self.sent = data

    def recv(self, timeout: float = 1.0) -> bytes:
        # ELM327 terminates responses with '>'.
        return self._response + b">"

    def is_open(self) -> bool:
        return self._open

    def reset(self) -> None:
        self.sent = b""
        self._open = False


def test_decode_dtc():
    assert obd2._decode_dtc(0x0133) == "P0133"
    assert obd2._decode_dtc(0x0000) == "P0000"


def test_read_dtcs_parses_response():
    # Mode 03 response: 43 01 33 00 00 00 00 00  -> P0133
    conn = _MockConnector("43 01 33 00 00 00 00 00")
    conn.open()
    dtcs = obd2.read_dtcs(conn)
    assert len(dtcs) == 1
    assert dtcs[0].code == "P0133"
    assert isinstance(dtcs[0], DTC)


def test_read_dtcs_empty_on_no_data():
    conn = _MockConnector("NO DATA")
    conn.open()
    assert obd2.read_dtcs(conn) == []


def test_read_dtcs_skips_zero_words():
    conn = _MockConnector("43 01 33 00 00 00 00 00")
    conn.open()
    # same as above; zero words are skipped
    assert len(obd2.read_dtcs(conn)) == 1


def test_read_vin_parses_response():
    # VIN: 1G1YY23571A123456 (17 chars) -> hex ASCII
    vin = "1G1YY23571A123456"
    hexvin = "".join(f"{ord(c):02X}" for c in vin)
    resp = "49 02 01 " + " ".join(hexvin[i : i + 2] for i in range(0, len(hexvin), 2))
    conn = _MockConnector(resp)
    conn.open()
    assert obd2.read_vin(conn) == vin


def test_read_vin_returns_none_on_bad_length():
    conn = _MockConnector("49 02 01 31 32 33")
    conn.open()
    assert obd2.read_vin(conn) is None


def test_read_live_data_parses_pids():
    # RPM PID 0x0C: response 41 0C 1A F8 -> (0x1A*256+0xF8)/4 = 1726.0
    conn = _MockConnector("41 0C 1A F8")
    conn.open()
    data = obd2.read_live_data(conn)
    rpm = next((d for d in data if d.name == "EngineRPM"), None)
    assert rpm is not None
    assert rpm.value == 1726.0
    assert rpm.unit == "rpm"
    assert isinstance(rpm, LiveData)


def test_read_live_data_empty_on_no_data():
    conn = _MockConnector("NO DATA")
    conn.open()
    assert obd2.read_live_data(conn) == []


def test_virtual_echo_returns_empty():
    # Virtual (echo) mode: connector echoes the command; parsing yields nothing.
    conn = Elm327Connector("/dev/null", virtual=True)
    conn.open()
    assert obd2.read_dtcs(conn) == []
    assert obd2.read_live_data(conn) == []
    assert obd2.read_vin(conn) is None
    conn.close()


def test_clear_dtcs_sends_mode04():
    conn = _MockConnector("44")
    conn.open()
    obd2.clear_dtcs(conn)
    assert "04" in conn.sent.decode("ascii", errors="replace")
