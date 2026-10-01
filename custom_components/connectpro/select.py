"""Channel, routing, hotkey, and scan selection for ConnectPro KVM devices."""

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
AUTO_SCAN_COMMANDS = {
    "Off": "s0",
    "5 seconds": "s1",
    "8 seconds": "s2",
    "15 seconds": "s3",
    "20 seconds": "s4",
    "30 seconds": "s5",
}
ROUTING_OPTIONS = ("Sync", "Channel 1", "Channel 2", "Channel 3", "Channel 4")
ROUTING_COMMAND_PREFIXES = {
    "audio": "o",
    "video1": "v1p",
    "video2": "v2p",
    "hub1": "h1p",
    "hub2": "h2p",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConnectProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KVM channel, routing, hotkey, and scan selectors."""
    async_add_entities(
        [
            ConnectProChannelSelect(entry),
            ConnectProHotkeySelect(entry),
            ConnectProAutoScanSelect(entry),
            *(ConnectProRoutingSelect(entry, key) for key in ROUTING_COMMAND_PREFIXES),
        ]
    )


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


class ConnectProRoutingSelect(ConnectProEntity, SelectEntity):
    """Select a routing destination while reporting only observed state."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConnectProConfigEntry, key: str) -> None:
        """Initialize an audio, video, or USB hub routing selector."""
        super().__init__(entry, key)
        self._attr_options = list(ROUTING_OPTIONS)
        self._command_prefix = ROUTING_COMMAND_PREFIXES[key]

    @property
    def current_option(self) -> str | None:
        """Return a recognized routing destination reported by the KVM."""
        value = self._client.state.get(self._state_key)
        return value if isinstance(value, str) and value in ROUTING_OPTIONS else None

    async def async_select_option(self, option: str) -> None:
        """Request routing, requiring the shared button to synchronize USB hubs."""
        if option not in ROUTING_OPTIONS:
            raise ServiceValidationError(f"Unsupported ConnectPro routing: {option}")
        if option == "Sync" and self._state_key in ("hub1", "hub2"):
            raise ServiceValidationError(
                "Hub routing cannot be synchronized independently. "
                "Use Sync both USB hubs to synchronize both hubs."
            )
        port = ROUTING_OPTIONS.index(option)
        await self._async_send_command(f"{self._command_prefix}{port}")


class ConnectProAutoScanSelect(ConnectProEntity, SelectEntity):
    """Select automatic scanning from separately reported on/off and timing state."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: ConnectProConfigEntry) -> None:
        """Initialize the automatic scan selector."""
        super().__init__(entry, "auto_scan")
        self._attr_options = list(AUTO_SCAN_COMMANDS)

    @property
    def current_option(self) -> str | None:
        """Return Off or the last reported interval only when scan state is known."""
        enabled = self._client.state.get(self._state_key)
        if enabled is False:
            return "Off"
        interval = self._client.state.get("auto_scan_interval")
        if (
            enabled is True
            and isinstance(interval, str)
            and interval != "Off"
            and interval in AUTO_SCAN_COMMANDS
        ):
            return interval
        return None

    async def async_select_option(self, option: str) -> None:
        """Request a tested scan setting without assuming the command succeeded."""
        if option not in AUTO_SCAN_COMMANDS:
            raise ServiceValidationError(
                f"Unsupported ConnectPro scan setting: {option}"
            )
        await self._async_send_command(AUTO_SCAN_COMMANDS[option])
