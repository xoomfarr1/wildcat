"""Flash/calibration update helpers for programming.

NOTE: This module is a *scaffold*.  It does NOT implement a real ECU
flashing sequence (no RequestDownload/TransferData/RequestTransferExit,
chunking, checksum or verification).  :meth:`FlashUpdater.flash` only
forwards a payload to a target; it returns ``False`` (and raises nothing)
when there is no target, so callers can detect the missing wiring.
"""
from __future__ import annotations

from wildcat.core.uds import UDSService


class FlashUpdater:
    def __init__(self, uds=None, connector=None, **kwargs) -> None:
        if uds is None and connector is not None:
            uds = UDSService(connector)
        self.uds = uds

    def flash(self, data: bytes, uds=None) -> bool:
        target = uds if uds is not None else self.uds
        if target is None:
            return False
        target.send(data)
        return True

    def calibrate(self, data: bytes, uds=None) -> bool:
        target = uds if uds is not None else self.uds
        if target is None:
            return False
        target.send(data)
        return True
