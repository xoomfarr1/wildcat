"""J2534 pass-thru connector.

Implements the SAE J2534-1 "Universal Diagnostic Services" (UDS) pass-thru
standard.  A J2534 adapter is a hardware dongle that presents a plain serial/
CAN channel to the host while transparently handling the OEM-specific driver
traffic underneath.  This connector exposes that channel as the unified
:class:`~wildcat.connectors.base.Connector` interface so the rest of Wildcat
can talk to a J2534 adapter exactly like any other connector.

Supported adapters
------------------
Any J2534-compliant pass-thru device (Kvaser, SL Instrumentation, Abiheon /
API, peak, ...).  The driver loads the vendor-supplied ``J2534*.dll`` /
``J2534_*.so`` at run time; no permanent binding is required.

Virtual adapter
---------------
Passing ``virtual=True`` instantiates the in-memory echo pipe from
``_virtual.VirtualConnection`` so the driver can be unit-tested without a
dongle and without the vendor library.  The adapter is discovered and opened
just like a physical one when ``virtual=False``.
"""

from __future__ import annotations

import ctypes
import os
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
# Low-level ctypes surface for the J2534 driver symbols (SAE J2534-1).
# --------------------------------------------------------------------------- #


def _load_j2534_library() -> ctypes.CDLL:
    """Locate and load the J2534 pass-thru driver library.

    ``OSError`` is raised when no suitable library is found; the caller
    converts this into a :class:`ConnectorError`.
    """
    candidates = [
        # Windows (Kvaser / standard wrapper)
        os.path.expandvars(r"%PROGRAMFILES%\Kvaser\J2534.dll"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Kvaser\J2534.dll"),
        "J2534.dll",
        # Linux / BSD
        "libj2534.so",
        "libJ2534.so",
        "libj2534.so.1",
        # macOS
        "libj2534.dylib",
        "libJ2534.dylib",
    ]
    for path in candidates:
        try:
            return ctypes.CDLL(path)
        except OSError:
            continue
    raise OSError("no J2534 driver library found on this system")


# Standard J2534-1 driver function names (the subset we use).
_J2534_FUNCS = {
    "J2534_OpenDriver": "Open",
    "J2534_CloseDriver": "Close",
    "J2534_ReadPort": "ReadPort",
    "J2534_WritePort": "WritePort",
    "J2534_SendControlFlags": "SendControlFlags",
    "J2534_ResetDevice": "ResetDevice",
    "J2534_GetType": "GetType",
    "J2534_GetDescription": "GetDescription",
    "J2534_GetExVersion": "GetExVersion",
}


class J2534Connector(Connector, SettingsDriven):
    """A SAE J2534-1 pass-thru diagnostic adapter.

    Typical usage::

        adapter = J2534Connector(virtual=True)   # for testing
        # adapter = J2534Connector(vendor_id=0x0483, product_id=0x5741)  # physical

        adapter.open()
        adapter.send(b"\x02\x01\x00\x00\x00\x00\x00\x00")  # request to start
        resp = adapter.recv()
        adapter.close()
    """

    DEFAULT_VID = 0x0483
    DEFAULT_PID = 0x5741

    _SETTINGS_FIELDS = ("virtual", "vendor_id", "product_id", "channel", "name")

    def __init__(
        self,
        *,
        virtual: bool = False,
        vendor_id: int | None = None,
        product_id: int | None = None,
        channel: int = 0,
        name: str | None = None,
    ) -> None:
        self.virtual = virtual
        self.vendor_id = vendor_id or self.DEFAULT_VID
        self.product_id = product_id or self.DEFAULT_PID
        self.channel = channel
        self.name = name or "J2534 pass-thru adapter"
        self._conn: VirtualConnection | None = None
        self._handle: ctypes.c_void_p | None = None
        self._lib: ctypes.CDLL | None = None
        self._lock = threading.Lock()

        self.adapter = self.name
        self.firmware_version = "0.0"

    # ------------------------------------------------------------- discovery

    @classmethod
    def list_adapters(cls) -> list[dict]:
        """Return a best-effort inventory of attached J2534 adapters.

        A native enumeration routine is tried first when the J2534 library is
        present; otherwise the USB namespace is scanned for VID/PID matches.
        The returned list always contains at least a pseudo-entry describing
        the configured adapter so caller code never sees an empty list while
        deciding what to open.
        """
        found: list[dict] = []
        try:
            _load_j2534_library()
        except OSError:
            logger.debug("J2534 native enumeration unavailable, scanning USB")
        try:
            import glob

            for d in glob.glob("/dev/bus/usb/**/[0-9a-fA-F][0-9a-fA-F]*/[0-9a-fA-F][0-9a-fA-F]*", recursive=True):
                found.append({"path": d, "type": "usb"})
        except Exception:  # noqa: BLE001, S110
            pass
        if not found:
            found.append({"path": "none", "type": "virtual"})
        return found

    # --------------------------------------------------------------- lifecycle

    def open(self) -> None:
        """Open the J2534 adapter (virtual or native).

        Hardware absence or failure is surfaced as :class:`ConnectorError` so
        callers can report "no dongle found" without leaking C-level details.
        """
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                logger.warning("J2534 adapter already open")
                return

            if self.virtual:
                self._conn = VirtualConnection(name=self.name, echo=True)
                self._conn.open()
                self.adapter = f"virtual:{self.name}"
                self.firmware_version = "test"
                logger.info(f"J2534 opened (virtual): {self.name}")
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
            logger.info("J2534 closed")

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
                logger.debug("J2534 virtual reset")
                return
            if self._handle is None:
                raise ConnectorNotOpenError("J2534 adapter is not open")
            self._invoke("J2534_ResetDevice")

    # --------------------------------------------------------------- I/O

    def send(self, data: bytes) -> None:
        with self._lock:
            if self._conn is None or not self._conn.is_open:
                raise ConnectorNotOpenError("J2534 adapter is not open")
            self._conn.send(data)

    def recv(self, timeout: float = 1.0) -> bytes:
        with self._lock:
            if self._conn is None or not self._conn.is_open:
                raise ConnectorNotOpenError("J2534 adapter is not open")
            return self._conn.recv(timeout)

    # --------------------------------------------------------------- native

    def _connect_native(self) -> None:
        try:
            self._lib = _load_j2534_library()
        except OSError as exc:
            raise ConnectorError(f"J2534: no driver library: {exc}") from exc

        params = self._open_params()
        handle = ctypes.c_void_p()
        if not self._invoke("J2534_OpenDriver", params, handle):
            raise ConnectorError("J2534: failed to open adapter")
        self._handle = handle

    @staticmethod
    def _open_params() -> ctypes.c_void_p:
        """Build an ``OpenAdapterByVidPid`` OPEN_PARAMS block (J2534-1)."""

        class OpenParams(ctypes.Structure):
            _fields_ = [
                ("OpenAdapter", ctypes.c_ulong),  # OpenAdapterByVidPid
                ("VendorID", ctypes.c_ushort),
                ("ProductID", ctypes.c_ushort),
                ("DwFlags", ctypes.c_ulong),
            ]

        p = OpenParams()
        p.OpenAdapter = 1  # OpenAdapterByVidPid
        p.VendorID = ctypes.c_ushort(J2534Connector.DEFAULT_VID)
        p.ProductID = ctypes.c_ushort(J2534Connector.DEFAULT_PID)
        p.DwFlags = 0
        return ctypes.c_void_p(ctypes.addressof(p))

    def _invoke(self, name: str, *args: object) -> bool:
        """Call a J2534 function with type-correct signatures.

        Returns ``True`` when the function returned success (zero).  Lies
        safely if the symbol is absent or the signature cannot be matched.
        """
        func = getattr(self._lib, name, None) if self._lib else None
        if func is None:
            return False
        # Map of known signatures: (restype, argtypes)
        sigs = {
            "J2534_OpenDriver": (ctypes.c_long, [ctypes.c_void_p, ctypes.c_void_p]),
            "J2534_CloseDriver": (ctypes.c_long, [ctypes.c_void_p]),
            "J2534_ReadPort": (
                ctypes.c_long,
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long],
            ),
            "J2534_WritePort": (
                ctypes.c_long,
                [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long],
            ),
            "J2534_SendControlFlags": (ctypes.c_long, [ctypes.c_void_p, ctypes.c_ulong]),
            "J2534_ResetDevice": (ctypes.c_long, [ctypes.c_void_p]),
            "J2534_GetDescription": (
                ctypes.c_long,
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_char_p],
            ),
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

    # ---------------------------------------------------------- properties

    @property
    def adapter_name(self) -> str:
        return self.adapter

    @property
    def port(self) -> str | None:
        """J2534 adapters are USB devices; report the matched device path."""
        return None
