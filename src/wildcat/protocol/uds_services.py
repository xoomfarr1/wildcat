"""UDS (ISO 14229) service identifiers and helper constants.

Adapted from the Xentry-Portal reference collection (Caring Caribou).
Kept dependency-free so it can be imported anywhere in Wildcat.
"""
from __future__ import annotations

# Service IDs (request SID).  Positive responses are SID + 0x40.
SERVICE_NAMES: dict[int, str] = {
    0x10: "DiagnosticSessionControl",
    0x11: "ECUReset",
    0x14: "ClearDiagnosticInformation",
    0x19: "ReadDTCInformation",
    0x20: "ReturnToNormal",
    0x22: "ReadDataByIdentifier",
    0x23: "ReadMemoryByAddress",
    0x24: "ReadScalingDataByIdentifier",
    0x27: "SecurityAccess",
    0x28: "CommunicationControl",
    0x29: "Authentication",
    0x2A: "ReadDataByPeriodicIdentifier",
    0x2C: "DynamicallyDefineDataIdentifier",
    0x2D: "DefinePIDByMemoryAddress",
    0x2E: "WriteDataByIdentifier",
    0x2F: "InputOutputControlByIdentifier",
    0x31: "RoutineControl",
    0x34: "RequestDownload",
    0x35: "RequestUpload",
    0x36: "TransferData",
    0x37: "RequestTransferExit",
    0x38: "RequestFileTransfer",
    0x3D: "WriteMemoryByAddress",
    0x3E: "TesterPresent",
    0x7F: "NegativeResponse",
    0x83: "AccessTimingParameter",
}


def service_name(sid: int) -> str:
    """Return a human-readable name for a UDS service id."""
    return SERVICE_NAMES.get(sid & 0x7F, f"Unknown(0x{sid:02X})")


# UDS diagnostic session types
SESSION_DEFAULT = 0x01
SESSION_PROGRAMMING = 0x02
SESSION_EXTENDED = 0x03

# TesterPresent (0x3E) sub-function
TESTER_PRESENT_RESPONSE_REQUIRED = 0x00
TESTER_PRESENT_NO_RESPONSE = 0x80

# ReadDTCInformation (0x19) sub-functions
RDI_REPORT_NUMBER_OF_DTC_BY_STATUS_MASK = 0x01
RDI_REPORT_DTC_BY_STATUS_MASK = 0x02
RDI_REPORT_DTC_SNAPSHOT_IDENTIFICATION = 0x03
RDI_REPORT_DTC_SNAPSHOT_RECORD_BY_DTC_NUMBER = 0x04
RDI_REPORT_DTC_EXTENDED_DATA_RECORD_BY_DTC_NUMBER = 0x06
RDI_REPORT_SUPPORTED_DTC = 0x0A
RDI_REPORT_FIRST_TEST_FAILED_DTC = 0x0B
RDI_REPORT_FIRST_CONFIRMED_DTC = 0x0C
RDI_REPORT_MOST_RECENT_TEST_FAILED_DTC = 0x0D
RDI_REPORT_MOST_RECENT_CONFIRMED_DTC = 0x0E
RDI_REPORT_MIRROR_MEMORY_DTC_BY_STATUS_MASK = 0x0F
RDI_REPORT_MIRROR_MEMORY_DTC_EXTENDED_DATA_RECORD = 0x10
RDI_REPORT_NUMBER_OF_MIRROR_MEMORY_DTC_BY_STATUS_MASK = 0x11
RDI_REPORT_NUMBER_OF_EMISSIONS_OBD_DTC_BY_STATUS_MASK = 0x12
RDI_REPORT_EMISSIONS_OBD_DTC_BY_STATUS_MASK = 0x13
RDI_REPORT_DTC_FAULT_COUNTER = 0x14
RDI_REPORT_DTC_WITH_PERMANENT_STATUS = 0x15


def dtc_status_name(mask: int) -> str:
    """Decode a DTC status byte into a comma-joined list of active bits."""
    bits = {
        0x01: "testFailed",
        0x02: "testFailedThisOperationCycle",
        0x04: "pendingDTC",
        0x08: "confirmedDTC",
        0x10: "testNotCompletedSinceLastClear",
        0x20: "testFailedSinceLastClear",
        0x40: "testNotCompletedThisOperationCycle",
        0x80: "warningIndicatorRequested",
    }
    return ",".join(name for bit, name in bits.items() if mask & bit) or "none"
