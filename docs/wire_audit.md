# Wildcat UDS/K-line Wire Audit

Consolidated list of unvalidated wire-protocol assumptions. Each entry
states the assumption, where it lives, why it is unvalidated, and the
exact bytes / real-vehicle log needed to validate it. No behavior changes
are proposed; the 0x27/0x29 convention is deliberately left untouched
pending a spec or a real-vehicle log.

## 1. K-line fast init (25 ms break + 0xC1)

- Location: `src/wildcat/protocol/kline.py::fast_init`
- Assumption: 25 ms low break followed by `0xC1` at normal baud (10400);
  ECU replies with sync `0x55` + 2 key bytes; only `resp[0] == 0x55` is
  checked (key bytes ignored). Break polarity (`setRTS(True)` = low) and
  duration are unvalidated.
- Validate with: raw serial capture of a real fast-init exchange showing
  tester TX `break(25ms) 0xC1`, ECU RX `55 XX XX`, then tester's
  `0x81` (or equivalent) key-byte handling. Need full 3-byte response
  bytes and the inverted key-byte check per ISO 14230-2.

## 2. K-line slow (5-baud) init (0x33)

- Location: `src/wildcat/protocol/kline.py::slow_init`
- Assumption: 0x33 sent one bit at a time at 5 baud via RTS toggling
  (`setRTS(not bit)`); ECU replies `0x55 0x08 0x08 0xF7`; only sync
  byte checked. Bit ordering (LSB-first vs MSB-first), start/stop bits,
  and RTS polarity unvalidated.
- Validate with: logic-analyzer/serial capture of a real 5-baud init
  showing tester line transitions and ECU reply bytes
  `55 08 08 F7` (and their inverses), including inter-byte timing.

## 3. TesterPresent (0x3E) framing

- Location: `src/wildcat/protocol/kline.py::KLineSession.tester_present`
- Assumption: request `3E 00` (response required) / `3E 80` (no
  response); positive response `0x7E`. No checksum / length / address
  header handling (raw byte pipe).
- Validate with: captured K-line frame exchange for both sub-functions
  showing full frame bytes including header (target/source/length) and
  checksum, and ECU response `7E 00` (or no response for 0x80).

## 4. KWP2000 ReadDTC (0x18) parsing

- Location: `src/wildcat/protocol/kline.py::KLineSession.read_dtcs`
- Assumption: request `18 00 FF`; response starts `0x58`; payload is
  pairs of DTC bytes at offset 2; codes formatted `P{hi:02X}{lo:02X}`.
  Real KWP DTC layout and status bytes unvalidated; virtual mode returns
  empty.
- Validate with: real ECU response to `18 00 FF` (full frame bytes) to
  confirm service echo, DTC byte order, status byte, and termination.

## 5. UDS ReadDTCInformation (0x19 0x02) parsing

- Location: `src/wildcat/protocol/kline.py::KLineSession.read_dtcs_uds`
- Assumption: response `59 02 <statusAvailabilityMask>`, then 4-byte
  records (3-byte DTC + status); DTC type from bits 22-23 of 24-bit
  word; code formatted from low 16 bits. Termination condition
  `i + 3 < len(resp)` may drop a trailing record.
- Validate with: real ECU response bytes to `19 02 FF` showing
  statusAvailabilityMask and at least two DTC records, including a
  record whose DTC type bits exercise each of `P/C/B/U`.

## 6. UDS security access convention (0x27 / 0x29)

- Location: `src/wildcat/core/uds.py::UDSService.send_seed`,
  `send_key`
- Assumption (non-standard, must NOT be changed without spec/log): seed
  request uses SID `0x27` with `PS = len(seed)` and trailing key id;
  positive response echoed SID `0x27`, 4-byte seed at offset 2. Key
  response uses SID `0x29` (not a standard UDS service) with `PS = len(key)`;
  positive response echoed SID `0x29`, 4-byte session key at offset 2.
  Response-length check `>= 6` and fixed 4-byte value unvalidated.
- Validate with: a real-vehicle (or OEM diagnostic tool) log capturing
  the full seed/key exchange: request bytes, response bytes, and the
  resulting security level, for both successful and locked (NRC) cases.

## 7. ReadDTCByStatusMask (0x01) request/response

- Location: `src/wildcat/core/uds.py::UDSService.read_dtc`,
  `_parse_dtcs`
- Assumption: request `01 01 00 01` (status mask 0x0001); positive
  response SID `0x21`; each record 7 bytes with present flag 0x00;
  2-byte DTC at offset 1; unknown codes get empty description.
- Validate with: real ECU response to `01 01 00 01` showing the exact
  record layout, present-flag values, and a sample of DTC codes.

## 8. ReadDataByIdentifier (0x21) live data

- Location: `src/wildcat/core/uds.py::UDSService.read_live_data`,
  `_parse_live_data`
- Assumption: request `21 01 <2-byte keys>`; positive response SID `0x21`;
  variable-length records with present flag, name, echoed 2-byte id,
  4-byte big-endian float value, unit. Note: standard UDS RDBI is
  SID 0x22 (positive 0x62), so 0x21 is project-specific.
- Validate with: real ECU response showing at least one record with
  known identifier, value, and unit to confirm byte layout.

## 9. ClearDTCs (0x04)

- Location: `src/wildcat/core/uds.py::UDSService.clear_dtc`
- Assumption: request `04 01`; positive response `0x24`.
- Validate with: real ECU request/response bytes for a clear operation,
  including NRC cases.

## 10. ReadMemoryByAddress (0x23)

- Location: `src/wildcat/core/uds.py::UDSService.read_memory_by_address`
- Assumption: request `23 41 <4-byte addr> <1-byte size>`; positive
  response `0x63`; payload at offset 2. Address/size format identifier
  `0x41` (4-byte address / 1-byte size) unvalidated.
- Validate with: real ECU response to a known address/size, or an OEM
  tool log, to confirm format identifier and returned bytes.

## 11. DTC status byte decoding

- Location: `src/wildcat/protocol/uds_services.py::dtc_status_name`
- Assumption: ISO 14229 status-bit mapping (testFailed etc.) matches the
  target ECUs; no validation against real DTC status bytes.
- Validate with: real DTC responses including status bytes with multiple
  bits set.

## 12. K-line frame layer (none)

- Location: `src/wildcat/protocol/kline.py` (whole module)
- Assumption: raw byte pipe with no framing, addressing, length, or
  checksum handling. Real K-line (ISO 9141-2 / ISO 14230) requires
  header + length + checksum; the current code cannot talk to a real ECU
  without a framing layer.
- Validate with: a captured full K-line session (init + at least one
  service request/response) including all framing bytes, to design the
  framing layer.
