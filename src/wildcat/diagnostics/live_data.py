"""Live data view."""

from __future__ import annotations

from wildcat.cars.base import CarModel, LiveData


class LiveDataView:
    def __init__(self, car: CarModel):
        self.car = car

    def read(self, keys=None):
        return self.car.get_live_data(keys)

    def view(self, keys=None):
        return self.read(keys)


def live_data(car: CarModel, keys=None) -> list[LiveData]:
    return list(car.get_live_data(keys))
