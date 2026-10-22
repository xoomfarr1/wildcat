"""Vehicle / ECU identification.

This module wraps the low-level UDS service layer and turns a raw connector +
car model into a structured ECU identifier.  It is the entry point the
application layer uses to answer "which vehicle is on the bus and which ECU
does the session talk to?"

Design
------
The identification flow is deliberately thin:

1. Ask the car model for the target ECU identifier (``car.ecu_id()``).
2. Look up the vehicle name and CAN address from the VIN/ECU registry.
3. Send a UDS ``ReadDataByIdentifier`` (service 0x10) request for that
   identifier and read the identification payload.
4. Decode the payload with :func:`parse_ecu_response` into a plain dict, then
   assemble the :class:`ECUIdentifier` dataclass.

``ECUIdentifier`` is a frozen dataclass so it can be stored in the session and
compared by value without worrying about accidental mutation.
"""
from __future__ import annotations

from dataclasses import dataclass

from wildcat.core.uds import ECUIdentificationError, UDSService

__all__ = [
    "ECUIdentifier",
    "VehicleIdentification",
    "parse_ecu_response",
]

#: VIN / model -> ECU identification metadata.  The keys are human-readable
#: model names (the same strings returned by :class:`CarModel.name`) so that
#: ``VehicleIdentification.identify`` can map a connected car to the registry
#: entry without needing the raw VIN string.
#
#: The *address* field is the CAN/SBC node address the target ECU presents on
#: the bus (this drives the session's CAN identifier spaces).  The *ecu_id*
#: field is the identifier passed to UDS service 0x10 in the identification
#: request; it is provided by the car model's :meth:`CarModel.ecu_id` and is
#: kept here as a single source of truth for tooling/testing.
_VIN_ECU_REGISTRY: dict[str, dict[str, object]] = {
    # Mercedes C300 (W204 / M271) — powertrain ECU 0x12.
    "Mercedes C300 (2008)": {
        "name": "Mercedes C300 (W204)",
        "address": "0x12",
        "ecu_id": 0x12,
    },
    "Mercedes C200 (W203)": {
        "name": "Mercedes C200 (W203)",
        "address": "0x12",
        "ecu_id": 0x12,
    },
    # BMW E90 / F30 (3 Series) — powertrain ECU 0x21.
    "BMW E90 (320i)": {
        "name": "BMW E90 (320i)",
        "address": "0x21",
        "ecu_id": 0x21,
    },
    "BMW F30 (320i)": {
        "name": "BMW F30 (320i)",
        "address": "0x21",
        "ecu_id": 0x21,
    },
    # Ford Focus ST170 / Mondeo ST220 — OBD-II powertrain ECU 0x10.
    "Ford Focus ST170": {
        "name": "Ford Focus ST170",
        "address": "0x10",
        "ecu_id": 0x10,
    },
    "Ford Mondeo ST220": {
        "name": "Ford Mondeo ST220",
        "address": "0x22",
        "ecu_id": 0x22,
    },
    # VW / Audi Golf / Passat / A4 — powertrain ECU 0x12.
    "VW Golf (2010)": {
        "name": "VW Golf (VW/Audi)",
        "address": "0x12",
        "ecu_id": 0x12,
    },
    "VW Passat (2010)": {
        "name": "VW Passat (VW/Audi)",
        "address": "0x12",
        "ecu_id": 0x12,
    },
    "Audi A4 (2010)": {
        "name": "Audi A4 (VW/Audi)",
        "address": "0x12",
        "ecu_id": 0x12,
    },
}


@dataclass(frozen=True)
class ECUIdentifier:
    """A resolved ECU identifier for a connected vehicle.

    Attributes:
        vehicle_id: Numeric vehicle identifier parsed from the identification
            response payload (normally the VIN encoded as a 4-byte big-endian
            value).
        ecu_id: The target ECU identifier (the value of the identifier passed
            to UDS service 0x10).
        name: Human-readable name of the ECU / vehicle (from the registry and
            the identification response).
        address: CAN/SBC node address the target ECU presents on the bus.
    """

    vehicle_id: int
    ecu_id: int
    name: str
    address: str


