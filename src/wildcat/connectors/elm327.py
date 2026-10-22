"""ELM327 OBD-II connector.

Communicates with an ELM327-compatible OBD-II adapter over a serial port
(pyserial).  The ELM327 chip implements the full OBD-II command language
(SAE J1979) on top of the lower-level bus; this connector exposes that serial
link as the unified :class:`~wildcat.connectors.base.Connector` interface.

Supported hardware
------------------
* ELM327-compatible Bluetooth / USB-to-UART adapters ("ELM327" or "EMulatore"
  branded).
* Any 3-wire or 4-wire serial OBD-II adapter that the host can open at the
  configured baud rate (default 57600 for ELM327).

Virtual adapter
---------------
Passing ``virtual=True`` instantiates the in-memory echo pipe from
``_virtual.VirtualConnection`` so the driver (lifecycle, serial I/O, reset)
can be unit-tested without a serial port or a physical adapter.
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

DEFAULT_BAUD = 57600
DEFAULT_TIMEOUT = 1.0


class Elm327Connector(Connector, SettingsDriven):
    """An ELM327-compatible OBD-II adapter on a serial port.

    Typical usage::

        adapter = Elm327Connector(port="/dev/ttyACM0", virtual=True)
        # adapter = Elm327Connector(port="COM4")   # physical

        adapter.open()
        adapter.send(b"ATZ\r\n")                  # reset the ELM327 chip
        resp = adapter.recv()                     # "OK"
        adapter.close()
    """

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
        self.name = name or f"ELM327 on {port}"
        self._conn: VirtualConnection | None = None
        self._ser: serial.Serial | None = None
        self._lock = threading.Lock()

        self.adapter = self.name
        self.firmware_version = "1.3"  # representative ELM327 firmware

    # --------------------------------------------------------------- lifecycle

    def open(self) -> None:
        """Open the serial port (virtual or native).

        Errors are raised as :class:`ConnectorError` with a descriptive message
        when the port cannot be opened.
        """
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                logger.warning("ELM327 adapter already open")
                return

            if self.virtual:
                self._conn = VirtualConnection(name=self.name, echo=True)
                self._conn.open()
                self.adapter = f"virtual:{self.name}"
                self.firmware_version = "test"
                logger.info(f"ELM327 opened (virtual): {self.name}")
                return

            self._connect_native()

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
            logger.info(f"ELM327 closed: {self.port}")

    def inject(self, data: bytes) -> None:
        """Simulate an unsolicited hardware response (testing only).

        Raises :class:`ConnectorNotOpenError` if the adapter is not open.
        """
        if self._conn is None or not self._conn.is_open:
            raise ConnectorNotOpenError(f"{self.__class__.__name__} is not open")
        self._conn.inject(data)

    def reset(self) -> None:
        """Reset the adapter.

        Physical: toggle the modem control lines (RTS/DSR) so the ELM327
        re-initialises.  Virtual: flush the pipe.
        """
        with self._lock:
            if self._conn is not None:
                self._conn.reset()
                logger.debug("ELM327 virtual reset")
                return
            if self._ser is None:
                raise ConnectorNotOpenError("ELM327 adapter is not open")
            try:
                self._ser.setRTS(True)   # modem control reset
                self._ser.setDTR(True)
                self._ser.setRTS(False)
                self._ser.setDTR(False)
            except serial.SerialException as exc:
                raise ConnectorError(f"ELM327: failed to reset adapter: {exc}") from exc

    # --------------------------------------------------------------- I/O

    def send(self, data: bytes) -> None:
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                self._conn.send(data)
            elif self._ser is not None:
                try:
                    n = self._ser.write(data)
                    if n != len(data):
                        raise ConnectorError(
                            f"ELM327: partial write ({n}/{len(data)} bytes)"
                        )
                except serial.SerialException as exc:
                    raise ConnectorError(f"ELM327: write failed: {exc}") from exc
            else:
                raise ConnectorNotOpenError("ELM327 adapter is not open")

    def recv(self, timeout: float = DEFAULT_TIMEOUT) -> bytes:
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                return self._conn.recv(timeout)
            if self._ser is not None:
                try:
                    return self._ser.read(self._ser.in_waiting or 1)
                except serial.SerialException as exc:
                    raise ConnectorError(f"ELM327: read failed: {exc}") from exc
            raise ConnectorNotOpenError("ELM327 adapter is not open")

    # --------------------------------------------------------------- native

    def _connect_native(self) -> None:
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
            raise ConnectorError(f"ELM327: cannot open {self.port}: {exc}") from exc
        logger.info(f"ELM327 opened: {self.port} @ {self.baud} baud")

    def is_open(self) -> bool:
        with self._lock:
            if self._conn is not None:
                return self._conn.is_open
            return self._ser is not None and self._ser.is_open
