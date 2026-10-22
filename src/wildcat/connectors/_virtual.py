"""Shared in-memory "virtual adapter" used by every connector for testing.

A virtual adapter is a tiny echo pipe that stands in for a physical device so
the driver code (open / send / recv / reset / close) can be exercised and unit
tested without any real hardware or vendor DLLs.

Design
------
Two FIFO queues model the two directions of a wire:

* ``_tx``  - bytes leaving the driver toward the hardware (written by ``send``).
* ``_rx``  - bytes arriving from the hardware (consumed by ``recv``).

By default the pipe echoes everything written to ``send`` back into ``_rx``,
which makes a one-liner test look like a hardware round trip.  The echo can be
disabled, and a test can inject arbitrary data into ``_rx`` at any time with
``inject()`` to simulate an unsolicited hardware response.

Thread safety
-------------
All queue operations and counters are protected by a lock so a virtual adapter
may be driven from the same threads the real driver would be used from.

Exceptions
----------
``send`` / ``recv`` / ``inject`` raise :class:`ConnectorNotOpenError` if the
adapter has not been opened, mirroring the abstract base class contract.
"""

from __future__ import annotations

import queue
import threading

from wildcat.connectors.base import ConnectorNotOpenError


class VirtualConnection:
    """In-memory adapter pipe (producer/consumer channel)."""

    def __init__(self, *, name: str = "virtual", echo: bool = True) -> None:
        self.name = name
        self.echo = echo
        self._lock = threading.Lock()
        self._tx: queue.Queue[bytes] = queue.Queue()
        self._rx: queue.Queue[bytes] = queue.Queue()
        self._opened = False
        self.bytes_sent = 0
        self.bytes_received = 0
        self.firmware_version = "test"
        self.adapter = "virtual"

    # ------------------------------------------------------------------ lifecycle

    def open(self) -> None:
        """Open the virtual adapter (no hardware involved)."""
        with self._lock:
            self._opened = True
            self.bytes_sent = 0
            self.bytes_received = 0

    def close(self) -> None:
        """Close the virtual adapter."""
        with self._lock:
            self._opened = False

    # --------------------------------------------------------------- I/O core

    def _write(self, data: bytes) -> None:
        """Put bytes into the transmit queue and echo them into the receive
        queue unless echo mode is disabled."""
        data = bytes(data)
        if not self._opened:
            raise ConnectorNotOpenError("virtual adapter is not open")
        self._tx.put(data)
        if self.echo:
            self._rx.put(data)

    def _read(self, timeout: float = 1.0) -> bytes:
        """Pull a response from the receive queue; ``b''`` on timeout."""
        if not self._opened:
            raise ConnectorNotOpenError("virtual adapter is not open")
        try:
            data = self._rx.get(timeout=timeout)
        except queue.Empty:
            return b""
        with self._lock:
            self.bytes_received += len(data)
        return data

    # ----------------------------------------------------------------- public

    def send(self, data: bytes) -> None:
        """Write bytes toward the hardware (echoed back so tests see them)."""
        self._write(data)
        with self._lock:
            self.bytes_sent += len(data)

    def recv(self, timeout: float = 1.0) -> bytes:
        """Read bytes arriving from the hardware."""
        return self._read(timeout)

    def inject(self, data: bytes) -> None:
        """Push bytes into the receive queue, simulating a hardware response.

        Use this to test that the driver can read responses without first
        writing any request.
        """
        self._write(data)
        # ``_write`` already counted the bytes as "sent"; only count what the
        # test injected as received when the adapter is echo-disabled so that
        # the two counters stay meaningful in either configuration.
        with self._lock:
            if not self.echo:
                self.bytes_received += len(data)

    @property
    def is_open(self) -> bool:
        return self._opened

    def reset(self) -> None:
        """Reset the virtual adapter: keep the pipe but flush pending data."""
        with self._lock:
            self._tx.queue.clear()
            self._rx.queue.clear()
