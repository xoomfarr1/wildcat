"""Session management — the central entry point for a diagnostic session.

A session owns a connector, a protocol, and a car, and presents a simple API for
the application layer to use.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from wildcat.cars.base import CarModel
from wildcat.connectors.base import Connector, ConnectorError


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

    def connect(self) -> None:
        """Open the hardware connection."""
        self.connector.open()
        self._connected = True
        logger.info(f"Connected: {self.car.name} via {self.connector.__class__.__name__}")

    def disconnect(self) -> None:
        """Close the hardware connection."""
        self.connector.close()
        self._connected = False
        logger.info("Disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def read_dtc(self) -> list:
        """Read fault codes from the vehicle."""
        if not self._connected:
            raise ConnectorError("Session not connected")
        return self.car.get_dtc_reader()

    def read_live_data(self, keys=None):
        """Read live data from the vehicle."""
        if not self._connected:
            raise ConnectorError("Session not connected")
        return self.car.get_live_data(keys)

    def clear_dtc(self) -> None:
        if not self._connected:
            raise ConnectorError("Session not connected")
        self.car.clear_dtc()
