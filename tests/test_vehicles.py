"""Tests for the auto-generated NHTSA vPIC vehicle catalogue."""
from __future__ import annotations

import re

from wildcat.cars import BMW, Ford, MercedesC300, VWAudi
from wildcat.cars.generic_obd2 import GenericOBD2
from wildcat.cars.vehicles import CATALOG, CATALOG_COUNT, CATALOG_MAKES, class_for_make

# Must stay in sync with scripts/clean_catalogue.py: corporate/manufacturer
# tokens that mark a NHTSA model_name row as a leaked manufacturer name. ``CORP``
# is a substring match (catches Corporation/Corp/Transcorp); ``INC.`` is dotted
# so real models like "Bolt Incomplete" / "Rincon" are not flagged.
_JUNK_RE = re.compile(
    r"(CORP|INC\.|LLC|LTD|INDUSTRIES|STEEL|MFG|DISTRIBUTOR|BROS|MANUFACTURER)",
    re.IGNORECASE,
)


def test_catalog_is_large_and_curated():
    # Authoritative NHTSA vPIC snapshot: thousands of rows across 31 makes.
    assert len(CATALOG) > 10_000
    assert CATALOG_COUNT == len(CATALOG)
    assert CATALOG_MAKES == 31
    makes = {entry["make"] for entry in CATALOG}
    assert len(makes) == 31
    assert "Mercedes-Benz" in makes and "Toyota" in makes and "Porsche" in makes


def test_catalog_year_range():
    years = {entry["year"] for entry in CATALOG}
    assert years == set(range(2000, 2025))


def test_catalog_entries_well_formed():
    for entry in CATALOG:
        assert set(entry) == {"class", "year", "make", "model"}
        assert isinstance(entry["class"], type)
        assert 2000 <= entry["year"] <= 2024
        assert isinstance(entry["make"], str) and entry["make"]
        assert isinstance(entry["model"], str) and entry["model"]


def test_catalog_has_no_manufacturer_junk():
    """NHTSA occasionally leaks manufacturer names into model_name; the cleaned
    catalogue must contain only real model labels."""
    for entry in CATALOG:
        assert not _JUNK_RE.search(entry["model"])
        assert entry["model"].strip() != entry["make"].strip()
        assert len(entry["model"]) <= 60


def test_make_class_mapping_real_models():
    assert class_for_make("Mercedes-Benz") is MercedesC300
    assert class_for_make("BMW") is BMW
    assert class_for_make("Ford") is Ford
    assert class_for_make("Volkswagen") is VWAudi
    assert class_for_make("Audi") is VWAudi


def test_make_class_mapping_curated_make_is_generic_stub():
    # Curated makes without a protocol model resolve to the read-only stub.
    assert class_for_make("Toyota") is GenericOBD2
    assert class_for_make("Acura") is GenericOBD2
    assert class_for_make("Porsche") is GenericOBD2


def test_make_class_mapping_unknown_make_is_generic():
    assert class_for_make("Not-A-Real-Make") is GenericOBD2


def test_make_class_table_has_all_curated_makes():
    # Every curated make has an explicit entry in the make->class table.
    from wildcat.cars.vehicles import _MAKE_CLASS

    assert len(_MAKE_CLASS) == CATALOG_MAKES == 31
    assert _MAKE_CLASS["Mercedes-Benz"] is MercedesC300
    assert _MAKE_CLASS["Volkswagen"] is VWAudi
    assert _MAKE_CLASS["Audi"] is VWAudi
    assert _MAKE_CLASS["Toyota"] is GenericOBD2


def test_mercedes_2008_c_class_maps_to_c300():
    entries = [
        e for e in CATALOG
        if e["make"] == "Mercedes-Benz" and e["year"] == 2008
    ]
    assert entries
    assert any(e["model"] == "C-Class" for e in entries)
    assert all(e["class"] is MercedesC300 for e in entries)
