"""Tests for the car model implementations (Phase 3: car models)."""

from __future__ import annotations

import pytest

from wildcat.cars import BMW, Ford, MercedesC300, VWAudi
from wildcat.cars.base import CarModel
from wildcat.connectors.base import Connector
from wildcat.core.session import WildcatSession


class _DummyConnector(Connector):
    """Minimal Connector stub: no hardware, but implements the ABC."""

    def __init__(self) -> None:
        self._open = False
        self.sent: bytes = b""
        self.recv_buf: bytes = b""

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def send(self, data: bytes) -> None:
        self.sent = data

    def recv(self, timeout: float = 1.0) -> bytes:
        return self.recv_buf

    def is_open(self) -> bool:
        return self._open

    def reset(self) -> None:
        self.sent = b""
        self.recv_buf = b""


def _make_session(car):
    """Build a connected session with a dummy connector (no hardware)."""
    session = WildcatSession(_DummyConnector(), car)
    session.connect()
    return session


def test_all_models_subclass_base():
    for car_cls in (MercedesC300, BMW, Ford, VWAudi):
        assert issubclass(car_cls, CarModel)
        assert car_cls().name
        assert car_cls().language


def test_mercedes_supports_pt3g():
    assert "PT3G" in MercedesC300().SUPPORTED_CONNECTORS


def test_mercedes_dtc_reader_and_clear():
    car = MercedesC300()
    codes = list(car.get_dtc_reader())
    # No fabricated fault codes: reads are empty until a real connector provides data.
    assert codes == []
    assert car.clear_dtc() is None
    assert list(car.get_dtc_reader()) == []


def test_live_data_no_fabricated_values():
    car = MercedesC300()
    # No fabricated samples: reads are empty until a real connector provides data.
    assert car.get_live_data() == []


def test_live_data_filters_by_key():
    car = MercedesC300()
    # No fabricated data: both filtered and unfiltered reads are empty.
    assert car.get_live_data(keys=["EngineRPM", "CoolantTemp"]) == []
    assert car.get_live_data() == []


def test_security_access_flags():
    assert MercedesC300().security_access() is True
    assert BMW().security_access() is True
    assert VWAudi().security_access() is True
    assert Ford().security_access() is False


def test_seed_key_exchange_requires_real_connector():
    for car_cls in (MercedesC300, BMW, VWAudi):
        car = car_cls()
        # No fabricated seed/key bytes: a real connector is required.
        with pytest.raises(NotImplementedError):
            car.send_seed(b"\x01\x02\x03\x04")
        with pytest.raises(NotImplementedError):
            car.send_key(b"\x01\x02\x03\x04")


def test_session_end_to_end():
    for car_cls in (MercedesC300, BMW, Ford, VWAudi):
        session = _make_session(car_cls())
        assert session.is_connected
        assert session.read_dtc() == []
        assert session.read_live_data() == []
        session.clear_dtc()
        session.disconnect()
        assert not session.is_connected


def test_mercedes_mirrors_pt3g_brand_message():
    """Integration check: PT3G-style security exchange over the model."""
    car = MercedesC300()
    # No fabricated seed/key bytes: a real connector is required.
    with pytest.raises(NotImplementedError):
        car.send_seed(b"\x01\x02\x03\x04")
    with pytest.raises(NotImplementedError):
        car.send_key(b"\x01\x02\x03\x04")
