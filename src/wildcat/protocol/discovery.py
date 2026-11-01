"""DID/PID discovery helpers.

Inspired by studying jakka351/GenericDiagnosticTool (J2534 raw diagnostic tool)
for service coverage ideas.  The implementation here is original Python
following ISO 14229 (UDS) and is NOT a port of that project's code.  That
project's licence is listed as "Other / no assertion" and is not treated as
openly licensed; no code or definitions were copied from it.

Discovery scans a range of Data Identifiers via UDS ReadDataByIdentifier
(0x22) and reports which ones the ECU answers.  On a virtual/unresponsive
connector the result is an empty list (honest).
"""
from __future__ import annotations

from collections.abc import Iterable


def discover_dids(uds, start: int, end: int) -> list[int]:
    """Return the list of DIDs in [start, end] that the ECU responds to."""
    found: list[int] = []
    for did in range(start, end + 1):
        try:
            uds.send(bytes([0x22, (did >> 8) & 0xFF, did & 0xFF]))
            resp = uds.recv(uds.timeout if hasattr(uds, "timeout") else 1.0)
        except Exception:  # noqa: BLE001, S112
            continue
        if resp and len(resp) >= 2 and resp[0] == 0x62:
            found.append(did)
    return found


def discover_pids(uds, pids: Iterable[int]) -> list[int]:
    """Return the subset of OBD-II PIDs (Mode 01) that the ECU answers."""
    found: list[int] = []
    for pid in pids:
        try:
            uds.send(bytes([0x01, pid & 0xFF]))
            resp = uds.recv(uds.timeout if hasattr(uds, "timeout") else 1.0)
        except Exception:  # noqa: BLE001, S112
            continue
        if resp and len(resp) >= 2 and resp[0] == 0x41:
            found.append(pid)
    return found
