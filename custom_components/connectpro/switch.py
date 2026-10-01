"""Buzzer and mouse channel-switching controls for ConnectPro KVM devices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up the KVM buzzer and mouse channel-switching controls."""
    async_add_entities(
        [ConnectProBuzzerSwitch(entry), ConnectProMouseChannelSwitch(entry)]
    )


class ConnectProBuzzerSwitch(ConnectProEntity, SwitchEntity):
    """Control the buzzer while reporting only received state."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:volume-high"

    def __init__(self, entry: ConnectProConfigEntry) -> None:
        """Initialize the control with the shared buzzer state."""
        super().__init__(entry, "buzzer")

    @property
    def is_on(self) -> bool | None:
        """Return the last reported buzzer state, or unknown until observed."""
        value = self._client.state.get(self._state_key)
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Request buzzer on without assuming the command succeeded."""
        await self._async_send_command("BZON")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Request buzzer off without assuming the command succeeded."""
        await self._async_send_command("BZOFF")


class ConnectProMouseChannelSwitch(ConnectProEntity, SwitchEntity):
    """Control mouse channel switching while reporting only received state."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:mouse"

    def __init__(self, entry: ConnectProConfigEntry) -> None:
        """Initialize the control with the shared mouse-switching state."""
        super().__init__(entry, "mouse_change_channel")

    @property
    def is_on(self) -> bool | None:
        """Return the last reported setting, or unknown until observed."""
        value = self._client.state.get(self._state_key)
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Request mouse channel switching on without assuming success."""
        await self._async_send_command("M1")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Request mouse channel switching off without assuming success."""
        await self._async_send_command("M0")
