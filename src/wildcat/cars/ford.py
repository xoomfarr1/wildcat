"""Ford car model (Focus ST170 / Mondeo ST220).

This model follows the same conventions as the Mercedes C300 and BMW models:
class-level dicts are CAN identifier spaces, live data is decoded with
:func:`wildcat.cars.spaces.decode_signal`, and stored fault codes are kept
in-memory.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from wildcat.cars.base import DTC, CarModel, LiveData
from wildcat.cars.spaces import decode_signal


class Ford(CarModel):
    """Ford Focus ST170 / Mondeo ST220 car model."""

    SUPPORTED_CONNECTORS: ClassVar[tuple[str, ...]] = ("J2534", "USB-CAN", "ELM327")

    # CAN identifier spaces (Ford OBD-II PID map).
    DTC_SPACES: ClassVar[dict[str, list[dict[str, object]]]] = {
        "ENGINE": [
            {"code": "P0301", "description": "Cylinder 1 misfire detected", "severity": "Critical", "is_temporary": False},
            {"code": "P0171", "description": "System too lean (bank 1)", "severity": "Warning", "is_temporary": False},
            {"code": "P0128", "description": "Coolant thermostat below regulating temperature", "severity": "Warning", "is_temporary": False},
            {"code": "P0420", "description": "Catalyst efficiency below threshold (bank 1)", "severity": "Warning", "is_temporary": False},
            {"code": "P0455", "description": "Evaporative leak detected (large leak)", "severity": "Warning", "is_temporary": False},
            {"code": "P0135", "description": "O2 sensor heater circuit malfunction (bank 1, sensor 1)", "severity": "Warning", "is_temporary": True},
        ],
        "COOLING": [
            {"code": "P0115", "description": "Engine coolant temperature circuit", "severity": "Warning", "is_temporary": True},
            {"code": "P0591", "description": "Engine coolant temperature sensor performance", "severity": "Warning", "is_temporary": True},
        ],
        "CHASSIS": [
            {"code": "P0500", "description": "Vehicle speed sensor (default)", "severity": "Warning", "is_temporary": False},
        ],
    }

    LIVE_DATA_SPACES: ClassVar[dict[str, list[dict[str, object]]]] = {
        "ENGINE": [
            {"name": "EngineRPM", "address": 0x100, "length": 2, "sample": 6000, "scale": 0.125, "offset": 0.0, "unit": "rpm"},
            {"name": "IntakeManifoldPressure", "address": 0x101, "length": 2, "sample": 6000, "scale": 0.01, "offset": 0.0, "unit": "kPa"},
            {"name": "CoolantTemp", "address": 0x102, "length": 1, "sample": 92, "scale": 1.0, "offset": 0.0, "unit": "°C"},
            {"name": "ThrottlePosition", "address": 0x103, "length": 1, "sample": 100, "scale": 0.1, "offset": 0.0, "unit": "%"},
        ],
        "TRANSMISSION": [
            {"name": "Gear", "address": 0x104, "length": 4, "sample": 3, "scale": 1.0, "offset": 0.0, "unit": "gear"},
            {"name": "OutputSpeed", "address": 0x105, "length": 2, "sample": 1800, "scale": 0.1, "offset": 0.0, "unit": "rpm"},
        ],
        "COOLING": [
            {"name": "IntakeAirTemp", "address": 0x106, "length": 1, "sample": 21.5, "scale": 1.0, "offset": 0.0, "unit": "°C"},
            {"name": "RadiatorFan", "address": 0x107, "length": 1, "sample": 1, "scale": 1.0, "offset": 0.0, "unit": "state"},
        ],
        "CHASSIS": [
            {"name": "VehicleSpeed", "address": 0x108, "length": 1, "sample": 65, "scale": 1.0, "offset": 0.0, "unit": "km/h"},
            {"name": "AuxBatteryVoltage", "address": 0x109, "length": 2, "sample": 132, "scale": 0.1, "offset": 0.0, "unit": "V"},
        ],
    }

    _POWERTRAIN_ECU_ID = 0x22

    def __init__(self) -> None:
        super().__init__()
        self._language = "EN"
        self._ecu_id = self._POWERTRAIN_ECU_ID
        self._stored_dtc: list[DTC] = []
        for _space in self.DTC_SPACES.values():
            for _dtc in _space:
                self._stored_dtc.append(
                    DTC(
                        code=_dtc["code"],
                        description=_dtc["description"],
                        severity=_dtc["severity"],
                        is_temporary=_dtc.get("is_temporary", False),
                    )
                )

    @property
    def name(self) -> str:
        return "Ford Focus ST170 / Mondeo ST220"

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        """Configure the vehicle language (applied at session level)."""
        self._language = str(language).upper()

    def get_dtc_reader(self) -> list[DTC]:
        """Read all currently stored fault codes."""
        return list(self._stored_dtc)

    def get_live_data(self, keys: Iterable[str] | None = None) -> list[LiveData]:
        """Read live data from the vehicle.

        Decodes every configured signal with :func:`spaces.decode_signal` and
        returns a ``LiveData`` record per signal. ``keys`` optionally
        restricts the result to the given signal names.

        Args:
            keys: Optional list of signal names to include.

        Returns:
            Decoded live data records.
        """
        out: list[LiveData] = []
        for space_name, signals in self.LIVE_DATA_SPACES.items():
            if keys and space_name not in keys:
                continue
            for sig in signals:
                raw = sig.get("sample", 0)
                value = round(decode_signal(sig, raw), 2)
                out.append(LiveData(name=sig["name"], value=value, unit=sig.get("unit", "")))
        return out

    def clear_dtc(self) -> None:
        """Clear all currently stored fault codes."""
        self._stored_dtc = []

    def ecu_id(self) -> int:
        """Target ECU identifier (Ford UDS target ECU)."""
        return self._ecu_id

    def security_access(self) -> bool:
        """Standard OBD-II Ford ECUs do not require security access."""
        return False

    def send_seed(self, seed: bytes) -> bytes:
        """Ask the vehicle for a security seed.

        Ford ECUs in OBD-II mode do not require security access, so this
        method is not applicable and raises :class:`NotImplementedError`.

        Args:
            seed: Unused (kept for API compatibility).

        Raises:
            NotImplementedError: Always; see :meth:`security_access`.
        """
        raise NotImplementedError("Ford does not require security access")

    def send_key(self, key: bytes) -> bytes:
        """Send a seed response to the vehicle.

        Ford ECUs in OBD-II mode do not require security access, so this
        method is not applicable and raises :class:`NotImplementedError`.

        Args:
            key: Unused (kept for API compatibility).

        Raises:
            NotImplementedError: Always; see :meth:`security_access`.
        """
        raise NotImplementedError("Ford does not require security access")
