"""Shared decoding helpers for the car model implementations.

All four car models reuse this helper to decode raw CAN signal values into
physical units (rpm, °C, kPa, V, ...). Keeping the math in one place lets
each vehicle stay a data-only table while the decoding stays consistent.
"""

from __future__ import annotations


def decode_signal(sig: dict[str, object], raw: int) -> float:
    """Decode a raw CAN signal into a physical value.

    Applies ``scale`` (default 1.0) and ``offset`` (default 0.0) per the
    signal's CAN definition. Unknown keys are ignored.

    Args:
        sig: Signal definition dictionary (see the car model modules).
        raw: Raw unsigned integer read from the CAN bus.

    Returns:
        The decoded physical value.
    """
    scale = float(sig.get("scale", 1.0))
    offset = float(sig.get("offset", 0.0))
    return raw * scale + offset
