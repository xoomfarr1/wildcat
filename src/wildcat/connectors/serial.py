"""Raw serial (FTDI) connector for K-line / KWP2000 and slcan adapters.

This is the transport for the BMW K+DCAN and VAG-COM cables: a plain
UART over pyserial (FTDI chip).  Unlike :class:`Elm327Connector` it does
NOT speak the ELM327 command language; bytes go straight to the wire so
the protocol layer (K-line init, KWP2000, UDS) can drive the adapter.

Virtual mode uses the in-memory echo pipe from ``_virtual`` so the
lifecycle and I/O can be unit-tested without hardware.
"""
from __future__ import annotations

import threading

import serial
from loguru import logger

from wildcat.connectors._settings import SettingsDriven
from wildcat.connectors._virtual import VirtualConnection
from wildcat.connectors.base import (
    Connector,
    ConnectorError,
    ConnectorNotOpenError,
)

DEFAULT_BAUD = 10400  # K-line default
DEFAULT_TIMEOUT = 1.0


class SerialConnector(Connector, SettingsDriven):
    """A raw serial (FTDI) adapter — no protocol framing of its own."""

    _SETTINGS_FIELDS = ("virtual", "baud", "timeout", "name", "port")

    def __init__(
        self,
        port: str,
        *,
        baud: int = DEFAULT_BAUD,
        timeout: float = DEFAULT_TIMEOUT,
        virtual: bool = False,
        name: str | None = None,
    ) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.virtual = virtual
        self.name = name or f"Serial on {port}"
        self._conn: VirtualConnection | None = None
        self._ser: serial.Serial | None = None
        self._lock = threading.Lock()
        self.adapter = self.name

    def open(self) -> None:
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                logger.warning("Serial adapter already open")
                return
            if self.virtual:
                self._conn = VirtualConnection(name=self.name, echo=True)
                self._conn.open()
                self.adapter = f"virtual:{self.name}"
                logger.info(f"Serial opened (virtual): {self.name}")
                return
            try:
                self._ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baud,
                    timeout=self.timeout,
                    write_timeout=self.timeout,
                    dsrdtr=False,
                    rtscts=False,
                )
            except serial.SerialException as exc:
                raise ConnectorError(f"Serial: cannot open {self.port}: {exc}") from exc
            logger.info(f"Serial opened: {self.port} @ {self.baud} baud")

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None
            if self._ser is not None:
                try:
                    self._ser.close()
                finally:
                    self._ser = None
            logger.info(f"Serial closed: {self.port}")

    def inject(self, data: bytes) -> None:
        if self._conn is None or not self._conn.is_open:
            raise ConnectorNotOpenError("Serial adapter is not open")
        self._conn.inject(data)

    def reset(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.reset()
                return
            if self._ser is None:
                raise ConnectorNotOpenError("Serial adapter is not open")
            try:
                self._ser.setRTS(True)
                self._ser.setDTR(True)
                self._ser.setRTS(False)
                self._ser.setDTR(False)
            except serial.SerialException as exc:
                raise ConnectorError(f"Serial: reset failed: {exc}") from exc

    def send(self, data: bytes) -> None:
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                self._conn.send(data)
            elif self._ser is not None:
                try:
                    n = self._ser.write(data)
                    if n != len(data):
                        raise ConnectorError(
                            f"Serial: partial write ({n}/{len(data)} bytes)"
                        )
                except serial.SerialException as exc:
                    raise ConnectorError(f"Serial: write failed: {exc}") from exc
            else:
                raise ConnectorNotOpenError("Serial adapter is not open")

    def recv(self, timeout: float = DEFAULT_TIMEOUT) -> bytes:
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                return self._conn.recv(timeout)
            if self._ser is not None:
                try:
                    return self._ser.read(self._ser.in_waiting or 1)
                except serial.SerialException as exc:
                    raise ConnectorError(f"Serial: read failed: {exc}") from exc
            raise ConnectorNotOpenError("Serial adapter is not open")

    def is_open(self) -> bool:
        with self._lock:
            if self._conn is not None:
                return self._conn.is_open
            return self._ser is not None and self._ser.is_open
