"""Observed hotkey and routing settings for ConnectPro KVM devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity

from .entity import ConnectProEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import ConnectProConfigEntry

SENSOR_KEYS = ("hotkey", "audio", "hub1", "hub2")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnectProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the observed KVM hotkey and routing settings."""
    async_add_entities(ConnectProSensor(entry, key) for key in SENSOR_KEYS)


class ConnectProSensor(ConnectProEntity, SensorEntity):
    """A read-only text setting reported by the KVM."""

    @property
    def native_value(self) -> str | None:
        """Return the last reported setting, or unknown until observed."""
        value = self._client.state.get(self._state_key)
        return value if isinstance(value, str) else None
