"""Supplier info."""

from __future__ import annotations

from dataclasses import dataclass

from wildcat.cars.base import CarModel


@dataclass
class SupplierInfo:
    name: str
    ecu_id: int


class SupplierInfoReader:
    def __init__(self, car: CarModel):
        self.car = car

    def read(self) -> SupplierInfo:
        return SupplierInfo(name=self.car.name, ecu_id=self.car.ecu_id())


def supplier_info(car: CarModel) -> SupplierInfo:
    return SupplierInfoReader(car).read()
