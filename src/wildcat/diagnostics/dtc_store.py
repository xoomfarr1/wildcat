"""Generic DTC text store with user-supplied overlay.

Provides human-readable text for OBD-II / UDS DTCs from two sources:

1. A small *generic* table of widely-published, non-proprietary DTC
   descriptions (common powertrain codes).  These are public knowledge, not
   OEM-licensed text.
2. An optional *user-supplied overlay* loaded from a JSON file (e.g. an
   exported ODX/PDX/CSV-derived mapping).  Overlay entries take precedence
   over the generic table.

Unknown codes return ``None`` (honest fallback) rather than a fabricated
description.  No Mercedes (or other OEM) licensed DTC text is shipped.
"""
from __future__ import annotations

import json
from pathlib import Path

# Generic, publicly documented OBD-II DTC descriptions.  Keep this small and
# non-proprietary: only widely-published codes.
_GENERIC: dict[str, str] = {
    "P0001": "Fuel Volume Regulator Control Circuit/Open",
    "P0002": "Fuel Volume Regulator Control Circuit Range/Performance",
    "P0100": "Mass or Volume Air Flow Circuit Malfunction",
    "P0101": "Mass or Volume Air Flow Circuit Range/Performance Problem",
    "P0102": "Mass or Volume Air Flow Circuit Low Input",
    "P0103": "Mass or Volume Air Flow Circuit High Input",
    "P0110": "Intake Air Temperature Circuit Malfunction",
    "P0115": "Engine Coolant Temperature Circuit Malfunction",
    "P0120": "Throttle/Pedal Position Sensor A Circuit Malfunction",
    "P0130": "O2 Sensor Circuit Malfunction (Bank 1 Sensor 1)",
    "P0171": "System Too Lean (Bank 1)",
    "P0172": "System Too Rich (Bank 1)",
    "P0300": "Random/Multiple Cylinder Misfire Detected",
    "P0301": "Cylinder 1 Misfire Detected",
    "P0302": "Cylinder 2 Misfire Detected",
    "P0303": "Cylinder 3 Misfire Detected",
    "P0304": "Cylinder 4 Misfire Detected",
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
    "P0440": "Evaporative Emission Control System Malfunction",
    "P0442": "Evaporative Emission Control System Leak Detected (Small Leak)",
    "P0455": "Evaporative Emission Control System Leak Detected (Large Leak)",
    "P0500": "Vehicle Speed Sensor Malfunction",
    "P0505": "Idle Air Control System Malfunction",
    "P0600": "Serial Communication Link Malfunction",
}


class DTCStore:
    def __init__(self, overlay=None) -> None:
        self._generic = dict(_GENERIC)
        self._overlay: dict[str, str] = {}
        if overlay:
            self.load_overlay(overlay)

    def load_overlay(self, overlay) -> None:
        """Load a user-supplied mapping (dict or path/JSON)."""
        if isinstance(overlay, (str, Path)):
            with open(overlay, encoding="utf-8") as fh:
                data = json.load(fh)
        else:
            data = overlay
        if not isinstance(data, dict):
            raise TypeError("overlay must be a dict or JSON object")
        for k, v in data.items():
            self._overlay[str(k).upper()] = str(v)

    def lookup(self, code: str) -> str | None:
        code = code.upper().strip()
        if code in self._overlay:
            return self._overlay[code]
        return self._generic.get(code)

    def known_codes(self) -> list[str]:
        return sorted(set(self._generic) | set(self._overlay))
