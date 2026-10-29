"""Session management — the central entry point for a diagnostic session.

A session owns a connector, a protocol, and a car, and presents a simple API for
the application layer to use.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from wildcat.cars.base import CarModel
from wildcat.connectors.base import Connector, ConnectorError
from wildcat.connectors.elm327 import Elm327Connector
from wildcat.connectors.serial import SerialConnector
from wildcat.diagnostics import obd2 as _obd2
from wildcat.protocol.kline import KLineSession as _KLineSession


@dataclass
class WildcatConfig:
    """Runtime configuration for a session."""

    language: str = "EN"
    verbose: bool = False
    log_file: str | None = None


class WildcatSession:
    """Central diagnostic session.

    Typical usage::

        session = WildcatSession(connector, car)
        session.connect()
        dtcs = session.read_dtc()
        session.disconnect()
    """

    def __init__(self, connector: Connector, car: CarModel, config: WildcatConfig | None = None):
        self.connector = connector
        self.car = car
        self.config = config or WildcatConfig()
        self._connected = False
        self._kline: _KLineSession | None = None

    def connect(self) -> None:
        """Open the hardware connection."""
        self.connector.open()
        self._connected = True
        if isinstance(self.connector, SerialConnector):
            self._kline = _KLineSession(self.connector)
        logger.info(f"Connected: {self.car.name} via {self.connector.__class__.__name__}")

    def disconnect(self) -> None:
        """Close the hardware connection."""
        self.connector.close()
        self._connected = False
        self._kline = None
        logger.info("Disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def read_dtc(self) -> list:
        """Read fault codes from the vehicle."""
        if not self._connected:
            raise ConnectorError("Session not connected")
        if isinstance(self.connector, Elm327Connector):
            return _obd2.read_dtcs(self.connector)
        if isinstance(self.connector, SerialConnector):
            if self._kline is None:
                self._kline = _KLineSession(self.connector)
            return self._kline.read_dtcs()
        return self.car.get_dtc_reader()

    def read_live_data(self, keys=None):
        """Read live data from the vehicle."""
        if not self._connected:
            raise ConnectorError("Session not connected")
        if isinstance(self.connector, Elm327Connector):
            return _obd2.read_live_data(self.connector)
        if isinstance(self.connector, SerialConnector):
            if self._kline is None:
                self._kline = _KLineSession(self.connector)
            return self._kline.read_live_data()
        return self.car.get_live_data(keys)

    def clear_dtc(self) -> None:
        if not self._connected:
            raise ConnectorError("Session not connected")
        if isinstance(self.connector, Elm327Connector):
            _obd2.clear_dtcs(self.connector)
            return
        if isinstance(self.connector, SerialConnector):
            if self._kline is None:
                self._kline = _KLineSession(self.connector)
            self._kline.clear_dtcs()
            return
        self.car.clear_dtc()
