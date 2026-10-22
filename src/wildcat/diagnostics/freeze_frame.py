"""Freeze frame capture."""

from __future__ import annotations

from dataclasses import dataclass, field

from wildcat.cars.base import DTC, CarModel, LiveData


@dataclass
class FreezeFrame:
    dtc: DTC | None = None
    data: list[LiveData] = field(default_factory=list)


class FreezeFrameReader:
    def __init__(self, car: CarModel):
        self.car = car

    def read(self) -> FreezeFrame:
        dtcs = list(self.car.get_dtc_reader())
        dtc = dtcs[0] if dtcs else None
        data = list(self.car.get_live_data())
        return FreezeFrame(dtc=dtc, data=data)


def freeze_frame(car: CarModel) -> FreezeFrame:
    return FreezeFrameReader(car).read()
