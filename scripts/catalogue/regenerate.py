"""Regenerate the NHTSA vPIC vehicle catalogue.

Produces ``src/wildcat/cars/vehicles.py``: a flat ``CATALOG`` of
``{"class", "year", "make", "model"}`` entries that :mod:`wildcat.cars.vin`
reads directly for the year/make/model selector and VIN resolver.

Modes
-----
Full (requires network):
    python scripts/catalogue/regenerate.py

Re-clean an existing catalogue in place (no network, idempotent):
    python scripts/catalogue/regenerate.py --clean-only

No fabrication
--------------
Every make/model/year comes from NHTSA's GetModelsForMakeYear API. Only a
curated set of 31 mass-market makes is kept (the vehicles a diagnostic shop
actually sees); vPIC's thousands of micro-builders are excluded, but any VIN
is still year/WMI-decodable by :mod:`wildcat.cars.vin`.

Year interpolation
------------------
Model presence is sampled at the ANCHOR years; a model seen in non-adjacent
anchors is assumed available for every year in [min, max] (documented in the
generated module header rather than hidden).
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "src" / "wildcat" / "cars" / "vehicles.py"

#: Real Wildcat car-class per make. Every other curated make -> GenericOBD2.
MAKE_CLASS: dict[str, str] = {
    "Mercedes-Benz": "MercedesC300",
    "BMW": "BMW",
    "Ford": "Ford",
    "Audi": "VWAudi",
    "Volkswagen": "VWAudi",
}
DEFAULT_CLASS = "GenericOBD2"

CURATED: list[str] = [
    "Mercedes-Benz", "BMW", "Porsche", "Audi", "Volkswagen",
    "Ford", "Chevrolet", "GMC", "Cadillac", "Buick", "Chrysler",
    "Dodge", "Jeep", "Ram", "Toyota", "Honda", "Acura", "Nissan",
    "Infiniti", "Hyundai", "Kia", "Mazda", "Subaru", "Volvo",
    "Land Rover", "Jaguar", "MINI", "Tesla", "Alfa Romeo",
    "Mitsubishi", "Fiat",
]

# 10 anchor years (includes 2008 for the C300 target).
ANCHORS = [2000, 2003, 2006, 2008, 2010, 2012, 2015, 2018, 2021, 2024]
SLEEP = 0.3

# Corporate/manufacturer tokens that mark a vPIC model_name row as a leaked
# manufacturer name (e.g. "Tramont Corporation", "X, Inc."). ``CORP`` is a
# substring match (catches Corporation/Corp/Transcorp); ``INC.`` is dotted so
# real models like "Bolt Incomplete" / "Rincon" are left untouched.
_JUNK_RE = re.compile(
    r"(CORP|INC\.|LLC|LTD|INDUSTRIES|STEEL|MFG|DISTRIBUTOR|BROS|MANUFACTURER)",
    re.IGNORECASE,
)


def is_junk(model: str, make: str) -> bool:
    if not model or model == make or len(model) > 60:
        return True
    return bool(_JUNK_RE.search(model))


def fetch(url: str, retries: int = 4) -> str:
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "wildcat-catalogue/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except OSError:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))
    return ""


def models_for_year(make: str, year: int) -> list[str]:
    url = (
        "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeYear"
        f"/make/{urllib.parse.quote(make)}/modelyear/{year}?format=csv"
    )
    rows = list(csv.DictReader(io.StringIO(fetch(url))))
    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        name = (r.get("model_name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def harvest() -> dict[str, dict[str, set[int]]]:
    """Raw scrape: make -> model -> set of anchor years present."""
    presence: dict[str, dict[str, set[int]]] = {m: {} for m in CURATED}
    for make in CURATED:
        for y in ANCHORS:
            try:
                ms = models_for_year(make, y)
            except OSError as e:
                print(f"WARN {make} {y}: {e}")
                ms = []
            for m in ms:
                presence[make].setdefault(m, set()).add(y)
        print(f"harvested {make}: {len(presence[make])} models")
        time.sleep(SLEEP)
    return presence


def build_entries(presence: dict[str, dict[str, set[int]]]) -> list[tuple[int, str, str, str]]:
    """Raw (year, make, model, class) tuples across interpolated spans."""
    entries: list[tuple[int, str, str, str]] = []
    for make in CURATED:
        cls = MAKE_CLASS.get(make, DEFAULT_CLASS)
        for model, years in presence[make].items():
            if not years:
                continue
            lo, hi = min(years), max(years)
            for y in range(lo, hi + 1):
                entries.append((y, make, model, cls))
    # Deterministic ordering: Mercedes-Benz first (so the VIN resolver's first
    # Mercedes match is a Mercedes platform), then make, model, year.
    entries.sort(key=lambda e: (e[1] != "Mercedes-Benz", e[1], e[2], e[0]))
    return entries


def clean_entries(
    raw: list[tuple[int, str, str, str]],
) -> tuple[list[tuple[int, str, str, str]], int]:
    """Drop junk rows, dedupe (year, make, model), re-sort. Returns (rows, dropped)."""
    seen: set[tuple[int, str, str]] = set()
    clean: list[tuple[int, str, str, str]] = []
    dropped = 0
    for y, make, model, cls in raw:
        if is_junk(model, make):
            dropped += 1
            continue
        key = (y, make, model)
        if key in seen:
            continue
        seen.add(key)
        clean.append((y, make, model, cls))
    clean.sort(key=lambda e: (e[1] != "Mercedes-Benz", e[1], e[2], e[0]))
    return clean, dropped


def make_class_pairs(raw: list[tuple[int, str, str, str]]) -> list[tuple[str, str]]:
    """Distinct make -> class, real models first then GenericOBD2 stubs."""
    mc: dict[str, str] = {}
    for _y, make, _model, cls in raw:
        mc.setdefault(make, cls)
    return sorted(mc.items(), key=lambda kv: (kv[1] == DEFAULT_CLASS, kv[0]))


def emit(clean: list[tuple[int, str, str, str]], dropped: int) -> str:
    pairs = make_class_pairs(clean)
    lines: list[str] = [
        "# auto-generated NHTSA vPIC data; long lines are data, not code",
        '"""Auto-generated authoritative vehicle catalogue.',
        "",
        "Source: NHTSA Product Information Catalog and Vehicle Listing (vPIC),",
        "https://vpic.nhtsa.dot.gov/api/ -- data submitted by manufacturers",
        "under 49 CFR 565. Regenerate with scripts/catalogue/regenerate.py.",
        "",
        "Coverage: a curated set of 31 mass-market makes (the vehicles a",
        "diagnostic shop actually sees). vPIC's full registry also includes",
        "thousands of bespoke low-volume builders; those are excluded here and",
        "are still VIN-decodable (year/WMI) by :mod:`wildcat.cars.vin`, which",
        "returns ``None`` for makes with no catalogue entry.",
        "",
        "Year availability: sampled at anchor years " + str(ANCHORS) + "; a",
        "model present in non-adjacent anchors is assumed available for every",
        "year in its [min, max] span (interpolated) -- documented here.",
        "",
        "Noise removal: vPIC's model_name field occasionally contains",
        "manufacturer names (e.g. \"Tramont Corporation\"); rows matching",
        "corporate/manufacturer tokens are filtered out (see _JUNK_RE).",
        "",
        "Make -> car-class mapping: Mercedes-Benz -> MercedesC300, BMW -> BMW,",
        "Ford -> Ford, Volkswagen/Audi -> VWAudi (protocol-specific). All other",
        "curated makes -> GenericOBD2, a read-only stub (recognised & selectable,",
        "but no vehicle-specific protocol model is implemented yet).",
        '"""',
        "from __future__ import annotations",
        "",
        "from wildcat.cars.bmw import BMW",
        "from wildcat.cars.ford import Ford",
        "from wildcat.cars.generic_obd2 import GenericOBD2",
        "from wildcat.cars.mercedes_c300 import MercedesC300",
        "from wildcat.cars.vw_audi import VWAudi",
        "",
        "_MAKE_CLASS = {",
    ]
    for make, cls_name in pairs:
        lines.append(f"    {make!r}: {cls_name},")
    lines += ["}", "", "CATALOG: list[dict] = ["]
    for y, make, model, cls_name in clean:
        lines.append(
            f'    {{"class": {cls_name}, "year": {y}, "make": {make!r}, "model": {model!r}}},'
        )
    lines += [
        "]",
        "",
        "def class_for_make(make: str):",
        '    """Return the Wildcat car class for a make (GenericOBD2 fallback)."""',
        "    return _MAKE_CLASS.get(make, GenericOBD2)",
        "",
        f"# Total catalogue entries: {len(clean)} | dropped junk: {dropped}",
        "CATALOG_COUNT = len(CATALOG)",
        f"CATALOG_MAKES = {len(pairs)}",
    ]
    return "\n".join(lines) + "\n"


def clean_only() -> list[tuple[int, str, str, str]]:
    """Re-clean the existing catalogue in place (no network)."""
    from wildcat.cars.vehicles import CATALOG as existing

    raw = [
        (e["year"], e["make"], e["model"], e["class"].__name__)
        for e in existing
    ]
    clean, dropped = clean_entries(raw)
    OUT.write_text(emit(clean, dropped), encoding="utf-8")
    print(f"clean-only: before={len(raw)} after={len(clean)} dropped={dropped}")
    return clean


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate the vPIC catalogue.")
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Re-clean an existing vehicles.py in place (no network).",
    )
    args = parser.parse_args(argv)
    if args.clean_only:
        clean_only()
    else:
        presence = harvest()
        clean, dropped = clean_entries(build_entries(presence))
        OUT.write_text(emit(clean, dropped), encoding="utf-8")
        print(f"DONE entries={len(clean)} makes={len(CURATED)} dropped={dropped} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
