"""Generic DTC text store with user-supplied overlay.

Provides human-readable text for OBD-II / UDS DTCs from a single source:

1. A user-supplied overlay loaded from a JSON file (or dict).  Overlay
   entries take precedence.

No generic (built-in) DTC descriptions are shipped: the previously
included SAE J2012 / ISO 15031-6 descriptions were removed because their
licence (copyright SAE/ISO) could not be verified as open.  Only
user-supplied overlays provide descriptions; unknown codes return None.

No proprietary or OEM (Mercedes or other) DTC text is shipped.
"""
from __future__ import annotations

import json
from pathlib import Path

# Generic, openly licensed DTC descriptions.
#
# AUDIT NOTE (2026-10-28): The previous generic table contained DTC
# descriptions written from general knowledge of the SAE J2012 / ISO 15031-6
# standard.  That standard is copyright SAE/ISO and its licence/provenance
# cannot be verified as open, so every entry was removed.  No proprietary or
# OEM (Mercedes or other) DTC text is shipped.  Only user-supplied overlays
# (ODX/PDX/JSON) provide descriptions; unknown codes return None.
_GENERIC: dict[str, str] = {}


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
