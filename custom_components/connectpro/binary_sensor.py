"""Observed boolean settings for ConnectPro KVM devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import ConnectProEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import ConnectProConfigEntry

BINARY_SENSOR_KEYS = ("buzzer", "mouse_change_channel")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnectProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the observed KVM boolean settings."""
    async_add_entities(ConnectProBinarySensor(entry, key) for key in BINARY_SENSOR_KEYS)


class ConnectProBinarySensor(ConnectProEntity, BinarySensorEntity):
    """A read-only boolean setting reported by the KVM."""

    @property
    def is_on(self) -> bool | None:
        """Return the last reported setting, or unknown until observed."""
        value = self._client.state.get(self._state_key)
        return value if isinstance(value, bool) else None
