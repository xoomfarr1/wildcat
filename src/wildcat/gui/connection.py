"""Shared connection model bridging the desktop GUI to the Wildcat backend.

A single :class:`ConnectionModel` is created by the main window and handed to
every tab. It owns the live :class:`~wildcat.core.session.WildcatSession`
(connector + car) and exposes a Qt-signal-rich API so the tab views can react to
connect/disconnect and read data without importing the backend layers directly.

Why a model object
------------------
The three tab views (diagnostics, live data, programming) all need the same
session: the connected car, the fault codes, the live signals. Rather than each
view building its own session, they share this one model and subscribe to its
signals. This keeps a single source of truth for "what vehicle is on the bus".

Virtual-first
-------------
Every connector offered in the UI is built in its built-in *virtual* mode, so
the whole application runs against simulated data with NO physical adapter
attached:

* ``Virtual (simulated)`` uses ``connectors._virtual.VirtualConnection`` (an
  in-memory echo pipe).
* ``PT3G`` / ``J2534`` / ``ELM327`` / ``USB-CAN`` are constructed with
  ``virtual=True`` — their test/driver virtual adapters.

The diagnostic reads (``read_dtcs`` / ``read_live_data``) come straight from the
car model's data tables, so they are connector-agnostic: any open connector
works. Selecting a real connector whose virtual mode is unavailable surfaces a
clear message through the :attr:`error` signal instead of crashing.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from wildcat.cars.base import CarModel
from wildcat.cars.vin import CATALOG, decode_vin, find_vehicle_by_vin
from wildcat.connectors._virtual import VirtualConnection
from wildcat.connectors.elm327 import Elm327Connector
from wildcat.connectors.j2534 import J2534Connector
from wildcat.connectors.pt3g import PT3GConnector
from wildcat.connectors.serial import SerialConnector
from wildcat.connectors.usbcan import UsbCANConnector
from wildcat.core.exceptions import WildcatError
from wildcat.core.session import WildcatConfig, WildcatSession

#: Friendly connector labels shown in the UI, in selection order.
CONNECTOR_LABELS: tuple[str, ...] = (
    "Virtual (simulated)",
    "PT3G VCI (J2534)",
    "J2534 Pass-thru",
    "ELM327 OBD-II",
    "USB-CAN",
    "K-Line (BMW/VAG)",
)

#: Friendly vehicle labels (each car model's own name), in catalogue order.
#: Sourced from :data:`wildcat.cars.vin.CATALOG` so the VIN resolver and the
#: manual year/make/model selector always agree on which vehicles are supported.
_LABEL_TO_CLASS: dict[str, type[CarModel]] = {}
_seen_classes: set[type[CarModel]] = set()
for _entry in CATALOG:
    # Many catalogue rows share a car class (e.g. every Mercedes-Benz row maps
    # to MercedesC300); instantiate each class once, not once per row, so the
    # ~12k-row catalogue does not build 12k car objects on import.
    _cls = _entry["class"]
    if _cls in _seen_classes:
        continue
    _seen_classes.add(_cls)
    _LABEL_TO_CLASS[_cls().name] = _cls
VEHICLE_LABELS: tuple[str, ...] = tuple(_LABEL_TO_CLASS)


def _build_connector(label: str):
    """Instantiate a connector in its virtual (hardware-free) mode.

    Args:
        label: A value from :data:`CONNECTOR_LABELS`.

    Returns:
        A ready-to-open :class:`~wildcat.connectors.base.Connector`.

    Raises:
        ValueError: If the label is not a recognised connector.
    """
    if label == "Virtual (simulated)":
        return VirtualConnection(name="virtual")
    if label == "PT3G VCI (J2534)":
        return PT3GConnector(virtual=True)
    if label == "J2534 Pass-thru":
        return J2534Connector(virtual=True)
    if label == "ELM327 OBD-II":
        return Elm327Connector(port="VIRTUAL", virtual=True)
    if label == "USB-CAN":
        return UsbCANConnector(virtual=True)
    if label == "K-Line (BMW/VAG)":
        return SerialConnector(port="VIRTUAL", virtual=True)
    raise ValueError(f"unknown connector: {label!r}")


class ConnectionModel(QObject):
    """Owns the diagnostic session and publishes its state to the views.

    Signals
    -------
    connected:
        Emitted with the connected :class:`CarModel` after a successful connect.
    disconnected:
        Emitted after a disconnect.
    status_changed:
        Emitted with a human-readable status string on every state change.
    error:
        Emitted with an error message when an operation fails; the UI maps this
        to a dialog instead of letting the exception propagate.
    """

    connected = Signal(object)
    disconnected = Signal()
    status_changed = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session: WildcatSession | None = None
        self._connector_label = CONNECTOR_LABELS[0]
        self._vehicle_label = VEHICLE_LABELS[0]

    # ------------------------------------------------------------- queries --- #
    def available_connectors(self) -> list[str]:
        """Return the connector labels offered in the UI."""
        return list(CONNECTOR_LABELS)

    def available_vehicles(self) -> list[str]:
        """Return the vehicle labels offered in the UI."""
        return list(VEHICLE_LABELS)

    @property
    def is_connected(self) -> bool:
        """True while a session is open."""
        return self._session is not None and self._session.is_connected

    @property
    def car(self) -> CarModel | None:
        """The connected car model, or ``None`` when disconnected."""
        return self._session.car if self._session else None

    # --------------------------------------------------------- lifecycle ----- #
    def connect(self, connector_label: str, vehicle_label: str) -> None:
        """Open a diagnostic session for the chosen connector + vehicle.

        Args:
            connector_label: A value from :data:`CONNECTOR_LABELS`.
            vehicle_label: A value from :data:`VEHICLE_LABELS` (the car
                model's own ``name``).

        Raises:
            ValueError: If the vehicle label is unknown.
            WildcatError: If the session cannot open. The GUI catches this and
                shows it via the :attr:`error` signal.
        """
        try:
            car = _LABEL_TO_CLASS[vehicle_label]()
        except KeyError as exc:
            raise ValueError(f"unknown vehicle: {vehicle_label!r}") from exc
        try:
            self._open_session(connector_label, car)
        except (WildcatError, Exception) as exc:
            self._session = None
            self.error.emit(f"Could not connect: {exc}")
            raise

    def _open_session(self, connector_label: str, car: CarModel) -> None:
        """Build and open a session for a connector + resolved car model."""
        if connector_label not in CONNECTOR_LABELS:
            raise ValueError(f"unknown connector: {connector_label!r}")
        connector = _build_connector(connector_label)
        self._session = WildcatSession(connector, car, WildcatConfig())
        self._session.connect()
        self._connector_label = connector_label
        self._vehicle_label = car.name
        self.status_changed.emit(f"Connected: {car.name} via {connector_label}")
        self.connected.emit(car)

    def connect_by_vin(self, connector_label: str, vin: str) -> None:
        """Decode a VIN and open a session for its resolved vehicle.

        Args:
            connector_label: A value from :data:`CONNECTOR_LABELS`.
            vin: A 17-character VIN.

        Raises:
            WildcatError: If the VIN is invalid/unsupported or the session
                cannot open.
        """
        car = find_vehicle_by_vin(vin)
        if car is None:
            decoded = decode_vin(vin)
            if not decoded.valid:
                msg = f"Invalid VIN: {decoded.reason}"
            else:
                make = decoded.make or "unknown"
                msg = (
                    f"VIN decodes to {make} {decoded.year}, which is not a "
                    f"supported Wildcat vehicle"
                )
            self.error.emit(msg)
            raise WildcatError(msg)
        try:
            self._open_session(connector_label, car)
        except (WildcatError, Exception) as exc:
            self._session = None
            self.error.emit(f"Could not connect: {exc}")
            raise

    def disconnect(self) -> None:
        """Close the current session, if any."""
        if self._session is None:
            return
        try:
            self._session.disconnect()
        finally:
            self._session = None
        self.status_changed.emit("Disconnected")
        self.disconnected.emit()

    # --------------------------------------------------------- diagnostics --- #
    def read_dtcs(self) -> list:
        """Read stored fault codes from the connected vehicle.

        Returns:
            A list of :class:`~wildcat.cars.base.DTC` records.

        Raises:
            WildcatError: If not connected.
        """
        if not self.is_connected:
            raise WildcatError("Not connected")
        return list(self._session.read_dtc())

    def read_live_data(self, keys=None) -> list:
        """Read live signals from the connected vehicle.

        Args:
            keys: Optional iterable of signal names to include; ``None`` reads
                every configured signal.

        Returns:
            A list of :class:`~wildcat.cars.base.LiveData` records.
        """
        if not self.is_connected:
            raise WildcatError("Not connected")
        return list(self._session.read_live_data(keys))

    def clear_dtcs(self) -> None:
        """Clear all stored fault codes on the vehicle."""
        if not self.is_connected:
            raise WildcatError("Not connected")
        self._session.clear_dtc()
        self.status_changed.emit("Fault codes cleared")

    # ------------------------------------------------------- programming ----- #
    def ecu_info(self) -> dict:
        """Return a summary of the connected ECU for the programming tab.

        Returns:
            A dict with ``name``, ``ecu_id`` and ``security_required`` keys.
        """
        car = self.car
        if car is None:
            raise WildcatError("Not connected")
        return {
            "name": car.name,
            "ecu_id": car.ecu_id(),
            "security_required": bool(car.security_access()),
        }

    def perform_security_access(self, key_id: bytes = b"\x00\x00\x00\x00") -> tuple[bytes, bytes]:
        """Run a full security-access (seed/key) exchange.

        Args:
            key_id: The 4-byte key identifier sent to request the seed.

        Returns:
            A ``(seed, key)`` tuple: the seed the ECU returned and the session
            key the client replied with.
        """
        car = self.car
        if car is None:
            raise WildcatError("Not connected")
        if not car.security_access():
            raise WildcatError(f"{car.name} does not require security access")
        try:
            seed = car.send_seed(key_id)
            key = car.send_key(seed)
        except NotImplementedError as exc:
            raise WildcatError(f"Security access requires a real connector: {exc}") from exc
        return seed, key
