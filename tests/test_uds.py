"""Tests for the Wildcat UDS (ISO 14229) service helpers.

Run with::

    .venv/bin/python -m pytest tests/test_uds.py -v

All tests use a lightweight virtual connector so they run anywhere without
hardware or vendor DLLs.  Responses are injected deterministically, so the
wire framing (CANFrame / CANProtocol) is exercised separately in
``tests/test_protocol.py``.
"""
from __future__ import annotations

import pytest

from wildcat.connectors.base import ConnectorError
from wildcat.core.ecu import (
    ECUIdentificationError,
    VehicleIdentification,
    parse_ecu_response,
)
from wildcat.core.uds import (
    ClearDTCsError,
    ReadDataByIdentifierError,
    ReadDTCsByStatusMaskError,
    SecurityAccessError,
    UDSService,
    VirtualUDSConnector,
)

# --------------------------------------------------------------------------- #
# FakeUDSConnector — records sends and returns pre-injected responses
# --------------------------------------------------------------------------- #


class FakeUDSConnector(VirtualUDSConnector):
    """Virtual connector that records every sent payload and returns a
    pre-injected response on each ``recv``.

    The responses are supplied as a list (in order); when the list is
    exhausted the connector returns ``b''`` instead of blocking.  This keeps
    the UDS round-trips fast and deterministic.
    """

    def __init__(self, *, responses: list[bytes] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.responses = list(responses) if responses else []
        self.recording: list[bytes] = []

    def send(self, data: bytes) -> None:
        """Record the payload and forward it to the virtual pipe."""
        self.recording.append(bytes(data))
        super().send(data)

    def recv(self, timeout: float = 1.0) -> bytes:
        """Return the next injected response, or ``b''`` when exhausted."""
        if self.responses:
            return self.responses.pop(0)
        return b""


def _ecu_response(vehicle_id: int = 0x43243243, ecu_id: int = 0x12, name: str = "Powertrain") -> bytes:
    """Build a raw ECU identification payload (no UDS header).

    Payload layout: 4-byte vehicle_id | 4-byte ecu_id | name_len | name.
    """
    name_bytes = name.encode("utf-8")
    return (
        vehicle_id.to_bytes(4, "big")
        + ecu_id.to_bytes(4, "big")
        + bytes([len(name_bytes)])
        + name_bytes
    )


# --------------------------------------------------------------------------- #
# UDSService: send_seed / send_key
# --------------------------------------------------------------------------- #


class TestUDSSendSeedKey:
    def test_uds_send_seed(self) -> None:
        conn = FakeUDSConnector(responses=[b"\x27\x01\xA5\x5A\xA5\x5A"])
        conn.open()
        service = UDSService(conn, timeout=1.0)
        seed = service.send_seed(b"\x00\x00\x00\x00")
        assert seed == b"\xA5\x5A\xA5\x5A"
        assert conn.recording == [b"\x27\x04\x00\x00\x00\x00"]
        conn.close()

    def test_uds_send_key(self) -> None:
        conn = FakeUDSConnector(responses=[b"\x29\x01\x01\x02\x03\x04"])
        conn.open()
        service = UDSService(conn, timeout=1.0)
        key = service.send_key(b"\x00\x00\x00\x00")
        assert key == b"\x01\x02\x03\x04"
        assert conn.recording == [b"\x29\x04\x00\x00\x00\x00"]
        conn.close()

    def test_uds_send_seed_rejects_negative_response(self) -> None:
        conn = FakeUDSConnector(responses=[b"\x7F\x71\x31\x00\x00\x00"])
        conn.open()
        service = UDSService(conn, timeout=1.0)
        with pytest.raises(SecurityAccessError):
            service.send_seed(b"\x00\x00\x00\x00")
        conn.close()

    def test_uds_send_key_rejects_negative_response(self) -> None:
        conn = FakeUDSConnector(responses=[b"\x7F\x71\x31\x00\x00\x00"])
        conn.open()
        service = UDSService(conn, timeout=1.0)
        with pytest.raises(SecurityAccessError):
            service.send_key(b"\x00\x00\x00\x00")
        conn.close()


# --------------------------------------------------------------------------- #
# UDSService: read_dtc / clear_dtc
# --------------------------------------------------------------------------- #


class TestUDSReadDTC:
    def test_uds_read_dtc(self) -> None:
        # Positive response 0x21 0x01, then two 7-byte DTC records:
        #   [present(1), code(2), flags(1), count(1), reserved(2)]
        conn = FakeUDSConnector(responses=[
            b"\x21\x01"
            + b"\x00\x00\x01\x00\x00\x00\x00"      # record 1: 0x0001
            + b"\x00\x00\x3C\x00\x00\x00\x00",     # record 2: 0x003C
        ])
        conn.open()
        service = UDSService(conn, timeout=1.0)
        dtcs = service.read_dtc()
        assert len(dtcs) == 2
        assert dtcs[0] == {
            "code": "0001",
            "description": "Powertrain — cylinder misfire detected",
        }
        assert dtcs[1]["code"] == "003C"
        conn.close()

    def test_uds_read_dtc_rejects_bad_response(self) -> None:
        conn = FakeUDSConnector(responses=[b"\x7F\x71\x31"])
        conn.open()
        service = UDSService(conn, timeout=1.0)
        with pytest.raises(ReadDTCsByStatusMaskError):
            service.read_dtc()
        conn.close()

    def test_uds_clear_dtc(self) -> None:
        conn = FakeUDSConnector(responses=[b"\x24\x01"])
        conn.open()
        service = UDSService(conn, timeout=1.0)
        service.clear_dtc()
        assert conn.recording == [b"\x04\x01"]
        conn.close()

    def test_uds_clear_dtc_rejects_bad_response(self) -> None:
        conn = FakeUDSConnector(responses=[b"\x7F\x71\x31"])
        conn.open()
        service = UDSService(conn, timeout=1.0)
        with pytest.raises(ClearDTCsError):
            service.clear_dtc()
        conn.close()


# --------------------------------------------------------------------------- #
# UDSService: read_live_data
# --------------------------------------------------------------------------- #


class TestUDSReadLiveData:
    def test_uds_read_live_data(self) -> None:
        # Value 12.5 as a big-endian IEEE-754 single: 0x3F800000 = b'\x3F\x80\x00\x00'
        # Record: [present(1), name_len(1), name(n), identifier(2), value(4), unit_len(1), unit(n)]
        conn = FakeUDSConnector(responses=[
            b"\x21\x01"
            + b"\x00"            # present
            + b"\x09"            # name_len = 9
            + b"EngineRPM"       # name
            + b"\x00\x21"        # identifier
            + b"\x41\x48\x00\x00"  # value = 12.5 (big-endian float)
            + b"\x03"            # unit_len = 3
            + b"rpm"             # unit
            + b"\x00",           # end-of-payload present flag
        ])
        conn.open()
        service = UDSService(conn, timeout=1.0)
        data = service.read_live_data([0x21])
        assert len(data) == 1
        assert data[0] == {
            "name": "EngineRPM",
            "value": 12.5,
            "unit": "rpm",
        }
        conn.close()

    def test_uds_read_live_data_rejects_bad_response(self) -> None:
        conn = FakeUDSConnector(responses=[b"\x7F\x71\x31"])
        conn.open()
        service = UDSService(conn, timeout=1.0)
        with pytest.raises(ReadDataByIdentifierError):
            service.read_live_data([0x21])
        conn.close()


# --------------------------------------------------------------------------- #
# UDSService: ecu_id / security_access
# --------------------------------------------------------------------------- #


class TestUDSEcuIdSecurityAccess:
    def test_uds_read_ecu_id(self) -> None:
        conn = VirtualUDSConnector()
        conn.open()
        service = UDSService(conn, timeout=1.0, ecu_id=0x2E)
        assert service.ecu_id() == 0x2E
        conn.close()

    def test_uds_security_access_flag(self) -> None:
        conn = VirtualUDSConnector()
        conn.open()
        service = UDSService(conn, timeout=1.0, security_access=False)
        assert service.security_access() is False
        conn.close()

    def test_uds_rejects_closed_connector(self) -> None:
        closed = VirtualUDSConnector()
        closed.close()
        with pytest.raises(ConnectorError):
            UDSService(closed, timeout=1.0)


# --------------------------------------------------------------------------- #
# UDSService: session end-to-end (SendSeed -> SeedResponse -> ReadDataByIdentifier -> Data)
# --------------------------------------------------------------------------- #


class TestUDSSessionEndToEnd:
    def test_uds_session_end_to_end(self) -> None:
        # Inject the full set of responses before driving the service, so every
        # UDS round-trip is deterministic.
        conn = FakeUDSConnector()
        conn.responses = [
            b"\x27\x01\xA5\x5A\xA5\x5A",                      # seed response
            b"\x29\x01\x01\x02\x03\x04",                      # key response
            b"\x21\x01" + b"\x00\x00\x01\x00\x00\x00\x00",     # DTC response (0x0001)
            b"\x21\x01"
            + b"\x00"            # present
            + b"\x09"            # name_len = 9
            + b"EngineRPM"       # name
            + b"\x00\x21"        # identifier
            + b"\x41\x48\x00\x00"  # value = 12.5 (big-endian float)
            + b"\x03"            # unit_len = 3
            + b"rpm"             # unit
            + b"\x00",           # end-of-payload present flag
            b"\x24\x01",                      # clear DTC response
        ]
        conn.open()
        service = UDSService(conn, timeout=1.0)

        service.send_seed(b"\x00\x00\x00\x00")          # request seed
        seed = service.send_key(b"\xA5\x5A\xA5\x5A")   # respond with seed
        assert seed == b"\x01\x02\x03\x04"

        dtcs = service.read_dtc()
        assert len(dtcs) == 1
        assert dtcs[0]["code"] == "0001"

        live = service.read_live_data([0x21])
        assert len(live) == 1
        assert live[0]["name"] == "EngineRPM"
        assert live[0]["value"] == 12.5

        service.clear_dtc()
        assert conn.recording[-1] == b"\x04\x01"

        conn.close()


# --------------------------------------------------------------------------- #
# Vehicle identification (ecu.py)
# --------------------------------------------------------------------------- #


class TestVehicleIdentification:
    def test_parse_ecu_response(self) -> None:
        payload = _ecu_response(vehicle_id=0x43243243, ecu_id=0x12, name="Powertrain")
        decoded = parse_ecu_response(payload)
        assert decoded == {
            "vehicle_id": 0x43243243,
            "ecu_id": 0x12,
            "name": "Powertrain",
        }

    def test_parse_ecu_response_rejects_truncated(self) -> None:
        with pytest.raises(ECUIdentificationError):
            parse_ecu_response(b"\x00" * 8)

    def test_identify(self) -> None:
        conn = FakeUDSConnector(responses=[b"\x50\x01" + _ecu_response()])
        conn.open()

        # A minimal stub car: exposes ecu_id() and name().
        class _Car:
            def ecu_id(self) -> int:
                return 0x12

            @property
            def name(self) -> str:
                return "Mercedes C300 (2008)"

        ident = VehicleIdentification()
        ecu = ident.identify(conn, _Car())
        assert ecu.vehicle_id == 0x43243243
        assert ecu.ecu_id == 0x12
        assert ecu.name == "Powertrain"
        assert ecu.address == "0x12"
        conn.close()

    def test_identify_closed_connector_raises(self) -> None:
        conn = VirtualUDSConnector()
        conn.close()

        class _Car:
            def ecu_id(self) -> int:
                return 0x12

            @property
            def name(self) -> str:
                return "Mercedes C300 (2008)"

        ident = VehicleIdentification()
        with pytest.raises(ConnectorError):
            ident.identify(conn, _Car())
