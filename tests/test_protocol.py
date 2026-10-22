"""Tests for the Wildcat protocol layer (CAN, KWP2000, J1850)."""

from __future__ import annotations

import pytest

from wildcat.connectors.base import Connector
from wildcat.protocol import (
    FC,
    FF,
    ISO_TP,
    PID_DATA,
    PID_STATUS1,
    SF,
    CANFrame,
    CANProtocol,
    KWP2000Frame,
    KWP2000Protocol,
    KWP2000TimeoutError,
)
from wildcat.protocol.can import (
    CF,
    FR,
    IsoTpProtocolError,
)
from wildcat.protocol.j1850 import J1850Encoder, J1850Error, J1850Frame, J1850Protocol


class FakeConnector(Connector):
    """In-memory connector for deterministic protocol tests."""

    def __init__(self, *, received: bytes = b"", sent: bytes = b"") -> None:
        self._send_buf: list[bytes] = []
        self._recv_buf = bytearray(received)
        self.sent: bytes = sent
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def send(self, data: bytes) -> None:
        self._send_buf.append(bytes(data))

    def recv(self, timeout: float = 1.0) -> bytes:
        if self._recv_buf:
            chunk = bytes(self._recv_buf[:1])
            self._recv_buf = self._recv_buf[1:]
            return chunk
        return b""

    def is_open(self) -> bool:
        return self.opened

    def reset(self) -> None:
        pass

    @property
    def sent_data(self) -> bytes:
        return b"".join(self._send_buf)


# ---------------------------------------------------------------------------
# CAN frame model
# ---------------------------------------------------------------------------


def test_frame_roundtrip_standard() -> None:
    frame = CANFrame(arbitration_id=0x123, data=b"\xAA\xBB", is_extended=False)
    raw = frame.to_bytes()
    assert raw[0] == 0x00
    parsed = CANFrame.from_bytes(raw)
    assert parsed.arbitration_id == frame.arbitration_id
    assert parsed.data == frame.data
    assert parsed.is_extended is False


def test_frame_roundtrip_extended() -> None:
    frame = CANFrame(arbitration_id=0x1234567, data=b"hi", is_extended=True)
    assert CANFrame.from_bytes(frame.to_bytes()) == frame


def test_frame_invalid_id() -> None:
    with pytest.raises(ValueError):
        CANFrame(arbitration_id=0x20000000, data=b"")


def test_frame_dlc_matches_payload() -> None:
    f = CANFrame(arbitration_id=0x1, data=b"\x01\x02", dlc=3)
    assert f.dlc == 2  # dlc auto-corrected to actual payload length


# ---------------------------------------------------------------------------
# ISO-TP transport layer
# ---------------------------------------------------------------------------


def test_single_frame() -> None:
    iso = ISO_TP()
    frames = iso.fragment(b"hello")
    assert len(frames) == 1
    assert frames[0][0] == SF
    # ISO 15765-2 single frame format: [SF, length, data...]
    assert frames[0][1] == len(b"hello")
    assert frames[0][2:] == b"hello"


def test_single_frame_boundary() -> None:
    iso = ISO_TP(max_payload=8)
    frames = iso.fragment(b"A" * 8)
    assert len(frames) == 1
    assert frames[0][0] == SF
    assert frames[0][1] == 8
    assert frames[0][2:] == b"A" * 8


def test_multi_frame_fragment_and_reassemble() -> None:
    iso = ISO_TP()
    data = b"abcdef" * 3  # 18 bytes
    frames = iso.fragment(data)
    assert len(frames) == 1 + 3  # 1 FF + 3 CF
    cfs = [f for f in frames if f[0] == CF]
    # Consecutive frames: [CF, seq_hi, seq_lo, length, data...]
    # seq is 2 bytes big-endian at [1:3]
    expected_seqs = [(i << 8).to_bytes(2, "big") for i in range(3)]
    for cf, exp_seq in zip(cfs, expected_seqs):
        assert cf[1:3] == exp_seq, f"expected seq {exp_seq}, got {cf[1:3]}"
    recovered = b""
    for f in frames:
        recovered += iso.receive(f)
    assert recovered == data


def test_reassemble_missing_last_cf() -> None:
    iso = ISO_TP()
    partial = [bytes([FF, 0, 2, 0]), bytes([CF, 0, 0, 2, 0x01, 0x02])]
    # FF says 2 consecutive frames, but only 1 CF provided -> protocol error
    with pytest.raises(IsoTpProtocolError):
        for f in partial:
            iso.receive(f)


def test_flow_control_auto_answer() -> None:
    connector = FakeConnector()
    iso = ISO_TP(auto_flow_control=True)
    ff = bytes([FF, 0, 2, 0])
    cf1 = bytes([CF, 0, 0, 2, 0x01, 0x02])
    fc = bytes([FC, 0x00, 0x00])
    connector._recv_buf.extend(ff)
    connector._recv_buf.extend(cf1)
    connector._recv_buf.extend(fc)
    iso.receive(bytes(ff))
    iso.receive(bytes(cf1))
    iso.receive(bytes(fc))
    assert len(connector._send_buf) == 1
    assert connector._send_buf[0] == bytes([FR, 0x00])


