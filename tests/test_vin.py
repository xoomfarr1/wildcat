"""Tests for the VIN decoder and vehicle resolver."""
from __future__ import annotations

import pytest

from wildcat.cars import BMW, MercedesC300
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

# A 2008 Mercedes C300 VIN: WMI=WDB, 10th char(index9)='8' -> 2008, VIS=positions 11-17
VIN_2008_C300 = "WDB9040408BA12345"

# A 2010 BMW VIN: WMI=WBA, 10th char(index9)='A' -> 2010
VIN_2010_BMW = "WBA301123A1234567"

# A 2008 Mercedes whose 10th char is wrong position should still fail length
SHORT_VIN = "WDB9040408BA1234"  # 16 chars


def test_catalog_covers_all_four_makes():
    makes = {entry["class"].__name__ for entry in CATALOG}
    assert makes == {"MercedesC300", "BMW", "Ford", "VWAudi"}


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


@pytest.mark.parametrize("vin", ["short", SHORT_VIN, "WDB9040408BA1234", "WDB9040408BA123456"])
def test_invalid_vin_length_marked_invalid(vin):
    d = decode_vin(vin)
    assert not d.valid
    assert d.year is None and d.make is None


def test_invalid_vin_characters_rejected():
    # 'O' (letter O, forbidden) at position 9
    d = decode_vin("WDB90404O8BA12345")
    assert not d.valid
    assert "illegal VIN character" in d.reason


def test_find_vehicle_by_vin_resolves_mercedes():
    car = find_vehicle_by_vin(VIN_2008_C300)
    assert isinstance(car, MercedesC300)
    assert car.name == "Mercedes C300 (2008)"


def test_find_vehicle_by_vin_resolves_bmw():
    car = find_vehicle_by_vin(VIN_2010_BMW)
    assert isinstance(car, BMW)


def test_find_vehicle_by_unknown_make_returns_none():
    # 1G1 = Chevrolet (no wildcat model)
    assert find_vehicle_by_vin("1G1YY23571A123456") is None


def test_find_vehicle_by_manual_triplet():
    car = find_vehicle(2008, "Mercedes-Benz", "C300")
    assert isinstance(car, MercedesC300)
    assert car.name == "Mercedes C300 (2008)"


def test_find_vehicle_unknown_triplet_returns_none():
    assert find_vehicle(1999, "Mercedes-Benz", "DoesNotExist") is None


def test_list_helpers_consistent():
    makes = list_makes()
    years = list_years()
    assert makes == ["Mercedes-Benz", "BMW", "Ford", "Volkswagen"]
    assert years == sorted(years)
    assert list_models(2008, "Mercedes-Benz") == ["C300"]
    assert list_models(2024, "Mercedes-Benz") == []


def test_vehicle_triplet_for_known_vin():
    triplet = vehicle_triplet(VIN_2008_C300)
    assert triplet == (2008, "Mercedes-Benz", "C300")


def test_vehicle_triplet_for_unknown_make_is_none():
    # 1G1 = Chevrolet, no Wildcat model
    assert vehicle_triplet("1G1YY23571A123456") is None


def test_vehicle_triplet_for_invalid_vin_is_none():
    assert vehicle_triplet("short") is None


def test_makes_for_year():
    assert makes_for_year(2008) == ["Mercedes-Benz"]
    assert makes_for_year(2010) == ["Volkswagen"]
    assert makes_for_year(2024) == []
