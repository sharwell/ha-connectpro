"""Channel selection for ConnectPro KVM devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import ServiceValidationError

from .entity import ConnectProEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import ConnectProConfigEntry

CHANNEL_COMMANDS = {f"Channel {channel}": f"Ch{channel}" for channel in range(1, 5)}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnectProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KVM channel selector."""
    async_add_entities([ConnectProChannelSelect(entry)])


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
