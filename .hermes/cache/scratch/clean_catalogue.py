"""Clean + rewrite the NHTSA-sourced catalogue in place (idempotent).

Reads the CATALOG produced by harvest_catalogue.py, drops noisy/non-vehicle
rows that NHTSA leaks into the model_name field (manufacturer names such as
"Tramont Corporation"), dedupes, rebuilds an explicit make->class table, and
writes a clean vehicles.py. No network: operates on the already-fetched CATALOG.
"""
from __future__ import annotations

import re
from pathlib import Path

from wildcat.cars.vehicles import CATALOG as RAW

OUT = Path("/root/wildcat/src/wildcat/cars/vehicles.py")

# Corporate/manufacturer tokens that mark a NHTSA model_name row as a leaked
# manufacturer name (e.g. "Tramont Corporation", "X, Inc.", "Foo LLC").
# CORP matches as a substring so it catches "Corporation"/"Corp"/"Transcorp",
# and INC. is anchored with its dot so real models like "Bolt Incomplete" /
# "Rincon" are left untouched.
JUNK_RE = re.compile(
    r"(CORP|INC\.|LLC|LTD|INDUSTRIES|STEEL|MFG|DISTRIBUTOR|BROS|MANUFACTURER)",
    re.IGNORECASE,
)


def is_junk(model: str, make: str) -> bool:
    if not model or model == make:
        return True
    if len(model) > 60:
        return True
    if JUNK_RE.search(model):
        return True
    return False


def main() -> None:
    seen: set[tuple[str, int, str]] = set()
    clean: list[tuple[int, str, str, str]] = []
    dropped = 0
    for e in RAW:
        make, model, year, cls = e["make"], e["model"], e["year"], e["class"].__name__
        if is_junk(model, make):
            dropped += 1
            continue
        key = (make, year, model)
        if key in seen:
            continue
        seen.add(key)
        clean.append((year, make, model, cls))

    clean.sort(key=lambda e: (e[1] != "Mercedes-Benz", e[1], e[2], e[0]))

    # Rebuild an explicit, 31-entry make -> class table straight from the
    # catalogue so every curated make (real models and GenericOBD2 alike) is
    # named outright rather than relying on the default fallback.
    make_class: dict[str, str] = {}
    for _e in RAW:
        make_class.setdefault(_e["make"], _e["class"].__name__)
    make_class_pairs = sorted(
        make_class.items(), key=lambda kv: (kv[1] != "GenericOBD2", kv[0])
    )

    lines = [
        "# auto-generated NHTSA vPIC data; long lines are data, not code",
        '"""Auto-generated authoritative vehicle catalogue.',
        "",
        "Source: NHTSA Product Information Catalog and Vehicle Listing (vPIC),",
        "https://vpic.nhtsa.dot.gov/api/ -- manufacturer-submitted data under",
        "49 CFR 565. Regenerated via the scripts in the repo; do not hand-edit.",
        "",
        "Coverage: a curated set of 31 mass-market makes (the vehicles a",
        "diagnostic shop actually sees). vPIC also contains thousands of bespoke",
        "low-volume builders; those are excluded here. Any VIN is still decoded",
        "for make/year/serial by :mod:`wildcat.cars.vin` (which returns ``None``",
        "for makes with no catalogue entry).",
        "",
        "Year availability: sampled from vPIC ``GetModelsForMakeYear`` at anchor",
        "years [2000, 2003, 2006, 2008, 2010, 2012, 2015, 2018, 2021, 2024]; a",
        "model present in non-adjacent anchor years is assumed available for",
        "every year in its [min, max] span (interpolated) -- standard catalogue",
        "behaviour, documented here rather than hidden.",
        "",
        "Noise removal: vPIC's model_name field occasionally contains manufacturer",
        "names (e.g. \"Tramont Corporation\"); rows matching corporate/manufacturer",
        "tokens are filtered out (see scripts/clean_catalogue.py).",
        "",
        "Make -> car-class mapping: Mercedes-Benz -> MercedesC300, BMW -> BMW,",
        "Ford -> Ford, Volkswagen/Audi -> VWAudi (protocol-specific models). All",
        "other curated makes -> GenericOBD2, a read-only stub (recognised and",
        "selectable, but no vehicle-specific protocol model has been implemented).",
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
    for make, cls_name in make_class_pairs:
        lines.append(f"    {make!r}: {cls_name},")
    lines += [
        "}",
        "",
        "CATALOG: list[dict] = [",
    ]
    for year, make, model, cls in clean:
        lines.append(f'    {{"class": {cls}, "year": {year}, "make": {make!r}, "model": {model!r}}},')
    lines += [
        "]",
        "",
        "def class_for_make(make: str):",
        '    """Return the Wildcat car class for a make (GenericOBD2 fallback)."""',
        "    return _MAKE_CLASS.get(make, GenericOBD2)",
        "",
        f"# Total catalogue entries: {len(clean)} | dropped junk: {dropped}",
        "CATALOG_COUNT = len(CATALOG)",
        f"CATALOG_MAKES = {len(make_class_pairs)}",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"before={len(RAW)} after={len(clean)} dropped={dropped} "
        f"make_class={len(make_class_pairs)}"
    )
    print("Mercedes 2008:", sorted({e["model"] for e in RAW if e["make"] == "Mercedes-Benz" and e["year"] == 2008}))
    print(
        "real-class keys:",
        sorted(k for k, v in make_class_pairs if v != "GenericOBD2"),
    )


if __name__ == "__main__":
    main()
