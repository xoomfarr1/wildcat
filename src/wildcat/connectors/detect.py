"""Auto-detection of connected diagnostic cables / serial adapters.

Wraps :mod:`serial.tools.list_ports` so the GUI can discover what is
plugged in (FTDI K+DCAN, VAG-COM, ELM327, USB-CAN bridges, ...) without
the user having to type a COM port.  Detection is best-effort and never
raises: an empty list is returned when pyserial is unavailable or no
ports are present.
"""
from __future__ import annotations

from dataclasses import dataclass

try:
    import serial.tools.list_ports as _list_ports
except ImportError:  # pragma: no cover - pyserial missing
    _list_ports = None  # type: ignore[assignment]


@dataclass
class DetectedCable:
    """A discovered serial adapter."""

    port: str
    description: str
    vid: int | None = None
    pid: int | None = None
    suggested_connector: str = "K-Line (BMW/VAG)"


_FTDI_VID = 0x0403


def _suggest(description: str, vid: int | None, pid: int | None) -> str:
    desc = (description or "").lower()
    if "elm" in desc or "obd" in desc:
        return "ELM327 OBD-II"
    if "ftdi" in desc or vid == _FTDI_VID:
        # BMW K+DCAN / VAG-COM cables are FTDI-based serial adapters.
        if any(k in desc for k in ("k+dcan", "k+can", "vag", "bmw", "vcds")):
            return "K-Line (BMW/VAG)"
        # Generic FTDI serial (could be ELM327 or slcan) -> default to K-Line
        return "K-Line (BMW/VAG)"
    if "can" in desc:
        return "USB-CAN"
    return "K-Line (BMW/VAG)"


def detect_cables() -> list[DetectedCable]:
    """Return a list of serial adapters currently plugged in."""
    if _list_ports is None:
        return []
    out: list[DetectedCable] = []
    try:
        for p in _list_ports.comports():
            out.append(
                DetectedCable(
                    port=p.device,
                    description=p.description or p.device,
                    vid=getattr(p, "vid", None),
                    pid=getattr(p, "pid", None),
                    suggested_connector=_suggest(p.description or "", getattr(p, "vid", None), getattr(p, "pid", None)),
                )
            )
    except OSError:  # pragma: no cover - defensive
        return []
    return out


def detect_summary() -> str:
    """Human-readable summary of detected cables."""
    cables = detect_cables()
    if not cables:
        return "No serial adapters detected."
    lines = [f"{c.port}: {c.description} -> {c.suggested_connector}" for c in cables]
    return "\n".join(lines)
