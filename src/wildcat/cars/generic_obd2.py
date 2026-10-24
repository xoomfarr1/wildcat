"""Generic read-only OBD-II car model.

This is the fallback model for vehicle makes that Wildcat recognises (so they
appear in the year/make/model selector and can be VIN-decoded) but for which no
protocol-specific car model has been implemented yet.

It is intentionally a *stub*:

* ``get_dtc_reader`` / ``get_live_data`` return empty lists (there is no
  vehicle-specific data table behind them yet).
* ``security_access`` is ``False`` and ``send_seed`` / ``send_key`` are not used
  by the programming path, so no real exchange is attempted — the user is told
  the make is recognised but not yet modelled instead of silently faking data.

A make is mapped to :class:`GenericOBD2` in :mod:`wildcat.cars.vehicles` when
Wildcat has no dedicated model for it (i.e. everything that is not
Mercedes-Benz, BMW, Ford, Volkswagen or Audi).
"""
from __future__ import annotations

from wildcat.cars.base import CarModel


class GenericOBD2(CarModel):
    """Recognised but not protocol-modelled make (read-only stub)."""

    SUPPORTED_CONNECTORS: tuple[str, ...] = ("J2534", "PT3G", "ELM327", "USB-CAN")

    @property
    def name(self) -> str:
        return "Generic OBD-II"

    @property
    def language(self) -> str:
        return "EN"

    def set_language(self, language: str) -> None:
        self._language = str(language).upper()

    def get_dtc_reader(self):
        return []

    def get_live_data(self, keys=None):
        return []

    def clear_dtc(self) -> None:
        return None

    def security_access(self) -> bool:
        return False

    def ecu_id(self) -> int:
        return 0xF1

    def send_seed(self, seed: bytes) -> bytes:
        if len(seed) != 4:
            raise ValueError("seed request must be exactly 4 bytes")
        return bytes(4)

    def send_key(self, key: bytes) -> bytes:
        if len(key) != 4:
            raise ValueError("seed response must be exactly 4 bytes")
        return bytes(4)
