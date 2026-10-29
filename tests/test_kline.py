"""Tests for the K-line (BMW/VAG) session over a raw serial link."""
from __future__ import annotations

from wildcat.connectors.serial import SerialConnector
from wildcat.core.session import WildcatSession
from wildcat.protocol.kline import KLineSession, fast_init, slow_init


def test_fast_init_virtual_returns_false():
    conn = SerialConnector("VIRTUAL", virtual=True)
    conn.open()
    assert fast_init(conn) is False
    conn.close()


def test_slow_init_virtual_returns_false():
    conn = SerialConnector("VIRTUAL", virtual=True)
    conn.open()
    assert slow_init(conn) is False
    conn.close()


def test_kline_session_virtual_not_established():
    conn = SerialConnector("VIRTUAL", virtual=True)
    conn.open()
    sess = KLineSession(conn)
    assert sess.established is False
    assert sess.read_dtcs() == []
    assert sess.read_live_data() == []
    conn.close()


def test_session_routes_serial_to_kline():
    from wildcat.cars import BMW

    conn = SerialConnector("VIRTUAL", virtual=True)
    session = WildcatSession(conn, BMW())
    session.connect()
    assert session.is_connected
    assert session.read_dtc() == []
    assert session.read_live_data() == []
    session.disconnect()
    assert not session.is_connected