# ---------------------------------------------------------------------------
# CAN protocol (ISO 15765-4)
# ---------------------------------------------------------------------------


def test_can_protocol_send_frame() -> None:
    connector = FakeConnector()
    proto = CANProtocol(connector)
    frame = CANFrame(arbitration_id=0x7DF, data=b"test", is_extended=False)
    proto.send(frame)
    assert len(connector._send_buf) == 1
    assert connector._send_buf[0] == frame.to_bytes()


def test_can_protocol_receive_frame() -> None:
    data = bytes([0x00, 0x11, 0x00, 0x00, 0x08, 0x41, 0x42, 0x43, 0x44])
    connector = FakeConnector(received=data)
    proto = CANProtocol(connector)
    frame = proto.recv()
    assert frame.arbitration_id == 0x123
    assert frame.data == b"ABCD"
    assert frame.is_extended is False


def test_can_protocol_iso_tp_fragments() -> None:
    connector = FakeConnector()
    proto = CANProtocol(connector, timeout=0.01)
    proto.send(b"The quick brown fox jumps over the lazy dog")
    frames = [tuple(c) for c in connector._send_buf]
    assert any(f[0] == FF for f in frames)
    assert sum(1 for f in frames if f[0] == CF) >= 2


# ---------------------------------------------------------------------------
# KWP2000 protocol (ISO 9141-2)
# ---------------------------------------------------------------------------


def test_kwp2000_frame_build_and_parse() -> None:
    frame = KWP2000Frame(frame_type=PID_DATA, data=b"\x02\x01\x00")
    raw = frame.to_bytes()
    assert raw[0] == PID_DATA
    assert raw[1] == 0x32  # even parity of 0x33
    assert KWP2000Frame.parse(raw) == frame


def test_kwp2000_frame_bad_checksum() -> None:
    frame = KWP2000Frame(frame_type=PID_DATA, data=b"X")
    raw = bytearray(frame.to_bytes())
    raw[-1] ^= 0xFF  # corrupt checksum
    with pytest.raises(KWP2000TimeoutError):
        KWP2000Frame.parse(bytes(raw))  # type: ignore[arg-type]


def test_kwp2000_proto_roundtrip() -> None:
    connector = FakeConnector()
    proto = KWP2000Protocol(connector)
    frame = KWP2000Frame(frame_type=PID_DATA, data=b"\x02\x01\x00")
    proto.send(frame)
    assert len(connector._send_buf) == 1
    assert KWP2000Frame.parse(connector._send_buf[0]).data == b"\x02\x01\x00"


def test_kwp2000_status_frame() -> None:
    frame = KWP2000Frame(frame_type=PID_STATUS1, data=bytes([0x00]))
    raw = frame.to_bytes()
    assert raw[0] == PID_STATUS1
    assert KWP2000Frame.parse(raw).data[0] == 0x00


# ---------------------------------------------------------------------------
# J1850 protocol (VPW / PWM)
# ---------------------------------------------------------------------------


def test_j1850_frame_pwm_roundtrip() -> None:
    frame = J1850Frame(arbitration_id=0x123, data=b"\x01\x02\x03", mode="pwm")
    parsed = J1850Frame.from_bytes(frame.to_bytes())
    assert parsed.data == frame.data
    assert parsed.mode == frame.mode


def test_j1850_encoder_pwm() -> None:
    encoded = J1850Encoder.encode_pwm(b"\x01")
    assert len(encoded) == 16
    assert J1850Encoder.decode_pwm(encoded) == b"\x01"


def test_j1850_encoder_vpw() -> None:
    encoded = J1850Encoder.encode_vpw(b"\x01\x02")
    assert len(encoded) == 16
    assert J1850Encoder.decode_vpw(encoded) == b"\x01\x02"


def test_j1850_protocol_send_recv() -> None:
    data = bytes([0x01, 0x01, 0x02, 0x03])
    connector = FakeConnector(received=data)
    proto = J1850Protocol(connector, mode="pwm")
    frame = J1850Frame(arbitration_id=0x123, data=b"\x01\x02\x03", mode="pwm")
    proto.send(frame)
    assert len(connector._send_buf) == 1
    assert proto.recv().data == b"\x01\x02\x03"


def test_j1850_protocol_bitstream_roundtrip() -> None:
    encoded = J1850Encoder.encode_pwm(b"\x01\x02")
    connector = FakeConnector(received=bytes(encoded))
    proto = J1850Protocol(connector, mode="pwm")
    proto.send_bitstream(bytes(encoded))
    assert proto.recv_bitstream() == b"\x01\x02"


def test_j1850_invalid_mode() -> None:
    connector = FakeConnector()
    with pytest.raises(J1850Error):
        J1850Protocol(connector, mode="unknown")  # type: ignore[arg-type]