"""Protocol layer — command/response languages for vehicle diagnostics."""

from wildcat.protocol.can import CANFrame, CANError

__all__ = ["CANFrame", "CANError"]
