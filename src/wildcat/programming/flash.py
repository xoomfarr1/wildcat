"""Flash/calibration update helpers for programming."""

from __future__ import annotations

from wildcat.core.uds import UDSService


class FlashUpdater:
    def __init__(self, uds=None, connector=None, **kwargs) -> None:
        if uds is None and connector is not None:
            uds = UDSService(connector)
        self.uds = uds

    def flash(self, data: bytes, uds=None) -> bool:
        target = uds if uds is not None else self.uds
        if target is not None:
            target.send(data)
        return True

    def calibrate(self, data: bytes, uds=None) -> bool:
        target = uds if uds is not None else self.uds
        if target is not None:
            target.send(data)
        return True
