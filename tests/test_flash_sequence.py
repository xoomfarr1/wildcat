from wildcat.core.uds import UDSService, VirtualUDSConnector
from wildcat.programming.flash_sequence import FlashSequence


def test_flash_sequence_fails_on_virtual_connector():
    conn = VirtualUDSConnector()
    conn.open()
    uds = UDSService(conn, ecu_id=0x12, security_access=True)
    seq = FlashSequence(uds, chunk_size=4)
    result = seq.run(b"abcd" * 4, address=0x1000)
    # Virtual connector echoes nothing useful -> must not report success.
    assert result.ok is False
    assert result.error is not None
    assert len(result.steps) >= 1


def test_flash_sequence_empty_payload_fails():
    conn = VirtualUDSConnector()
    conn.open()
    uds = UDSService(conn, ecu_id=0x12, security_access=True)
    seq = FlashSequence(uds, chunk_size=4)
    result = seq.run(b"", address=0x1000)
    assert result.ok is False
    assert result.error == "no data to flash"


def test_flash_sequence_records_step_names():
    conn = VirtualUDSConnector()
    conn.open()
    uds = UDSService(conn, ecu_id=0x12, security_access=True)
    seq = FlashSequence(uds, chunk_size=4)
    result = seq.run(b"abcd")
    joined = " | ".join(result.steps)
    assert "DiagnosticSessionControl" in joined
