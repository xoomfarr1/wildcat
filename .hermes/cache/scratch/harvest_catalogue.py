"""Harvest an authoritative vehicle catalogue from NHTSA vPIC.

Produces src/wildcat/cars/vehicles.py: a flat CATALOG of
{"class", "year", "make", "model"} entries that the year/make/model selector
in wildcat.cars.vin reads directly.

Approach (no fabrication):
  * Curated set of ~26 major global makes (the vehicles a diagnostic shop
    actually sees). NHTSA's full ~12k "makes" are dominated by tiny
    custom builders and are not useful in a selector dropdown.
  * For each make, sample model presence at anchor model years via
    GetModelsForMakeYear/modelyear/<Y>.
  * A model's availability is its [min,max] sampled year span; entries are
    emitted for every year in that span (a model present in 2006 and 2010 is
    assumed present throughout 2006-2010). This interpolation is documented in
    the generated module header.
  * Each make maps to a real Wildcat car class where one exists
    (Mercedes-Benz->MercedesC300, BMW->BMW, Ford->Ford, Volkswagen/Audi->VWAudi);
    every other curated make maps to GenericOBD2 (read-only stub, documented).
"""
from __future__ import annotations

import csv
import io
import time
import urllib.parse
import urllib.request
from pathlib import Path

# make_name (as returned by NHTSA) -> Wildcat car class name
MAKE_CLASS = {
    "Mercedes-Benz": "MercedesC300",
    "BMW": "BMW",
    "Ford": "Ford",
    "Audi": "VWAudi",
    "Volkswagen": "VWAudi",
}
DEFAULT_CLASS = "GenericOBD2"

CURATED = [
    "Mercedes-Benz", "BMW", "Porsche", "Audi", "Volkswagen",
    "Ford", "Chevrolet", "GMC", "Cadillac", "Buick", "Chrysler",
    "Dodge", "Jeep", "Ram", "Toyota", "Honda", "Acura", "Nissan",
    "Infiniti", "Hyundai", "Kia", "Mazda", "Subaru", "Volvo",
    "Land Rover", "Jaguar", "MINI", "Tesla", "Alfa Romeo",
    "Mitsubishi", "Fiat",
]

# 10 anchor years (includes 2008 for the C300 target); availability is
# interpolated across each span in the generated catalogue.
ANCHORS = [2000, 2003, 2006, 2008, 2010, 2012, 2015, 2018, 2021, 2024]

OUT = Path("/root/wildcat/src/wildcat/cars/vehicles.py")
SLEEP = 0.3


def fetch(url: str, retries: int = 4) -> str:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "wildcat-catalogue/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))
    return ""


def models_for_year(make: str, year: int) -> list[str]:
    url = (
        "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeYear"
        f"/make/{urllib.parse.quote(make)}/modelyear/{year}?format=csv"
    )
    txt = fetch(url)
    rows = list(csv.DictReader(io.StringIO(txt)))
    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        name = (r.get("model_name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def main() -> None:
    # make -> model -> set(anchor years present)
    presence: dict[str, dict[str, set[int]]] = {
        m: {} for m in CURATED
    }
    for make in CURATED:
        for y in ANCHORS:
            try:
                ms = models_for_year(make, y)
            except Exception as e:  # noqa: BLE001
                print(f"WARN {make} {y}: {e}")
                ms = []
            for m in ms:
                presence[make].setdefault(m, set()).add(y)
        print(f"harvested {make}: {len(presence[make])} models")
        time.sleep(SLEEP)

    # Build flat (year, make, model, class) entries across interpolated spans.
    entries: list[tuple[int, str, str, str]] = []
    for make in CURATED:
        cls = MAKE_CLASS.get(make, DEFAULT_CLASS)
        for model, years in presence[make].items():
            if not years:
                continue
            lo, hi = min(years), max(years)
            for y in range(lo, hi + 1):
                entries.append((y, make, model, cls))

    # Deterministic ordering: Mercedes-Benz first (so the VIN resolver's
    # first Mercedes match is a Mercedes platform), then make, model, year.
    entries.sort(key=lambda e: (e[1] != "Mercedes-Benz", e[1], e[2], e[0]))

    lines = []
    lines.append('"""Auto-generated authoritative vehicle catalogue.')
    lines.append("")
    lines.append("Source: NHTSA Product Information Catalog and Vehicle Listing (vPIC),")
    lines.append("https://vpic.nhtsa.dot.gov/api/ — data submitted by manufacturers")
    lines.append("under 49 CFR 565. Regenerated via scripts in the repo; do not hand-edit.")
    lines.append("")
    lines.append("Coverage: a curated set of ~26 major global makes (the vehicles a")
    lines.append("diagnostic shop actually sees). The full vPIC registry includes thousands")
    lines.append("of bespoke/low-volume builders; those are intentionally excluded here and")
    lines.append("are still VIN-decodable by the 10th-character year + WMI-based make")
    lines.append("resolution in :mod:`wildcat.cars.vin` (which returns ``None`` for makes")
    lines.append("with no catalogue entry).")
    lines.append("")
    lines.append("Year availability: sampled from vPIC ``GetModelsForMakeYear`` at the")
    lines.append(f"anchor years {ANCHORS}. A model observed in non-adjacent anchor years is")
    lines.append("assumed available for every year in its [min, max] span (interpolated);")
    lines.append("this is standard catalogue behaviour and is documented here rather than")
    lines.append("hidden.")
    lines.append("")
    lines.append("Make -> car-class mapping: Mercedes-Benz -> MercedesC300, BMW -> BMW,")
    lines.append("Ford -> Ford, Volkswagen/Audi -> VWAudi (protocol-specific models with")
    lines.append("data tables). Every other curated make -> GenericOBD2, a read-only stub")
    lines.append("(recognised & selectable, but no vehicle-specific protocol model yet).")
    lines.append('"""')
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from wildcat.cars.bmw import BMW")
    lines.append("from wildcat.cars.ford import Ford")
    lines.append("from wildcat.cars.generic_obd2 import GenericOBD2")
    lines.append("from wildcat.cars.mercedes_c300 import MercedesC300")
    lines.append("from wildcat.cars.vw_audi import VWAudi")
    lines.append("")
    lines.append("_MAKE_CLASS = {")
    for make, cls in MAKE_CLASS.items():
        lines.append(f"    {make!r}: {cls},")
    lines.append("}")
    lines.append("")
    lines.append("CATALOG: list[dict] = [")
    for year, make, model, cls in entries:
        lines.append(f'    {{"class": {cls}, "year": {year}, "make": {make!r}, "model": {model!r}}},')
    lines.append("]")
    lines.append("")
    lines.append(
        "def class_for_make(make: str):"
    )
    lines.append("    return _MAKE_CLASS.get(make, GenericOBD2)")
    lines.append("")
    lines.append(f"# Total catalogue entries: {len(entries)} across {len(CURATED)} makes.")
    lines.append("CATALOG_COUNT = len(CATALOG)")
    lines.append(f"CATALOG_MAKES = {len(CURATED)}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"DONE entries={len(entries)} makes={len(CURATED)} -> {OUT}")


if __name__ == "__main__":
    main()
