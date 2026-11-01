"""Generic DTC text store with user-supplied overlay.

Provides human-readable text for OBD-II / UDS DTCs from a single source:

1. A user-supplied overlay loaded from a JSON file (or dict).  Overlay
   entries take precedence.
2. Bundled Automotive-9/dtc-codes data, included at Zach's direction as a
   user-supplied overlay (licence unverified).

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
        self._scoped: dict[tuple[str, str], str] = {}
        self._fallback: dict[str, str] = {}
        self._load_bundled()
        if overlay:
            self.load_overlay(overlay)

    @staticmethod
    def _norm_mfr(name) -> str:
        return "".join(ch for ch in str(name).upper() if ch.isalnum())

    def _bundled_dir(self) -> Path | None:
        p = Path(__file__).resolve().parent.parent / "data" / "dtc"
        if p.is_dir():
            return p
        return None

    @staticmethod
    def normalize_code(code) -> str:
        """Normalize a DTC code for lookup.

        Strips surrounding whitespace and stray double-quotes (seen in the
        bundled GM file), and upper-cases.  VW codes are 5-digit numeric
        strings (e.g. "00001") and BMW codes are 4-digit (e.g. "0001");
        these are distinct formats and are NOT converted between each other
        -- they are looked up verbatim after normalization.
        """
        return str(code).upper().strip().strip('"').strip()

    def _load_bundled(self) -> None:
        d = self._bundled_dir()
        if d is None:
            return
        for json_file in sorted(d.glob("*.json")):
            manufacturer = self._norm_mfr(json_file.stem)
            try:
                with json_file.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    for k, v in data.items():
                        code = self.normalize_code(k)
                        desc = str(v)
                        self._scoped[(manufacturer, code)] = desc
                        if code not in self._fallback:
                            self._fallback[code] = desc
            except (OSError, ValueError, json.JSONDecodeError):
                continue

    def load_overlay(self, overlay) -> None:
        """Load a user-supplied mapping (dict or path to a JSON file).

        User overlay entries take precedence over bundled data on lookup
        (checked first in lookup()).  Supply a path to a JSON file mapping
        code -> description, or a dict.  Unknown codes fall back to None
        unless a description is supplied.
        """
        if isinstance(overlay, (str, Path)):
            with open(overlay, encoding="utf-8") as fh:
                data = json.load(fh)
        else:
            data = overlay
        if not isinstance(data, dict):
            raise TypeError("overlay must be a dict or a path to a JSON file")
        for k, v in data.items():
            self._overlay[self.normalize_code(k)] = str(v)

    def lookup(self, code: str, manufacturer=None) -> str | None:
        code = self.normalize_code(code)
        # User overlay takes precedence over bundled data.
        if code in self._overlay:
            return self._overlay[code]
        if manufacturer is not None:
            key = (self._norm_mfr(manufacturer), code)
            if key in self._scoped:
                return self._scoped[key]
        if code in self._fallback:
            return self._fallback[code]
        return self._generic.get(code)

    def known_codes(self) -> list[str]:
        codes = set(self._generic) | set(self._overlay) | set(self._fallback)
        codes |= {c for (_, c) in self._scoped}
        return sorted(codes)
