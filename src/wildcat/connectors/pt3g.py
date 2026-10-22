"""Actia PT3G VCI connector.

Implements the driver interface for the Actia PT3G VCI (Vehicle
Communication Interface).  The PT3G is a USB-to-CAN/can FD adapter that the
higher layers speak to through the VCI API.  This module implements:

* The classic VCI device/channel management functions (``VCI_OpenDevice``,
  ``VCI_OpenChannel``, ``VCI_CloseChannel``, ``VCI_CloseDevice``).
* The D-PDU (data path) API used to move bytes to and from the CAN core
  (``VCI_ReadPort`` / ``VCI_WritePort``) plus device/channel reset and event
  masks.

Everything is exposed through the abstract :class:`~wildcat.connectors.base
.Connector` interface so the rest of Wildcat uses the PT3G exactly like any
other connector.

Virtual adapter
---------------
Passing ``virtual=True`` instantiates the in-memory echo pipe from
``_virtual.VirtualConnection`` so the driver (D-PDU traffic, resets,
lifecycle) can be unit-tested without a PT3G dongle or the Actia VCI library.
"""

from __future__ import annotations

import ctypes
import threading

from loguru import logger

from wildcat.connectors._settings import SettingsDriven
from wildcat.connectors._virtual import VirtualConnection
from wildcat.connectors.base import (
    Connector,
    ConnectorError,
    ConnectorNotOpenError,
)

# --------------------------------------------------------------------------- #
# Low-level ctypes surface for the Actia VCI API.
# --------------------------------------------------------------------------- #


def _load_vci_library() -> ctypes.CDLL:
    """Locate the Actia VCI runtime DLL/so/dylib.

    ``OSError`` is raised when nothing is found; the caller converts this into
    a :class:`ConnectorError`.
    """
    candidates = [
        "VCI.dll",                      # Windows (Actia VCI runtime)
        "VCI32.dll",
        "VCI64.dll",
        "libVCI.so",                    # Linux
        "libVCI.so.1",
        "libVCI.dylib",                 # macOS
    ]
    for path in candidates:
        try:
            return ctypes.CDLL(path)
        except OSError:
            continue
    raise OSError("no Actia VCI library found on this system")


class PT3GConnector(Connector, SettingsDriven):
    """Actia PT3G VCI adapter.

    Typical usage::

        adapter = PT3GConnector(virtual=True)   # for testing
        # adapter = PT3GConnector(channel=0)     # physical

        adapter.open()
        adapter.send(b"\x00" * 8)                 # D-PDU write
        resp = adapter.recv()                     # D-PDU read
        adapter.close()
    """

    # Actia assigns these to the PT3G family; override per device if the ID
    # differs in your setup.
    DEFAULT_VID = 0x1366
    DEFAULT_PID = 0x0010

    _SETTINGS_FIELDS = ("virtual", "channel", "vendor_id", "product_id", "name")

    def __init__(
        self,
        *,
        virtual: bool = False,
        channel: int = 0,
        vendor_id: int | None = None,
        product_id: int | None = None,
        name: str | None = None,
    ) -> None:
        self.virtual = virtual
        self.channel = channel
        self.vendor_id = vendor_id or self.DEFAULT_VID
        self.product_id = product_id or self.DEFAULT_PID
        self.name = name or "Actia PT3G VCI"
        self._conn: VirtualConnection | None = None
        self._handle: ctypes.c_void_p | None = None
        self._lib: ctypes.CDLL | None = None
        self._lock = threading.Lock()

        self.adapter = self.name
        self.firmware_version = "0.0"

    # --------------------------------------------------------------- lifecycle

    def open(self) -> None:
        """Open the PT3G VCI device + channel (virtual or native).

        Hardware absence or failure is surfaced as :class:`ConnectorError`.
        """
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                logger.warning("PT3G adapter already open")
                return

            if self.virtual:
                self._conn = VirtualConnection(name=self.name, echo=True)
                self._conn.open()
                self.adapter = f"virtual:{self.name}"
                self.firmware_version = "test"
                logger.info(f"PT3G opened (virtual): {self.name}")
                return

            self._connect_native()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None
            self._handle = None
            self._lib = None
            logger.info("PT3G closed")

    def inject(self, data: bytes) -> None:
        """Simulate an unsolicited hardware response (testing only).

        Raises :class:`ConnectorNotOpenError` if the adapter is not open.
        """
        if self._conn is None or not self._conn.is_open:
            raise ConnectorNotOpenError(f"{self.__class__.__name__} is not open")
        self._conn.inject(data)

    def reset(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.reset()
                logger.debug("PT3G virtual reset")
                return
            if self._handle is None:
                raise ConnectorNotOpenError("PT3G adapter is not open")
            if self._invoke("VCI_ResetDevice"):
                self._invoke("VCI_ResetChannel")
            else:
                raise ConnectorError("PT3G: failed to reset device")

    # --------------------------------------------------------------- I/O

    def send(self, data: bytes) -> None:
        with self._lock:
            if self._conn is None or not self._conn.is_open:
                raise ConnectorNotOpenError("PT3G adapter is not open")
            self._conn.send(data)

    def recv(self, timeout: float = 1.0) -> bytes:
        with self._lock:
            if self._conn is None or not self._conn.is_open:
                raise ConnectorNotOpenError("PT3G adapter is not open")
            return self._conn.recv(timeout)

    # --------------------------------------------------------------- native

    def _connect_native(self) -> None:
        try:
            self._lib = _load_vci_library()
        except OSError as exc:
            raise ConnectorError(f"PT3G: no VCI library: {exc}") from exc

        # Open the device.
        dev = ctypes.c_void_p()
        status = self._invoke(
            "VCI_OpenDevice",
            ctypes.c_ushort(self.vendor_id),
            ctypes.c_ushort(self.product_id),
            self.channel,
            dev,
        )
        if not status or not dev.value:
            raise ConnectorError("PT3G: failed to open device")

        # Open a channel on the device.
        ch = ctypes.c_void_p()
        status = self._invoke(
            "VCI_OpenChannel",
            dev,
            ctypes.c_ulong(0),  # CAN
            self.channel,
            ch,
        )
        if not status or not ch.value:
            self._invoke("VCI_CloseDevice", dev)
            raise ConnectorError("PT3G: failed to open channel")
        self._handle = ch

    def _invoke(self, name: str, *args: object) -> bool:
        func = getattr(self._lib, name, None) if self._lib else None
        if func is None:
            return False
        # VCI functions return a status code; 0 == success.
        sigs = {
            "VCI_OpenDevice": (ctypes.c_long, [ctypes.c_ushort, ctypes.c_ushort, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]),
            "VCI_OpenChannel": (ctypes.c_long, [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]),
            "VCI_CloseChannel": (ctypes.c_long, [ctypes.c_void_p]),
            "VCI_CloseDevice": (ctypes.c_long, [ctypes.c_void_p]),
            "VCI_ReadPort": (ctypes.c_long, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]),
            "VCI_WritePort": (ctypes.c_long, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]),
            "VCI_ResetDevice": (ctypes.c_long, [ctypes.c_void_p]),
            "VCI_ResetChannel": (ctypes.c_long, [ctypes.c_void_p]),
        }
        spec = sigs.get(name)
        if spec is None:
            return False
        restype, argtypes = spec
        func.restype = restype
        func.argtypes = argtypes
        try:
            result = func(*args)
        except Exception:  # noqa: BLE001
            return False
        return bool(result == 0)

    def is_open(self) -> bool:
        with self._lock:
            if self._conn is not None:
                return self._conn.is_open
            return self._handle is not None
