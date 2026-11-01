"""Plug-in security-algorithm interface.

A security algorithm converts an ECU-issued seed into the key the ECU
expects.  The algorithm is *manufacturer- and ECU-specific* and is NOT
part of this repository: no Mercedes (or other OEM) seed-to-key algorithm
is shipped or invented here.

This module provides an empty-by-default registry keyed by (ECU, level) so
that a legitimately documented algorithm can be plugged in by a caller
without changing Wildcat's core.  When no algorithm is registered for a
given (ECU, level) pair, :meth:`SecurityAlgorithmRegistry.compute_key`
raises :class:`NoAlgorithmConfiguredError` — an honest "not configured"
failure rather than a fabricated answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class NoAlgorithmConfiguredError(Exception):
    """Raised when no seed-to-key algorithm is registered for (ECU, level)."""


class SecurityAlgorithm(Protocol):
    """Callable that turns a seed into a key for one (ECU, level)."""

    def compute_key(self, seed: bytes, level: int = 1) -> bytes: ...


@dataclass
class AlgorithmEntry:
    ecu: str
    level: int
    algorithm: SecurityAlgorithm


class SecurityAlgorithmRegistry:
    """Empty-by-default registry of seed-to-key algorithms."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, int], SecurityAlgorithm] = {}

    def register(self, ecu: str, level: int, algorithm: SecurityAlgorithm) -> None:
        self._entries[(ecu, level)] = algorithm

    def has(self, ecu: str, level: int) -> bool:
        return (ecu, level) in self._entries

    def compute_key(self, ecu: str, seed: bytes, level: int = 1) -> bytes:
        algo = self._entries.get((ecu, level))
        if algo is None:
            raise NoAlgorithmConfiguredError(
                f"No seed-to-key algorithm configured for ECU={ecu!r}, level={level}"
            )
        return algo.compute_key(seed, level)

    def list_registered(self) -> list[tuple[str, int]]:
        return sorted(self._entries)


# Module-level default registry (empty).
DEFAULT_REGISTRY = SecurityAlgorithmRegistry()


# ---------------------------------------------------------------------------
# Security provider definitions (UnlockECU, MIT licence)
# ---------------------------------------------------------------------------
# Source: https://github.com/jglim/UnlockECU (MIT, Copyright 2020 JinGen Lim).
# The db.json shipped there contains 3038 reverse-engineered provider
# definitions (ECU name, access level, seed/key lengths, provider, parameters).
# These are NOT manufacturer-licensed; they are reverse-engineered per the
# UnlockECU README.  Only the *definitions* (metadata) are ported here.  The
# actual seed-to-key *computation* is NOT ported (30+ C# algorithms); a
# concrete algorithm must still be registered in SecurityAlgorithmRegistry
# before compute_key can succeed.  No key is fabricated.

DATA_SOURCE_UNLOCKECU = "https://github.com/jglim/UnlockECU (MIT, reverse-engineered)"


@dataclass
class SecurityProvider:
    """A reverse-engineered security provider definition (metadata only)."""

    ecu: str
    access_level: int
    seed_length: int
    key_length: int
    provider: str
    origin: str = ""
    aliases: list[str] = field(default_factory=list)
    parameters: dict[str, str] = field(default_factory=dict)


class SecurityProviderRegistry:
    """Registry of UnlockECU provider definitions, keyed by (ECU, level)."""

    def __init__(self, data=None) -> None:
        self._entries: dict[tuple[str, int], list[SecurityProvider]] = {}
        if data is None:
            self._load_bundled()
        else:
            self._load(data)

    def _bundled_path(self):
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "data" / "security_providers.json"
        return p if p.is_file() else None

    def _load(self, data) -> None:
        import json
        from pathlib import Path

        if isinstance(data, (str, Path)):
            with open(data, encoding="utf-8") as fh:
                data = json.load(fh)
        if not isinstance(data, list):
            return
        for entry in data:
            if not isinstance(entry, dict):
                continue
            ecu = str(entry.get("EcuName", "")).strip()
            level = int(entry.get("AccessLevel", 0))
            params = {}
            for p in entry.get("Parameters") or []:
                if isinstance(p, dict):
                    params[str(p.get("Key", ""))] = str(p.get("Value", ""))
            prov = SecurityProvider(
                ecu=ecu,
                access_level=level,
                seed_length=int(entry.get("SeedLength", 0)),
                key_length=int(entry.get("KeyLength", 0)),
                provider=str(entry.get("Provider", "")),
                origin=str(entry.get("Origin", "")),
                aliases=list(entry.get("Aliases") or []),
                parameters=params,
            )
            self._entries.setdefault((ecu, level), []).append(prov)

    def _load_bundled(self) -> None:
        p = self._bundled_path()
        if p is None:
            return
        self._load(p)

    def lookup(self, ecu: str, level: int) -> list[SecurityProvider]:
        return list(self._entries.get((ecu, level), []))

    def has(self, ecu: str, level: int) -> bool:
        return bool(self._entries.get((ecu, level)))

    def count(self) -> int:
        return sum(len(v) for v in self._entries.values())

    def unique_ecus(self) -> int:
        return len({k[0] for k in self._entries})

    def unique_providers(self) -> list[str]:
        return sorted({p.provider for v in self._entries.values() for p in v})
