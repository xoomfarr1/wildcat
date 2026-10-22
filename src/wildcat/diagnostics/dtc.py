"""DTC reader: read and clear fault codes."""

from __future__ import annotations

from wildcat.cars.base import DTC, CarModel


class DTCReader:
    def __init__(self, car: CarModel):
        self.car = car

    def read(self) -> list[DTC]:
        return list(self.car.get_dtc_reader())

    def clear(self) -> None:
        self.car.clear_dtc()

    # aliases
    def read_dtc(self) -> list[DTC]:
        return self.read()

    def clear_dtc(self) -> None:
        self.clear()


def read_dtc(car: CarModel) -> list[DTC]:
    return list(car.get_dtc_reader())


def clear_dtc(car: CarModel) -> None:
    car.clear_dtc()
