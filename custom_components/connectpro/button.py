"""Reset command for ConnectPro KVM devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .entity import ConnectProEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import ConnectProConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnectProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KVM reset button."""
    async_add_entities([ConnectProResetButton(entry)])


class ConnectProResetButton(ConnectProEntity, ButtonEntity):
    """Send the reset command used by the existing Home Assistant setup."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConnectProConfigEntry) -> None:
        """Initialize the reset button."""
        super().__init__(entry, "reset")

    async def async_press(self) -> None:
        """Send reset without assuming any resulting device state."""
        await self._async_send_command("W0")
