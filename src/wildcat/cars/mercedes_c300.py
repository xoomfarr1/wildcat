"""2008 Mercedes C300 (W204) car model.

This is the model the Actia PT3G VCI is built around: the PT3G exposes the
Mercedes SBC (secure automotive bus) diagnostic/security protocol over the
same CAN network the car uses. The model below is the data layer the PT3G
driver drives.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from wildcat.cars.base import DTC, CarModel, LiveData
from wildcat.cars.spaces import decode_signal


class MercedesC300(CarModel):
    """2008 Mercedes C300 platform model (W204, M271/Diamond star engine)."""

    # The PT3G VCI is the primary programming connector for the C300 platform:
    # it runs the Mercedes SBC security-access protocol (SIDs 0x27/0x29) over
    # the vehicle CAN bus. J2534 pass-thru is supported for read-only sessions
    # on the same bus.
    SUPPORTED_CONNECTORS: ClassVar[tuple[str, ...]] = ("PT3G",)

    # CAN identifier spaces (native Mercedes SBC/CAN IDs). Many addresses are
    # illustrative of the W204 layout and do not represent a real byte map.
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
        "ELECTRICAL": [
            {"code": "U0100", "description": "Lost communication with ECM", "severity": "Critical", "is_temporary": False},
        ],
    }

    LIVE_DATA_SPACES: ClassVar[dict[str, list[dict[str, object]]]] = {
        "ENGINE": [
            {"name": "EngineRPM", "address": 0x213, "length": 2, "sample": 6000, "scale": 0.125, "offset": 0.0, "unit": "rpm"},
            {"name": "IntakeManifoldPressure", "address": 0x203, "length": 2, "sample": 6000, "scale": 0.01, "offset": 0.0, "unit": "kPa"},
            {"name": "CoolantTemp", "address": 0x100, "length": 1, "sample": 92, "scale": 1.0, "offset": 0.0, "unit": "°C"},
            {"name": "ThrottlePosition", "address": 0x1F1, "length": 1, "sample": 100, "scale": 0.1, "offset": 0.0, "unit": "%"},
        ],
        "TRANSMISSION": [
            {"name": "Gear", "address": 0x240, "length": 4, "sample": 3, "scale": 1.0, "offset": 0.0, "unit": "gear"},
            {"name": "OutputSpeed", "address": 0x241, "length": 2, "sample": 1800, "scale": 0.1, "offset": 0.0, "unit": "rpm"},
        ],
        "COOLING": [
            {"name": "IntakeAirTemp", "address": 0x101, "length": 1, "sample": 21.5, "scale": 1.0, "offset": 0.0, "unit": "°C"},
            {"name": "RadiatorFan", "address": 0x270, "length": 1, "sample": 1, "scale": 1.0, "offset": 0.0, "unit": "state"},
        ],
        "CHASSIS": [
            {"name": "VehicleSpeed", "address": 0x0D, "length": 1, "sample": 65, "scale": 1.0, "offset": 0.0, "unit": "km/h"},
            {"name": "AuxBatteryVoltage", "address": 0x3C, "length": 2, "sample": 132, "scale": 0.1, "offset": 0.0, "unit": "V"},
        ],
        "ELECTRICAL": [
            {"name": "BatteryCurrent", "address": 0x3F, "length": 2, "sample": 100, "scale": 0.1, "offset": 0.0, "unit": "A"},
            {"name": "SoC", "address": 0x3D, "length": 1, "sample": 85, "scale": 1.0, "offset": 0.0, "unit": "%"},
        ],
    }

    _POWERTRAIN_ECU_ID = 0x12

    def __init__(self) -> None:
        super().__init__()
        self._language = "EN"
        self._ecu_id = self._POWERTRAIN_ECU_ID
        # Fault codes currently stored in the vehicle's offline table.
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
        return "Mercedes C300 (2008)"

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
        for signals in self.LIVE_DATA_SPACES.values():
            for sig in signals:
                if keys and sig["name"] not in keys:
                    continue
                raw = sig.get("sample", 0)
                value = round(decode_signal(sig, raw), 2)
                out.append(LiveData(name=sig["name"], value=value, unit=sig.get("unit", "")))
        return out

    def clear_dtc(self) -> None:
        """Clear all currently stored fault codes."""
        self._stored_dtc = []

    def ecu_id(self) -> int:
        """Target ECU identifier (SBC powertrain node)."""
        return self._ecu_id

    def security_access(self) -> bool:
        """The C300 requires security access for programming."""
        return True

    def send_seed(self, seed: bytes) -> bytes:
        """Ask the vehicle for a security seed (SBC SID 0x27).

        ``seed`` is the 4-byte key ID the client sent to request a seed;
        the ECU replies with a 4-byte seed. The PT3G driver forwards this
        request over the VCI to the powertrain ECU (CAN 0x12) and returns
        the seed from the response.

        Args:
            seed: 4-byte key ID sent by the client.

        Returns:
            4-byte seed returned by the ECU.

        Raises:
            ValueError: If the request is not exactly 4 bytes.
        """
        if len(seed) != 4:
            raise ValueError("SBC seed request (key ID) must be exactly 4 bytes")
        # Real driver: forward the seed request over the PT3G/VCI and return
        # the seed from the ECU response.
        return bytes((0xA5, 0x5A, 0xA5, 0x5A))

    def send_key(self, key: bytes) -> bytes:
        """Send a seed response to the vehicle (SBC SID 0x29).

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
            raise ValueError("SBC seed response must be exactly 4 bytes")
        # Real driver: send the session key back over the PT3G/VCI.
        return bytes((0x01, 0x02, 0x03, 0x04))
