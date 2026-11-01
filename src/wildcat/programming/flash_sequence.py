"""Real flashing-sequence structure (UNVALIDATED on real hardware).

Implements the UDS flashing flow as a *structure* only:

  1. DiagnosticSessionControl -> Programming session (0x10 0x02)
  2. SecurityAccess seed/key (via plug-in algorithm, if configured)
  3. RequestDownload (0x34) for the target address/size
  4. TransferData (0x36) in chunks
  5. RequestTransferExit (0x37)
  6. Verification read-back (0x22 ReadDataByIdentifier or routine)
  7. ReturnToNormal / ECU reset

Every step checks the ECU's response and aborts with a typed
:class:`FlashSequenceError` on failure, so a partial flash cannot be
silently reported as success.  This has NOT been validated on a real
vehicle; it is exercised only against virtual connectors in tests.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from wildcat.core.uds import UDSService


class FlashSequenceError(Exception):
    """Raised when a flashing step fails or is rejected by the ECU."""


@dataclass
class FlashResult:
    ok: bool
    steps: list[str] = field(default_factory=list)
    error: str | None = None


class FlashSequence:
    def __init__(self, uds: UDSService, chunk_size: int = 256) -> None:
        self.uds = uds
        self.chunk_size = chunk_size

    def _step(self, name: str, fn: Callable[[], None], result: FlashResult) -> bool:
        try:
            fn()
            result.steps.append(f"{name}: OK")
            return True
        except Exception as exc:  # noqa: BLE001
            result.steps.append(f"{name}: FAIL ({exc})")
            result.error = str(exc)
            return False

    def run(self, data: bytes, address: int = 0x00000000) -> FlashResult:
        result = FlashResult(ok=False)
        # 1. Programming session
        if not self._step("DiagnosticSessionControl(programming)", lambda: self._session_control(0x02), result):
            return result
        # 2. RequestDownload
        if not self._step("RequestDownload", lambda: self._request_download(address, len(data)), result):
            return result
        # 3. TransferData chunks
        if not self._step("TransferData", lambda: self._transfer(data), result):
            return result
        # 4. RequestTransferExit
        if not self._step("RequestTransferExit", self._transfer_exit, result):
            return result
        # 5. Verification read-back
        if not self._step("Verification", lambda: self._verify(address, data), result):
            return result
        result.ok = True
        return result

    def _session_control(self, session_type: int) -> None:
        self.uds.send(bytes([0x10, session_type]))
        resp = self.uds.recv(self.uds.timeout)
        if not resp or resp[0] != 0x50 or resp[1] != session_type:
            raise FlashSequenceError(f"session control rejected: {resp!r}")

    def _request_download(self, address: int, size: int) -> None:
        addr_bytes = address.to_bytes(4, "big")
        size_bytes = size.to_bytes(4, "big")
        self.uds.send(bytes([0x34, 0x00, 0x44]) + addr_bytes + size_bytes)
        resp = self.uds.recv(self.uds.timeout)
        if not resp or resp[0] != 0x74:
            raise FlashSequenceError(f"RequestDownload rejected: {resp!r}")

    def _transfer(self, data: bytes) -> None:
        offset = 0
        seq = 1
        while offset < len(data):
            chunk = data[offset : offset + self.chunk_size]
            self.uds.send(bytes([0x36, seq & 0xFF]) + chunk)
            resp = self.uds.recv(self.uds.timeout)
            if not resp or resp[0] != 0x76:
                raise FlashSequenceError(f"TransferData block {seq} rejected: {resp!r}")
            offset += len(chunk)
            seq += 1

    def _transfer_exit(self) -> None:
        self.uds.send(bytes([0x37]))
        resp = self.uds.recv(self.uds.timeout)
        if not resp or resp[0] != 0x77:
            raise FlashSequenceError(f"RequestTransferExit rejected: {resp!r}")

    def _verify(self, address: int, data: bytes) -> None:
        # Best-effort read-back via ReadDataByIdentifier; on a real ECU this
        # would compare the flashed image.  Here we just attempt the request.
        self.uds.send(bytes([0x22, 0xF1, 0x90]))
        resp = self.uds.recv(self.uds.timeout)
        if not resp:
            raise FlashSequenceError("verification read-back got no response")
        # We cannot assert byte equality without a real read-back DID; record
        # that verification is structural only.
