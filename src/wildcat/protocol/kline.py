"""K-line (ISO 9141-2 / ISO 14230 KWP2000) init + session over a raw serial link.

This is the transport glue for the BMW K+DCAN and VAG-COM (Ross-Tech)
cables: a raw FTDI serial port plus a K-line initialisation sequence and a
minimal KWP2000 diagnostic session on top.

The initialisation sequences follow ISO 14230-2:

* **Fast init** -- a 25 ms break (low) followed by 0xC1 at the normal
  baud rate; the ECU replies with 0x55 (sync) and two key bytes.
* **Slow (5-baud) init** -- the tester sends 0x33 at 5 baud; the ECU
  replies with 0x55 (sync), 0x08, 0x08 and their inverses.

Without a real ECU on the line (virtual/echo mode) the init fails and the
session reports ``established == False``; reads then return empty lists
(honest -- no fabricated data).
"""
from __future__ import annotations

import time

from loguru import logger

from wildcat.cars.base import DTC, LiveData
from wildcat.connectors.base import Connector, ConnectorError

TESTER_ADDR = 0xF1
ECU_ADDR = 0x10
KLINE_BAUD = 10400


def _read_bytes(connector: Connector, n: int, timeout: float) -> bytes:
    buf = bytearray()
    deadline = time.monotonic() + timeout
    while len(buf) < n and time.monotonic() < deadline:
        try:
            chunk = connector.recv(timeout=0.1)
        except Exception:  # noqa: BLE001
            chunk = b""
        if chunk:
            buf += chunk
        else:
            time.sleep(0.02)
    return bytes(buf)


def fast_init(connector: Connector, timeout: float = 2.0) -> bool:
    """Attempt a K-line fast init.  Returns True on success."""
    try:
        # break: toggle RTS low for ~25 ms
        try:
            if hasattr(connector, "_ser") and connector._ser is not None:
                connector._ser.setRTS(True)
                time.sleep(0.025)
                connector._ser.setRTS(False)
        except Exception:  # noqa: BLE001, S110
            pass
        connector.send(bytes([0xC1]))
        logger.debug("K-line fast init: sent break + 0xC1")
        resp = _read_bytes(connector, 3, timeout)
        logger.debug(f"K-line fast init: response = {resp.hex()}")
    except (OSError, ConnectorError):
        logger.debug("K-line fast init: exception")
        return False
    # ECU replies with sync 0x55 + 2 key bytes
    ok = len(resp) >= 1 and resp[0] == 0x55
    logger.debug(f"K-line fast init: {'OK' if ok else 'FAIL'} (sync={resp[0:1].hex()})")
    return ok


def slow_init(connector: Connector, timeout: float = 2.0) -> bool:
    """Attempt a 5-baud (slow) K-line init.  Returns True on success."""
    try:
        # 5-baud: send 0x33 one bit at a time (~200 ms per bit)
        byte = 0x33
        for bit in range(8):
            val = (byte >> bit) & 1
            try:
                if hasattr(connector, "_ser") and connector._ser is not None:
                    connector._ser.setRTS(not bool(val))
            except Exception:  # noqa: BLE001, S110
                pass
            time.sleep(0.2)
        try:
            if hasattr(connector, "_ser") and connector._ser is not None:
                connector._ser.setRTS(False)
        except Exception:  # noqa: BLE001, S110
            pass
        logger.debug("K-line slow init: sent 0x33 @ 5 baud")
        resp = _read_bytes(connector, 4, timeout)
        logger.debug(f"K-line slow init: response = {resp.hex()}")
    except (OSError, ConnectorError):
        logger.debug("K-line slow init: exception")
        return False
    # ECU replies with 0x55 0x08 0x08 0xF7
    ok = len(resp) >= 1 and resp[0] == 0x55
    logger.debug(f"K-line slow init: {'OK' if ok else 'FAIL'}")
    return ok


class KLineSession:
    """Minimal KWP2000 diagnostic session over a K-line serial link.

    In virtual (echo) mode the init fails and ``established`` is False;
    reads then return empty lists (no fabricated data).
    """

    def __init__(self, connector: Connector, fast: bool = True) -> None:
        self.connector = connector
        self.established = False
        self._init(fast)

    def _init(self, fast: bool) -> None:
        if not self.connector.is_open():
            try:
                self.connector.open()
            except ConnectorError:
                self.established = False
                return
        ok = fast_init(self.connector) if fast else slow_init(self.connector)
        self.established = ok

    def read_dtcs(self) -> list[DTC]:
        if not self.established:
            return []
        # KWP2000 service 0x18 (readDTCByStatusMask) -- best-effort.
        # Real parsing requires a validated K-line frame exchange; in
        # virtual/echo mode there is no ECU to answer, so return empty.
        try:
            self.connector.send(bytes([0x18, 0x00, 0xFF]))
            logger.debug("K-line: sent readDTC 0x18 0x00 0xFF")
            resp = _read_bytes(self.connector, 64, 1.0)
            logger.debug(f"K-line: readDTC response = {resp.hex()}")
        except (OSError, ConnectorError):
            logger.debug("K-line: readDTC exception")
            return []
        if not resp or resp[0] != 0x58:  # 0x18 + 0x40
            return []
        # payload after service byte: pairs of DTC bytes (best-effort)
        out: list[DTC] = []
        i = 2
        while i + 1 < len(resp):
            hi, lo = resp[i], resp[i + 1]
            if hi == 0 and lo == 0:
                break
            code = f"P{hi:02X}{lo:02X}"
            out.append(DTC(code=code, description="", severity="Warning"))
            i += 2
        return out

    def read_live_data(self) -> list[LiveData]:
        # KWP2000 live data is make/model specific (readDataByIdentifier);
        # no generic mapping without a diagnostic database.  Honest: empty.
        return []

    def clear_dtcs(self) -> None:
        if not self.established:
            return
        try:
            self.connector.send(bytes([0x14]))
            _read_bytes(self.connector, 4, 1.0)
        except (OSError, ConnectorError):
            pass
