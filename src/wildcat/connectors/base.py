"""Connector abstraction for vehicle diagnostic hardware.

Every physical interface (J2534 pass-thru, Actia PT3G VCI, ELM327 OBD-II, USB-CAN)
implements this abstract base so the rest of Wildcat never knows which hardware it
is talking to.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ConnectorError(Exception):
    """Base exception for connector operations."""


class ConnectorNotOpenError(ConnectorError):
    """Raised when an operation requires an open connection."""


class Connector(ABC):
    """Base class for all vehicle diagnostic connectors."""

    @abstractmethod
    def open(self) -> None:
        """Open the physical connection to the hardware."""

    @abstractmethod
    def close(self) -> None:
        """Close the physical connection to the hardware."""

    @abstractmethod
    def send(self, data: bytes) -> None:
        """Send raw bytes to the connected hardware."""

    @abstractmethod
    def recv(self, timeout: float = 1.0) -> bytes:
        """Receive raw bytes from the connected hardware."""

    @abstractmethod
    def is_open(self) -> bool:
        """Return True if the connection is open."""

    @abstractmethod
    def reset(self) -> None:
        """Perform a hardware-level reset if supported."""