def parse_ecu_response(response: bytes) -> dict:
    """Decode the ECU identification response payload into a plain dict.

    The ECU identification payload (the data portion of a UDS positive
    response to service 0x10) is an ASCII-friendly blob:
      - vehicle_id: 4 bytes, big-endian integer
      - ecu_id:     4 bytes, big-endian integer
      - name_len:   1 byte (length of the name that follows)
      - name:       name_len bytes, UTF-8

    Args:
        response: The payload bytes that follow the 3-byte UDS response header
            (``[0x50, 0x01] + data``).  Hand this the raw data slice, not the
            full frame.

    Returns:
        A dict with the keys ``vehicle_id``, ``ecu_id`` and ``name``.

    Raises:
        ECUIdentificationError: If the payload is too short or truncated.
    """
    if len(response) < 9:  # 4 + 4 + name_len
        raise ECUIdentificationError(
            f"payload too short for ECU identification: {len(response)} bytes"
        )
    vehicle_id = int.from_bytes(response[0:4], "big")
    ecu_id = int.from_bytes(response[4:8], "big")
    name_len = response[8]
    if len(response) < 9 + name_len:
        raise ECUIdentificationError(
            f"payload truncated: need {9 + name_len} bytes, got {len(response)}"
        )
    name = response[9 : 9 + name_len].decode("utf-8", errors="replace")
    return {"vehicle_id": vehicle_id, "ecu_id": ecu_id, "name": name}


class VehicleIdentification:
    """Turn a connector + car model into an :class:`ECUIdentifier`.

    Typical usage::

        ident = VehicleIdentification()
        ecu = ident.identify(connector, car)
        print(ecu.vehicle_id, ecu.name, ecu.address)
    """

    def __init__(self, *, registry: dict[str, dict[str, object]] | None = None) -> None:
        """Store the VIN/ECU registry.

        Args:
            registry: Optional override of the default VIN/ECU mapping.  Used by
                tests to inject known mappings without touching the class
                attribute.
        """
        self._registry = registry if registry is not None else dict(_VIN_ECU_REGISTRY)

    # ------------------------------------------------------------- identify -- #
    def identify(self, connector, car) -> ECUIdentifier:
        """Identify the vehicle and its target ECU on the bus.

        The flow:
          1. Ask the car for the target ECU identifier (``car.ecu_id()``).
          2. Look up the vehicle name and CAN address from the registry.
          3. Send a UDS ``ReadDataByIdentifier`` (0x10) request for that
             identifier and read the identification payload.
          4. Decode the payload with :func:`parse_ecu_response` and return an
             :class:`ECUIdentifier`.

        Args:
            connector: Open raw connector (must be open; ``UDSService`` will
                reject a closed one).
            car: Car model instance exposing :meth:`CarModel.ecu_id` and
                :attr:`CarModel.name`.

        Returns:
            An :class:`ECUIdentifier` for the connected vehicle.

        Raises:
            ECUIdentificationError: If the connector is closed, the car's ECU
                identifier is unknown, or the identification request fails.
        """
        ecu_id = car.ecu_id()

        model_name = car.name
        entry = self._registry.get(model_name)
        if entry is None:
            raise ECUIdentificationError(
                f"no VIN/ECU registry entry for car {model_name!r}"
            )

        # The registry's address is the CAN/SBC node the ECU presents.
        address = str(entry["address"])

        # Request the ECU identification data via UDS service 0x10
        # (ReadDataByIdentifier).  The identifier is the car's ecu_id(), cast
        # to a 2-byte value per the service's fixed-length parameter.
        service = UDSService(connector, timeout=1.0, ecu_id=ecu_id)
        request = bytes([0x10, 0x01]) + ecu_id.to_bytes(2, "big")
        connector.send(request)
        response = connector.recv(service.timeout)
        if len(response) < 2 or response[0] != 0x50:
            raise ECUIdentificationError(
                f"unexpected identification response: {response!r}"
            )

        decoded = parse_ecu_response(response[2:])
        name = str(decoded.get("name", entry["name"]))

        return ECUIdentifier(
            vehicle_id=decoded["vehicle_id"],
            ecu_id=ecu_id,
            name=name,
            address=address,
        )
