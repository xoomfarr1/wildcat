"""Pydantic settings and a shared settings-driver mixin.

``ConnectorSettings`` is the validated, normalised configuration bundle that
every connector in this package maintains as ``.settings``.  It is built from
the connector's own attributes on demand, so there is a single source of truth
for the configuration (the instance attributes) plus a validated view of it.

``SettingsDriven`` is a mixin that all four connector drivers (``j2534``,
``pt3g``, ``elm327``, ``usbcan``) inherit.  It exposes:

* ``settings``  - pydantic model holding the validated configuration.
* ``validate_settings()`` - re-run validation (e.g. after a device re-open).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConnectorSettings(BaseModel):
    """Validated, normalised connector configuration."""

    virtual: bool = Field(default=False, description="Use the in-memory test adapter.")
    baud: int = Field(default=500000, ge=1200, description="Serial bit rate (Hz).")
    device: str | None = Field(
        default=None, description="Backend device path / USB VID-PID pair."
    )
    vendor_id: int | None = Field(default=None, ge=0x0000, le=0xFFFF, description="USB vendor ID.")
    product_id: int | None = Field(default=None, ge=0x0000, le=0xFFFF, description="USB product ID.")
    channel: int = Field(default=0, ge=0, description="Device channel number.")
    timeout: float = Field(default=1.0, ge=0, description="Default receive timeout (seconds).")
    name: str | None = Field(default=None, description="Human-readable adapter name.")

    @property
    def vid(self) -> int | None:
        return self.vendor_id

    @property
    def pid(self) -> int | None:
        return self.product_id

    def to_dict(self) -> dict:
        return self.model_dump()


class SettingsDriven:
    """Mixin providing a pydantic-validated settings snapshot for connectors."""

    _SETTINGS_FIELDS: tuple[str, ...] = ()

    def validate_settings(self) -> ConnectorSettings:
        """Re-build and return a validated settings snapshot."""
        return self.settings

    @property
    def settings(self) -> ConnectorSettings:
        """Return a pydantic-validated snapshot of this connector's config."""
        if not getattr(type(self), "_SETTINGS_FIELDS", None):
            return ConnectorSettings()
        data = {}
        for field in type(self)._SETTINGS_FIELDS:
            value = getattr(self, field, None)
            if value is not None:
                data[field] = value
        return ConnectorSettings.model_validate(data)
