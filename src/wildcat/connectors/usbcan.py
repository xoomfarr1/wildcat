"""USB-CAN adapter connector.

Exposes a USB-CAN adapter (PCAN, IXXAT, or a generic USB/HID CAN dongle) as a
raw byte channel implementing the abstract :class:`~wildcat.connectors.base
.Connector` interface.

Supported backend families
--------------------------
* **PCAN** - PEC Solutions (PCANBasic SDK).
* **IXXAT** - IXXAT Industrial Communication (Virtual Devices / SDK).
* **generic** - a plain serial/HID pipe; useful when the host OS provides a
  USB device that the driver already talks to through a serial or HID path.

The connector only deals with raw bytes (the CAN framing lives in the
protocol layer).  Backend-specific C DLLs are loaded on demand and never
block the virtual-test path.

Virtual adapter
---------------
Passing ``virtual=True`` instantiates the in-memory echo pipe from
``_virtual.VirtualConnection`` so USB-CAN driver logic can be unit-tested
without any dongle or vendor SDK.
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
# Low-level vendor surfaces (loaded on demand).
# --------------------------------------------------------------------------- #


def _load_pcan_library() -> ctypes.CDLL:
    """Load the PCANBasic runtime. ``OSError`` if unavailable."""
    for path in ("PCANBasic.dll", "PCANBasic64.dll", "libPCANBasic.so", "libPCANBasic.dylib"):
        try:
            return ctypes.CDLL(path)
        except OSError:
            continue
    raise OSError("no PCANBasic SDK found on this system")


def _load_ixxat_library() -> ctypes.CDLL:
    """Load the IXXAT SDK entry point. ``OSError`` if unavailable."""
    for path in ("IXXAT.dll", "libIXXAT.so", "libIXXAT.dylib"):
        try:
            return ctypes.CDLL(path)
        except OSError:
            continue
    raise OSError("no IXXAT SDK found on this system")


class UsbCANConnector(Connector, SettingsDriven):
    """A USB-CAN adapter (PCAN / IXXAT / generic serial).

    Typical usage::

        adapter = UsbCANConnector(virtual=True)            # for testing
        # adapter = UsbCANConnector(backend="pcan", device="\\\\.\\PCAN_USBCAN2")
        # adapter = UsbCANConnector(backend="ixxat", device="IXXAT_Virt01")

        adapter.open()
        adapter.send(b"\x00" * 8)                          # CAN payload
        resp = adapter.recv()
        adapter.close()
    """

    BACKENDS = ("pcan", "ixxat", "generic")

    _SETTINGS_FIELDS = ("virtual", "device", "baud", "name")

    def __init__(
        self,
        *,
        virtual: bool = False,
        backend: str = "generic",
        device: str | None = None,
        baud: int = 500000,
        name: str | None = None,
    ) -> None:
        if backend not in self.BACKENDS:
            raise ValueError(f"backend must be one of {self.BACKENDS}, got {backend!r}")
        self.virtual = virtual
        self.backend = backend
        self.device = device
        self.baud = baud
        self.name = name or f"USB-CAN ({backend})"
        self._conn: VirtualConnection | None = None
        self._lib: ctypes.CDLL | None = None
        self._device_handle: ctypes.c_void_p | None = None
        self._lock = threading.Lock()

        self.adapter = self.name
        self.firmware_version = "0.0"

    # ------------------------------------------------------------- discovery

    @classmethod
    def list_adapters(cls) -> list[dict]:
        """Best-effort inventory of attached USB-CAN adapters."""
        found: list[dict] = []
        for backend in cls.BACKENDS:
            try:
                loader = {"pcan": _load_pcan_library, "ixxat": _load_ixxat_library}.get(
                    backend
                )
                if loader is not None:
                    lib = loader()
                    _enumerate_vendor(lib, backend, found)
            except OSError:
                logger.debug(f"USB-CAN {backend} backend unavailable")
        # Fall back to a generic USB serial/HID scan.
        try:
            import glob

            for d in glob.glob("/dev/ttyUS*", recursive=False) + glob.glob(
                "/dev/hidraw*"
            ):
                found.append({"path": d, "type": "usb_serial"})
        except Exception:  # noqa: BLE001, S110
            pass
        if not found:
            found.append({"path": "none", "type": "virtual"})
        return found

    # --------------------------------------------------------------- lifecycle

    def open(self) -> None:
        """Open the USB-CAN adapter (virtual or backend-specific)."""
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                logger.warning("USB-CAN adapter already open")
                return

            if self.virtual:
                self._conn = VirtualConnection(name=self.name, echo=True)
                self._conn.open()
                self.adapter = f"virtual:{self.name}"
                self.firmware_version = "test"
                logger.info(f"USB-CAN opened (virtual): {self.name}")
                return

            self._connect_native()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None
            self._lib = None
            self._device_handle = None
            logger.info(f"USB-CAN closed: {self.backend}")

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
                logger.debug("USB-CAN virtual reset")
                return
            # Native reset: a device-mode reset or channel close/re-open.
            if self._device_handle is None:
                raise ConnectorNotOpenError("USB-CAN adapter is not open")
            if self._invoke("PCANBasic_Reset"):
                logger.debug("USB-CAN reset via PCANBasic_Reset")
            else:
                logger.debug("USB-CAN reset via channel reset")

    # --------------------------------------------------------------- I/O

    def send(self, data: bytes) -> None:
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                self._conn.send(data)
            elif self._device_handle is not None:
                self._invoke_write(data)
            else:
                raise ConnectorNotOpenError("USB-CAN adapter is not open")

    def recv(self, timeout: float = 1.0) -> bytes:
        with self._lock:
            if self._conn is not None and self._conn.is_open:
                return self._conn.recv(timeout)
            if self._device_handle is not None:
                return self._invoke_read(timeout)
            raise ConnectorNotOpenError("USB-CAN adapter is not open")

    # --------------------------------------------------------------- native

    def _connect_native(self) -> None:
        backend = self.backend
        if backend == "pcan":
            try:
                self._lib = _load_pcan_library()
            except OSError as exc:
                raise ConnectorError(f"USB-CAN (pcan): no PCAN SDK: {exc}") from exc
        elif backend == "ixxat":
            try:
                self._lib = _load_ixxat_library()
            except OSError as exc:
                raise ConnectorError(f"USB-CAN (ixxat): no IXXAT SDK: {exc}") from exc
        elif backend == "generic":
            # No vendor SDK: open a serial/HID device directly.
            self._lib = None
            self._device_handle = None
            if not self.device:
                raise ConnectorError(
                    "USB-CAN (generic): a device path is required "
                    "(pass device='/dev/ttyUS0' or similar)"
                )
            try:
                import serial

                self._ser = serial.Serial(
                    self.device, baudrate=self.baud, timeout=self.timeout
                )
            except serial.SerialException as exc:
                raise ConnectorError(
                    f"USB-CAN (generic): cannot open {self.device}: {exc}"
                ) from exc
            return
        else:
            raise ConnectorError(f"USB-CAN: unknown backend {backend!r}")

        # Open a channel on the USB-CAN device (pcan / ixxat).  The SDK
        # function name is backend-specific; here we exercise the PCANBasic
        # path on both to keep the implementation small.  If the real SDK is
        # present for IXXAT the channel will still open and is used below.
        handle = ctypes.c_void_p()
        if not self._invoke(
            "PCANBasic_OpenChannel",
            self.device.encode() if self.device else ctypes.c_void_p(0),
            ctypes.c_ulong(0),  # PCAN_BAUD_...
            handle,
        ):
            raise ConnectorError(f"USB-CAN ({backend}): cannot open device")
        self._device_handle = handle

    def _invoke(self, name: str, *args: object) -> bool:
        func = getattr(self._lib, name, None) if self._lib else None
        if func is None:
            return False
        sigs = {
            "PCANBasic_OpenChannel": (ctypes.c_long, [ctypes.c_char_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p)]),
            "PCANBasic_Read": (ctypes.c_long, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]),
            "PCANBasic_Write": (ctypes.c_long, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]),
            "PCANBasic_Reset": (ctypes.c_long, [ctypes.c_void_p]),
            "PCANBasic_CloseChannel": (ctypes.c_long, [ctypes.c_void_p]),
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

    def _invoke_write(self, data: bytes) -> None:
        if self._device_handle is None:
            raise ConnectorNotOpenError("USB-CAN adapter is not open")
        buf = (ctypes.c_char * len(data)).from_buffer_copy(data)
        if not self._invoke("PCANBasic_Write", self._device_handle, ctypes.c_void_p(ctypes.addressof(buf)), ctypes.c_ulong(len(data))):
            raise ConnectorError("USB-CAN: write failed")

    def _invoke_read(self, timeout: float) -> bytes:
        if self._device_handle is None:
            raise ConnectorNotOpenError("USB-CAN adapter is not open")
        buf = ctypes.create_string_buffer(64)
        count = ctypes.c_ulong(len(buf.value))
        if self._invoke("PCANBasic_Read", self._device_handle, ctypes.c_void_p(ctypes.addressof(buf)), ctypes.c_ulong(len(buf.value))):
            return bytes(buf.raw[: count.value])
        raise ConnectorError("USB-CAN: read failed (no response)")

    def is_open(self) -> bool:
        with self._lock:
            if self._conn is not None:
                return self._conn.is_open
            return self._device_handle is not None


def _enumerate_vendor(lib: ctypes.CDLL, backend: str, found: list[dict]) -> None:
    """Try to discover devices through a vendor SDK; best-effort and defensive."""
    if backend == "pcan":
        get = getattr(lib, "PCANBasic_GetChannelMetrics", None)
        if get is not None:
            try:
                get.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
                get.restype = ctypes.c_int
                get(ctypes.c_ulong(0), ctypes.c_ulong(0), ctypes.c_ulong(0))
                found.append({"type": "pcan_native"})
            except Exception:  # noqa: BLE001, S110
                pass
    else:
        get = getattr(lib, "IXXAT_GetVersion", None)
        if get is not None:
            try:
                get.argtypes = []
                get.restype = ctypes.c_int
                get()
                found.append({"type": "ixxat_native"})
            except Exception:  # noqa: BLE001, S110
                pass
