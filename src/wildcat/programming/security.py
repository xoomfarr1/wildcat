"""Security access helpers for programming."""

from __future__ import annotations

from wildcat.core.uds import SecurityAccessError, UDSService


class SecurityAccess:
    def __init__(self, uds: UDSService) -> None:
        self.uds = uds

    def request_seed(self, key_id: bytes = b"\x00\x00\x00\x00") -> bytes:
        return self.uds.send_seed(key_id)

    def send_key(self, key: bytes) -> bytes:
        return self.uds.send_key(key)

    def unlock(self, key: bytes) -> bool:
        try:
            self.uds.send_key(key)
            return True
        except SecurityAccessError:
            return False
