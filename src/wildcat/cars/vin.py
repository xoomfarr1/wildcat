"""VIN decoding and vehicle-model resolution for Wildcat.

A VIN (Vehicle Identification Number) is 17 characters. This module validates a
VIN, decodes the fields wildcat cares about for diagnostics, and maps a VIN (or
a manual year/make/model selection) onto one of the supported
:class:`~wildcat.cars.base.CarModel` instances.

What we decode
--------------
* **year** -- the 10th character, via the SAE J1199 / ISO 3779 30-year cycle.
  ``8`` -> 2008, ``A`` -> 2010, ``L`` -> 2020, etc.
* **make** -- from the WMI (first three characters) using a curated table. A
  two-character prefix fallback covers makes with many WMIs (e.g. ``1F`` -> Ford).
* **serial** -- characters 10..17 (the VDS/VIS portion), the part most relevant
  to a VIN-mismatch repair (e.g. an EIS/electronic steering lock swap) since it
  ties a chassis to its module programming.

Only the makes wildcat ships car models for are mapped; everything else is
still decoded (make/year/serial are returned) but :func:`find_vehicle_by_vin`
returns ``None`` so the UI can tell the user the vehicle isn't supported yet.
"""
from __future__ import annotations

from dataclasses import dataclass

from wildcat.cars import BMW, Ford, MercedesC300, VWAudi
from wildcat.cars.base import CarModel

#: 10th-character VIN positions decode to a year. Digits 0-9 cover 2000-2009 and
#: the letters A-Y (I, O, Q never appear in a VIN) cover 2010-2030; the cycle
#: repeats every 30 years, so this table gives the most-recent matching year.
_YEAR_CODES: dict[str, int] = {
    "0": 2000,
    "1": 2001, "2": 2002, "3": 2003, "4": 2004,
    "5": 2005, "6": 2006, "7": 2007, "8": 2008, "9": 2009,
    "A": 2010, "B": 2011, "C": 2012, "D": 2013, "E": 2014,
    "F": 2015, "G": 2016, "H": 2017, "J": 2018, "K": 2019,
    "L": 2020, "M": 2021, "N": 2022, "P": 2023, "R": 2024,
    "S": 2025, "T": 2026, "V": 2027, "W": 2028, "X": 2029, "Y": 2030,
}

#: First-three-character WMI -> manufacturer for the makes we support (and a
#: few common neighbours). Used to resolve a VIN to a wildcat car model.
_WMI_MAKE: dict[str, str] = {
    # Germany
    "WDB": "Mercedes-Benz", "WDC": "Mercedes-Benz", "WDD": "Mercedes-Benz",
    "WBA": "BMW", "WBS": "BMW",
    "WVW": "Volkswagen", "WSW": "Volkswagen",
    "WAU": "Audi",
    # Japan / Korea (decoded for completeness; no wildcat model yet)
    "KMHD": "Hyundai", "JH1": "Yamaha",
    # USA
    "1G1": "Chevrolet", "1G2": "Saturn",
}
#: Two-character prefix fallback (covers makes with many WMIs, e.g. Ford).
_PREFIX_MAKE: dict[str, str] = {
    "1F": "Ford", "2F": "Ford",
    "1G": "Chevrolet",
    "3C": "Chrysler", "4T": "Toyota",
}

#: Supported vehicles: how each (year, make, model) triplet maps to a car class.
#: This is the catalogue the manual selector and the VIN resolver both read.
CATALOG: list[dict] = [
    {"class": MercedesC300, "year": 2008, "make": "Mercedes-Benz", "model": "C300"},
    {"class": BMW, "year": 2006, "make": "BMW", "model": "3 Series"},
    {"class": Ford, "year": 2004, "make": "Ford", "model": "Focus"},
    {"class": VWAudi, "year": 2010, "make": "Volkswagen", "model": "Golf"},
]


