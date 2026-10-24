"""Tests for the VIN decoder, vehicle resolver, and NHTSA-sourced catalogue."""
from __future__ import annotations

import pytest

from wildcat.cars import BMW, MercedesC300
from wildcat.cars.generic_obd2 import GenericOBD2
from wildcat.cars.vin import (
    CATALOG,
    decode_vin,
    find_vehicle,
    find_vehicle_by_vin,
    list_makes,
    list_models,
    list_years,
    makes_for_year,
    vehicle_triplet,
)

# A 2008 Mercedes C300 VIN: WMI=WDB, 10th char (index 9)='8' -> 2008, VIS=positions 11-17
VIN_2008_C300 = "WDB9040408BA12345"
# A 2010 BMW VIN: WMI=WBA, 10th char='A' -> 2010
VIN_2010_BMW = "WBA301123A1234567"
# 1G1 -> Chevrolet (curated make, no protocol model), 10th char='1' -> 2001
VIN_2001_CHEVY = "1G1YY23571A123456"
# 1G2 -> Saturn (not in the curated catalogue), 10th char='1' -> 2001
VIN_2001_SATURN = "1G2YY23571A123456"


# --- catalogue scope ---------------------------------------------------------
def test_catalog_covers_supported_makes():
    """Every catalogue entry resolves to one of Wildcat's car classes."""
    classes = {entry["class"].__name__ for entry in CATALOG}
    assert classes == {"MercedesC300", "BMW", "Ford", "VWAudi", "GenericOBD2"}


def test_catalog_is_authoritative_nhtsa_set():
    """The catalogue spans 2000-2024 and contains no hand-authored junk."""
    years = list_years()
    assert years == list(range(2000, 2025))
    makes = list_makes()
    assert len(makes) == 31
    assert makes[0] == "Mercedes-Benz"  # anchor make, sorted first
    assert {"BMW", "Ford", "Volkswagen", "Audi", "Toyota"} <= set(makes)


# --- decode ------------------------------------------------------------------
def test_decode_valid_mercedes_vin_2008():
    d = decode_vin(VIN_2008_C300)
    assert d.valid
    assert d.year == 2008
    assert d.make == "Mercedes-Benz"
    # VIS = positions 11-17 (7 chars), excludes the year char at position 10
    assert d.serial == "BA12345"
    assert len(d.serial) == 7


def test_decode_valid_bmw_vin_2010():
    d = decode_vin(VIN_2010_BMW)
    assert d.valid
    assert d.year == 2010
    assert d.make == "BMW"
    assert d.serial == "1234567"


def test_decode_is_case_insensitive_and_strips():
    d = decode_vin("  wdb9040408ba12345  ")
    assert d.valid
    assert d.vin == "WDB9040408BA12345"
    assert d.year == 2008


@pytest.mark.parametrize("vin", ["short", "WDB9040408BA1234", "WDB9040408BA123456"])
def test_invalid_vin_length_marked_invalid(vin):
    d = decode_vin(vin)
    assert not d.valid
    assert d.year is None and d.make is None


def test_invalid_vin_characters_rejected():
    # 'O' (letter O, forbidden) at position 9
    d = decode_vin("WDB90404O8BA12345")
    assert not d.valid
    assert "illegal VIN character" in d.reason


# --- resolve by VIN ----------------------------------------------------------
def test_find_vehicle_by_vin_resolves_mercedes():
    car = find_vehicle_by_vin(VIN_2008_C300)
    assert isinstance(car, MercedesC300)
    assert car.name == "Mercedes C300 (2008)"


def test_find_vehicle_by_vin_resolves_bmw():
    car = find_vehicle_by_vin(VIN_2010_BMW)
    assert isinstance(car, BMW)


def test_find_vehicle_by_known_make_returns_generic_stub():
    # Chevrolet is curated but has no protocol model, so it resolves to the
    # read-only GenericOBD2 stub instead of None.
    car = find_vehicle_by_vin(VIN_2001_CHEVY)
    assert isinstance(car, GenericOBD2)
    assert car.name == "Generic OBD-II"


def test_find_vehicle_by_uncatalogued_make_returns_none():
    # Saturn is not in the curated catalogue -> no Wildcat profile.
    assert find_vehicle_by_vin(VIN_2001_SATURN) is None


# --- resolve by triplet ------------------------------------------------------
def test_find_vehicle_by_manual_triplet():
    car = find_vehicle(2008, "Mercedes-Benz", "C-Class")
    assert isinstance(car, MercedesC300)
    assert car.name == "Mercedes C300 (2008)"


def test_find_vehicle_unknown_triplet_returns_none():
    assert find_vehicle(1999, "Mercedes-Benz", "DoesNotExist") is None


# --- list helpers ------------------------------------------------------------
def test_list_helpers_consistent():
    makes = list_makes()
    years = list_years()
    assert years == sorted(years)
    assert years[0] == 2000 and years[-1] == 2024
    assert makes[0] == "Mercedes-Benz"
    assert {"BMW", "Ford", "Audi", "Toyota"} <= set(makes)
    mercedes_2008 = list_models(2008, "Mercedes-Benz")
    assert "C-Class" in mercedes_2008
    # Catalogue-sorted within (year, make).
    assert mercedes_2008 == sorted(mercedes_2008)
    assert list_models(2024, "Mercedes-Benz")  # has 2024 models
    assert "Mercedes-Benz" in makes_for_year(2008)


def test_vehicle_triplet_for_known_vin():
    triplet = vehicle_triplet(VIN_2008_C300)
    assert triplet == (2008, "Mercedes-Benz", "C-Class")


def test_vehicle_triplet_for_uncatalogued_make_is_none():
    assert vehicle_triplet(VIN_2001_SATURN) is None  # Saturn


def test_vehicle_triplet_for_invalid_vin_is_none():
    assert vehicle_triplet("short") is None
