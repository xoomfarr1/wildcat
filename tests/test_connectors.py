"""Tests for the connector drivers.

Run with::

    .venv/bin/python -m pytest tests/ -v

All tests use the in-memory *virtual* adapters so they run anywhere without
hardware or vendor DLLs.  Native open paths are exercised only for their error
handling (a missing DLL / port must surface as ``ConnectorError``).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wildcat.connectors._settings import ConnectorSettings
from wildcat.connectors._virtual import VirtualConnection
from wildcat.connectors.base import Connector, ConnectorError, ConnectorNotOpenError
from wildcat.connectors.elm327 import Elm327Connector
from wildcat.connectors.j2534 import J2534Connector
from wildcat.connectors.pt3g import PT3GConnector
from wildcat.connectors.serial import SerialConnector
from wildcat.connectors.usbcan import UsbCANConnector

VIRT = {"virtual": True}


# --------------------------------------------------------------------------- #
# J2534
# --------------------------------------------------------------------------- #


class TestJ2534Virtual:
    def test_open_close(self):
        a = J2534Connector(**VIRT)
        a.open()
        assert a.is_open() is True
        a.close()
        assert a.is_open() is False

    def test_round_trip_echo(self):
        a = J2534Connector(**VIRT)
        a.open()
        a.send(b"\x02\x01\x00\x00\x00\x00\x00\x00")
        assert a._conn.bytes_sent == 8
        recv = a.recv()
        assert recv == b"\x02\x01\x00\x00\x00\x00\x00\x00"
        assert a._conn.bytes_received == 8
        a.close()

    def test_inject_solicited_response(self):
        a = J2534Connector(**VIRT)
        a.open()
        a.inject(b"RESPONSE")
        assert a.recv() == b"RESPONSE"
        a.close()

    def test_counters_reset_on_open(self):
        a = J2534Connector(**VIRT)
        a.open()
        a.send(b"data")
        a.close()
        a.open()  # reopen resets counters
        a.send(b"x")
        assert a._conn.bytes_sent == 1
        a.close()

    def test_send_on_closed_raises(self):
        a = J2534Connector(**VIRT)
        with pytest.raises(ConnectorNotOpenError):
            a.send(b"x")

    def test_recv_on_closed_raises(self):
        a = J2534Connector(**VIRT)
        with pytest.raises(ConnectorNotOpenError):
            a.recv()

    def test_list_adapters_returns_a_entry(self):
        adapters = J2534Connector.list_adapters()
        assert isinstance(adapters, list)
        assert len(adapters) >= 1

    def test_timeout_returns_empty(self):
        conn = VirtualConnection(name="t", echo=False)
        conn.open()
        assert conn.recv(timeout=0.01) == b""
        conn.close()


class TestJ2534NativeOpenFailure:
    def test_open_without_library_raises(self):
        # No J2534 DLL on disk -> open must fail gracefully with ConnectorError.
        a = J2534Connector(virtual=False, name="no-lib")
        with pytest.raises(ConnectorError):
            a.open()


# --------------------------------------------------------------------------- #
# PT3G
# --------------------------------------------------------------------------- #


class TestPT3GVirtual:
    def test_open_close(self):
        a = PT3GConnector(**VIRT)
        a.open()
        assert a.is_open() is True
        a.close()
        assert a.is_open() is False

    def test_round_trip(self):
        a = PT3GConnector(**VIRT)
        a.open()
        a.send(b"\x00" * 16)
        assert a._conn.bytes_sent == 16
        assert a.recv() == b"\x00" * 16
        assert a._conn.bytes_received == 16
        a.close()

    def test_inject(self):
        a = PT3GConnector(**VIRT)
        a.open()
        a.inject(b"VCI-DATA")
        assert a.recv() == b"VCI-DATA"
        a.close()

    def test_send_before_open_raises(self):
        a = PT3GConnector(**VIRT)
        with pytest.raises(ConnectorNotOpenError):
            a.send(b"x")


class TestPT3GNativeOpenFailure:
    def test_open_without_library_raises(self):
        a = PT3GConnector(virtual=False, name="no-lib")
        with pytest.raises(ConnectorError):
            a.open()


# --------------------------------------------------------------------------- #
# ELM327
# --------------------------------------------------------------------------- #


class TestElm327Virtual:
    def test_open_close(self):
        a = Elm327Connector("/dev/null", **VIRT)
        a.open()
        assert a.is_open() is True
        a.close()
        assert a.is_open() is False

    def test_round_trip(self):
        a = Elm327Connector("/dev/null", **VIRT)
        a.open()
        a.send(b"ATZ\r\n")
        assert a._conn.bytes_sent == 5
        assert a.recv() == b"ATZ\r\n"
        assert a._conn.bytes_received == 5
        a.close()

    def test_inject(self):
        a = Elm327Connector("/dev/null", **VIRT)
        a.open()
        a.inject(b"OK")
        assert a.recv() == b"OK"
        a.close()

    def test_reset_virtual(self):
        a = Elm327Connector("/dev/null", **VIRT)
        a.open()
        a.reset()
        a.close()

    def test_send_before_open_raises(self):
        a = Elm327Connector("/dev/null", **VIRT)
        with pytest.raises(ConnectorNotOpenError):
            a.send(b"x")


class TestElm327NativeOpenFailure:
    def test_open_without_port_raises(self):
        a = Elm327Connector("/dev/ttyNOWHERE", virtual=False)
        with pytest.raises(ConnectorError):
            a.open()


# --------------------------------------------------------------------------- #
# USB-CAN
# --------------------------------------------------------------------------- #


class TestUsbCANVirtual:
    def test_open_close(self):
        a = UsbCANConnector(virtual=True, backend="generic")
        a.open()
        assert a.is_open() is True
        a.close()
        assert a.is_open() is False

    def test_round_trip(self):
        a = UsbCANConnector(virtual=True, backend="generic")
        a.open()
        a.send(b"\x00" * 8)
        assert a._conn.bytes_sent == 8
        assert a.recv() == b"\x00" * 8
        assert a._conn.bytes_received == 8
        a.close()

    def test_inject(self):
        a = UsbCANConnector(virtual=True, backend="generic")
        a.open()
        a.inject(b"IXXAT-RESPONSE")
        assert a.recv() == b"IXXAT-RESPONSE"
        a.close()

    def test_list_adapters_returns_a_entry(self):
        adapters = UsbCANConnector.list_adapters()
        assert isinstance(adapters, list)
        assert len(adapters) >= 1

    def test_send_before_open_raises(self):
        a = UsbCANConnector(virtual=True, backend="generic")
        with pytest.raises(ConnectorNotOpenError):
            a.send(b"x")


class TestUsbCANNativeOpenFailure:
    def test_open_without_sdk_raises(self):
        # No PCAN/IXXAT SDK present -> open must fail gracefully.
        a = UsbCANConnector(virtual=False, backend="generic")
        with pytest.raises(ConnectorError):
            a.open()


# --------------------------------------------------------------------------- #
# Shared connector contract
# --------------------------------------------------------------------------- #


class TestConnectorContract:
    def test_all_implement_the_base(self):
        for conn_cls in (J2534Connector, PT3GConnector, Elm327Connector, UsbCANConnector, SerialConnector):
            assert issubclass(conn_cls, Connector)
            for method in ("open", "close", "send", "recv", "is_open", "reset"):
                assert callable(getattr(conn_cls, method))

    def test_settings_snapshot_is_validated(self):
        a = J2534Connector(virtual=True, vendor_id=0x1234, product_id=0x5678, channel=2)
        s = a.settings
        assert s.virtual is True
        assert s.vendor_id == 0x1234
        assert s.product_id == 0x5678
        assert s.channel == 2
        assert s.name == "J2534 pass-thru adapter"

    def test_bad_settings_rejected(self):
        with pytest.raises(ValidationError):
            ConnectorSettings(baud=500)