@dataclass(frozen=True)
class VinDecode:
    """Decoded fields from a 17-character VIN."""

    vin: str
    valid: bool
    year: int | None
    make: str | None
    model: str | None
    serial: str
    reason: str = ""

    @property
    def label(self) -> str:
        """Best-effort human label."""
        if self.make and self.year and self.model:
            return f"{self.make} {self.model} ({self.year})"
        return self.vin


def decode_vin(vin: str) -> VinDecode:
    """Validate and decode a VIN.

    Args:
        vin: The 17-character VIN string (case-insensitive).

    Returns:
        A :class:`VinDecode`. ``valid`` is False with a ``reason`` if the VIN
        fails validation (wrong length, illegal characters); otherwise the
        decoded year/make/model (make/model may be None for unknown WMIs).
    """
    raw = vin.strip().upper()
    if len(raw) != 17:
        return VinDecode(raw, False, None, None, None, "", "VIN must be 17 characters")
    # I, O, Q are forbidden in a VIN (and Z is not used for positions 1-8); Z
    # is tolerated in the serial region since some vendors use it there.
    bad = sorted({c for c in raw[:9] if c not in "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"})
    if bad:
        return VinDecode(raw, False, None, None, None, "", f"illegal VIN character(s): {''.join(bad)}")

    year = _YEAR_CODES.get(raw[9])  # 10th character (index 9) = model year
    make = _WMI_MAKE.get(raw[:3]) or _PREFIX_MAKE.get(raw[:2])
    model = None  # a single VIN does not encode the trim unambiguously
    # Positions 11-17 (index 10 onward) are the VIS = chassis serial number.
    serial = raw[10:]
    return VinDecode(raw, True, year, make, model, serial)


def find_vehicle(year: int, make: str, model: str) -> CarModel | None:
    """Resolve a manual year/make/model selection to a car model instance.

    Args:
        year: Model year.
        make: Manufacturer label.
        model: Model label.

    Returns:
        A :class:`CarModel` instance, or ``None`` if the combination is
        unsupported.
    """
    for entry in CATALOG:
        if entry["year"] == year and entry["make"] == make and entry["model"] == model:
            return entry["class"]()
    return None


def find_vehicle_by_vin(vin: str) -> CarModel | None:
    """Resolve a VIN to a car model instance, if supported.

    Matches the decoded make against the catalogue; if the make matches a
    supported entry it returns that car. (The catalogue currently has one
    Mercedes model, so any Mercedes VIN resolves to the C300 platform.)
    """
    decoded = decode_vin(vin)
    if not decoded.valid or decoded.make is None:
        return None
    for entry in CATALOG:
        if entry["make"] == decoded.make:
            return entry["class"]()
    return None


def makes_for_year(year: int) -> list[str]:
    """Supported manufacturers for a given model year (catalogue order)."""
    seen: list[str] = []
    for entry in CATALOG:
        if entry["year"] == year and entry["make"] not in seen:
            seen.append(entry["make"])
    return seen


def vehicle_triplet(vin: str) -> tuple[int, str, str] | None:
    """Decode a VIN and return the ``(year, make, model)`` it resolves to.

    Returns ``None`` if the VIN is invalid, or decodes to a make with no
    installed Wildcat car model. The GUI uses this to pre-fill the
    year/make/model cascade when a VIN is entered.
    """
    decoded = decode_vin(vin)
    if not decoded.valid or decoded.make is None:
        return None
    for entry in CATALOG:
        if entry["make"] == decoded.make:
            return (entry["year"], entry["make"], entry["model"])
    return None


def list_makes() -> list[str]:
    """Supported manufacturers in catalogue order."""
    seen: list[str] = []
    for entry in CATALOG:
        if entry["make"] not in seen:
            seen.append(entry["make"])
    return seen


def list_years() -> list[int]:
    """Supported model years (distinct, ascending)."""
    return sorted({entry["year"] for entry in CATALOG})


def list_models(year: int, make: str) -> list[str]:
    """Models offered for a given year + make."""
    return [
        entry["model"]
        for entry in CATALOG
        if entry["year"] == year and entry["make"] == make
    ]
