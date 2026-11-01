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

from dataclasses import dataclass
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
