"""Diagnostics feature layer."""

from __future__ import annotations

from wildcat.cars.base import CarModel
from wildcat.diagnostics.actuator import ActuatorControl, actuator_control
from wildcat.diagnostics.dtc import DTCReader, clear_dtc, read_dtc
from wildcat.diagnostics.freeze_frame import (
    FreezeFrame,
    FreezeFrameReader,
    freeze_frame,
)
from wildcat.diagnostics.live_data import LiveDataView, live_data
from wildcat.diagnostics.supplier import SupplierInfo, SupplierInfoReader, supplier_info


class Diagnostics:
    def __init__(self, car: CarModel):
        self.car = car
        self.dtc = DTCReader(car)
        self.live_data = LiveDataView(car)
        self.freeze_frame = FreezeFrameReader(car)
        self.supplier = SupplierInfoReader(car)
        self.actuator = ActuatorControl(car)

    def read_dtc(self):
        return self.dtc.read()

    def clear_dtc(self):
        return self.dtc.clear()

    def read_live_data(self, keys=None):
        return self.live_data.read(keys)

    def read_freeze_frame(self):
        return self.freeze_frame.read()

    def read_supplier_info(self):
        return self.supplier.read()

    def actuate(self, name, state=True):
        return self.actuator.actuate(name, state)


__all__ = [
    "ActuatorControl",
    "DTCReader",
    "Diagnostics",
    "FreezeFrame",
    "FreezeFrameReader",
    "LiveDataView",
    "SupplierInfo",
    "SupplierInfoReader",
    "actuator_control",
    "clear_dtc",
    "freeze_frame",
    "live_data",
    "read_dtc",
    "supplier_info",
]
