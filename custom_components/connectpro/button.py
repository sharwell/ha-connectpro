"""Display reset and routing sync commands for ConnectPro KVM devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .entity import ConnectProEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import ConnectProConfigEntry

SYNC_COMMANDS = {
    "sync_usb_hubs": "h0p0",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnectProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KVM display reset and confirmed routing sync buttons."""
    async_add_entities(
        [
            ConnectProResetButton(entry),
            *(ConnectProRoutingSyncButton(entry, key) for key in SYNC_COMMANDS),
        ]
    )


class ConnectProResetButton(ConnectProEntity, ButtonEntity):
    """Send the command observed to cycle displays off and on."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConnectProConfigEntry) -> None:
        """Initialize the reset button."""
        super().__init__(entry, "reset")

    async def async_press(self) -> None:
        """Reset displays without assuming any resulting device state."""
        await self._async_send_command("W0")


class ConnectProRoutingSyncButton(ConnectProEntity, ButtonEntity):
    """Request sync for the routing scope established by a tested command."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConnectProConfigEntry, key: str) -> None:
        """Initialize one confirmed routing sync action."""
        super().__init__(entry, key)
        self._command = SYNC_COMMANDS[key]

    async def async_press(self) -> None:
        """Request routing sync without assuming the device state changed."""
        await self._async_send_command(self._command)
