"""Actuator control."""

from __future__ import annotations

from wildcat.cars.base import CarModel


class ActuatorControl:
    def __init__(self, car: CarModel):
        self.car = car

    def actuate(self, name: str, state: bool = True) -> bool:
        # Minimal stub: no hardware actuation; report success.
        return True


def actuator_control(car: CarModel, name: str, state: bool = True) -> bool:
    return ActuatorControl(car).actuate(name, state)
