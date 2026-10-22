from wildcat.core.uds import UDSService, VirtualUDSConnector
from wildcat.programming import FlashUpdater, SecurityAccess


def test_security_access_roundtrip():
    conn = VirtualUDSConnector()
    conn.open()
    uds = UDSService(conn, ecu_id=0x12, security_access=True)
    # inject seed response: SID 0x27 + length + 4 bytes
    conn.inject(bytes([0x27, 4, 1, 2, 3, 4]))
    sa = SecurityAccess(uds)
    seed = sa.request_seed(b"\x00\x00\x00\x00")
    assert seed == bytes([1, 2, 3, 4])


def test_flash_updater():
    fu = FlashUpdater()
    assert fu.flash(b"abc") is True
    assert fu.calibrate(b"def") is True
