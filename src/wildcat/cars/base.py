"""Car model abstraction.

Each supported vehicle (Mercedes C300, BMW, Ford, VW/Audi) implements this base to
expose VIN handling, CAN identifier spaces, and PID decoding tables.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class DTC:
    """A diagnostic trouble code."""

    code: str
    description: str
    severity: str
    is_temporary: bool = False


@dataclass(frozen=True)
class LiveData:
    """A live data point read from the vehicle."""

    name: str
    value: float
    unit: str


class CarModel(ABC):
    """Abstract base for a vehicle brand / model platform."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable model name."""

    @property
    @abstractmethod
    def language(self) -> str:
        """Requested vehicle language (e.g. 'EN', 'DE')."""

    @abstractmethod
    def set_language(self, language: str) -> None:
        """Configure the vehicle language."""

    @abstractmethod
    def get_dtc_reader(self) -> Iterable[DTC]:
        """Read all currently stored fault codes."""

    @abstractmethod
    def get_live_data(self, keys: Optional[Iterable[str]] = None) -> List[LiveData]:
        """Read live data from the vehicle."""

    @abstractmethod
    def clear_dtc(self) -> None:
        """Clear stored fault codes."""

    @abstractmethod
    def security_access(self) -> bool:
        """Check whether the vehicle requires security access."""

    @abstractmethod
    def send_seed(self, seed: bytes) -> bytes:
        """Ask the vehicle for a security seed (programming)."""

    @abstractmethod
    def send_key(self, key: bytes) -> bytes:
        """Send a seed response to the vehicle (programming)."""

    @abstractmethod
    def ecu_id(self) -> int:
        """Return the target ECU identifier."""
