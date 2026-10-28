"""BMW car model (E90 / F30 3 Series platform).

This model follows the same conventions as the Mercedes C300 model: each
class-level dict is a CAN identifier space (``<space name> ->
[<definitions>]``), live data is decoded with
:func:`wildcat.cars.spaces.decode_signal`, and the stored fault codes are
maintained in-memory (consulted by the PT3G/J2534 driver in a real
session).
"""

from __future__ import annotations

from typing import ClassVar

from wildcat.cars.base import DTC, CarModel, LiveData


class BMW(CarModel):
    """BMW 3 Series (E90/F30) car model."""

    SUPPORTED_CONNECTORS: ClassVar[tuple[str, ...]] = ("PT3G", "USB-CAN")

    # CAN identifier spaces (BMW OBD-II / KWP2000 message IDs).
    DTC_SPACES: ClassVar[dict[str, list[dict[str, object]]]] = {
        "ENGINE": [
            {"code": "P0301", "description": "Cylinder 1 misfire detected", "severity": "Critical", "is_temporary": False},
            {"code": "P0302", "description": "Cylinder 2 misfire detected", "severity": "Critical", "is_temporary": False},
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

    _POWERTRAIN_ECU_ID = 0x10

    def __init__(self) -> None:
        super().__init__()
        self._language = "EN"
        self._ecu_id = self._POWERTRAIN_ECU_ID
        self._stored_dtc: list[DTC] = []

    @property
    def name(self) -> str:
        return "BMW 3 Series (E90/F30)"

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        """Configure the vehicle language (applied at session level)."""
        self._language = str(language).upper()

    def get_dtc_reader(self) -> list[DTC]:
        """Read all currently stored fault codes."""
        return list(self._stored_dtc)

    def get_live_data(self, keys=None) -> list[LiveData]:
        """Read live data from the vehicle.

        No fabricated values: returns an empty list until a real connector
        (e.g. ELM327 over OBD-II) provides data. Signal definitions live in
        :attr:`LIVE_DATA_SPACES` for protocol use.
        """
        return []

    def clear_dtc(self) -> None:
        """Clear all currently stored fault codes."""
        self._stored_dtc = []

    def ecu_id(self) -> int:
        """Target ECU identifier (BMW CAN gateway / ECM node)."""
        return self._ecu_id

    def security_access(self) -> bool:
        """The BMW 3 Series requires security access for programming."""
        return True

    def send_seed(self, seed: bytes) -> bytes:
        """Ask the vehicle for a security seed (SBC-like SID 0x27).

        ``seed`` is the 4-byte key ID sent by the client; the ECU replies
        with a 4-byte seed. The J2534/PT3G driver forwards this request over
        the CAN bus and returns the seed from the response.

        Args:
            seed: 4-byte key ID sent by the client.

        Returns:
            4-byte seed returned by the ECU.

        Raises:
            ValueError: If the request is not exactly 4 bytes.
        """
        if len(seed) != 4:
            raise ValueError("BMW seed request (key ID) must be exactly 4 bytes")
        # Real driver: forward the seed request over the CAN bus via the
        # J2534/PT3G connector and return the seed from the response.
        raise NotImplementedError("no fabricated seed/key; requires a real connector")

    def send_key(self, key: bytes) -> bytes:
        """Send a seed response to the vehicle (SID 0x29).

        ``key`` is the 4-byte seed the ECU returned; the client replies
        with the encrypted session key.

        Args:
            key: 4-byte seed returned by the ECU.

        Returns:
            4-byte session key sent back to the ECU.

        Raises:
            ValueError: If the seed response is not exactly 4 bytes.
        """
        if len(key) != 4:
            raise ValueError("BMW seed response must be exactly 4 bytes")
        # Real driver: send the session key back over the CAN bus.
        raise NotImplementedError("no fabricated seed/key; requires a real connector")
