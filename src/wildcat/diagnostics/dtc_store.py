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

# Data source note:
# The bundled JSON files under src/wildcat/data/dtc/ are copied verbatim from
# https://github.com/Automotive-9/dtc-codes (10 manufacturer files, ~31272 codes).
# That repository has NO licence file; its licence/provenance is NOT verified
# as open.  They are included here at the user's (Zach's) explicit direction
# as a user-supplied overlay, NOT as openly licensed data.  No Mercedes file
# exists in that source, so Mercedes DTC descriptions remain unknown unless the
# user supplies a Mercedes mapping.
DATA_SOURCE = "https://github.com/Automotive-9/dtc-codes (licence unverified)"

# Audit note (2026-10-28): a previous generic table of SAE J2012 / ISO 15031-6
# DTC descriptions was removed because its licence (copyright SAE/ISO) could not
# be verified as open.  No proprietary or OEM (Mercedes or other) DTC text is
# shipped in _GENERIC.  Only user-supplied overlays (ODX/PDX/JSON, including the
# bundled Automotive-9/dtc-codes data loaded above) provide descriptions;
# unknown codes return None.
_GENERIC: dict[str, str] = {}


class DTCStore:
    def __init__(self, overlay=None) -> None:
        self._generic: dict[str, str] = {}
        self._overlay: dict[str, str] = {}
        # Load bundled user-supplied overlay data (Automotive-9/dtc-codes) if present.
        self._load_bundled()
        if overlay:
            self.load_overlay(overlay)

    def _bundled_dir(self) -> Path | None:
        # src/wildcat/data/dtc relative to this file
        p = Path(__file__).resolve().parent.parent / "data" / "dtc"
        if p.is_dir():
            return p
        return None

    def _load_bundled(self) -> None:
        d = self._bundled_dir()
        if d is None:
            return
        for json_file in sorted(d.glob("*.json")):
            try:
                with json_file.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    for k, v in data.items():
                        self._overlay[str(k).upper().strip().strip('"')] = str(v)
            except (OSError, ValueError, json.JSONDecodeError):
                # Skip unreadable files; never crash construction.
                continue

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
