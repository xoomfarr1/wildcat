"""ECU identification helpers for programming."""

from __future__ import annotations

from wildcat.core.ecu import ECUIdentifier, VehicleIdentification


class ECUIdentification:
    def __init__(self, *args, vehicle=None, connector=None, car=None,
                 registry=None, **kwargs) -> None:
        if vehicle is None and len(args) == 1 and isinstance(args[0], VehicleIdentification):
            vehicle = args[0]
            args = args[1:]
        # Allow ECUIdentification(connector, car) style construction.
        if vehicle is None and len(args) >= 1 and hasattr(args[0], "is_open"):
            connector = args[0]
            args = args[1:]
        if len(args) >= 1 and hasattr(args[0], "ecu_id"):
            car = args[0]
            args = args[1:]

        if vehicle is None:
            vehicle = VehicleIdentification(registry=registry)
        self.vehicle = vehicle
        self.connector = connector
        self.car = car

    def identify(self, connector=None, car=None) -> ECUIdentifier:
        connector = connector if connector is not None else self.connector
        car = car if car is not None else self.car
        return self.vehicle.identify(connector, car)
