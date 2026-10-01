"""Channel and hotkey selection for ConnectPro KVM devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import ServiceValidationError

from .entity import ConnectProEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import ConnectProConfigEntry

CHANNEL_COMMANDS = {f"Channel {channel}": f"Ch{channel}" for channel in range(1, 5)}
HOTKEY_COMMANDS = {
    "Ctrl": "ctrl",
    "Shift": "shift",
    "Scroll Lock": "scroll",
    "Caps Lock": "caps",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnectProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KVM channel and hotkey selectors."""
    async_add_entities([ConnectProChannelSelect(entry), ConnectProHotkeySelect(entry)])


class ConnectProChannelSelect(ConnectProEntity, SelectEntity):
    """Select the active KVM channel, confirmed by serial responses."""

    def __init__(self, entry: ConnectProConfigEntry) -> None:
        """Initialize the channel selector."""
        super().__init__(entry, "channel")
        self._attr_options = list(CHANNEL_COMMANDS)

    @property
    def current_option(self) -> str | None:
        """Return the last channel reported by the KVM."""
        value = self._client.state.get(self._state_key)
        return value if isinstance(value, str) else None

    async def async_select_option(self, option: str) -> None:
        """Request a channel change without assuming it succeeded."""
        if option not in CHANNEL_COMMANDS:
            raise ServiceValidationError(f"Unsupported ConnectPro channel: {option}")
        await self._async_send_command(CHANNEL_COMMANDS[option])


class ConnectProHotkeySelect(ConnectProEntity, SelectEntity):
    """Select the hotkey while reporting only received state."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConnectProConfigEntry) -> None:
        """Initialize the hotkey selector."""
        super().__init__(entry, "hotkey")
        self._attr_options = list(HOTKEY_COMMANDS)

    @property
    def current_option(self) -> str | None:
        """Return a recognized hotkey reported by the KVM."""
        value = self._client.state.get(self._state_key)
        return value if isinstance(value, str) and value in HOTKEY_COMMANDS else None

    async def async_select_option(self, option: str) -> None:
        """Request a hotkey change without assuming it succeeded."""
        if option not in HOTKEY_COMMANDS:
            raise ServiceValidationError(f"Unsupported ConnectPro hotkey: {option}")
        await self._async_send_command(HOTKEY_COMMANDS[option])
