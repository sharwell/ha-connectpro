"""Shared entity behavior for ConnectPro KVM devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

if TYPE_CHECKING:
    from . import ConnectProConfigEntry


class ConnectProEntity(Entity):
    """An entity backed by observed state from one serial connection."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConnectProConfigEntry, key: str) -> None:
        """Initialize the entity and associate it with the KVM device."""
        self._client = entry.runtime_data
        self._state_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._device_identifier = (DOMAIN, entry.entry_id)
        self._device_name = entry.title or "ConnectPro KVM"

    @property
    def device_info(self) -> DeviceInfo:
        """Describe the shared device, including a model only when reported."""
        model = self._client.state.get("model")
        model_info = {"model": model} if isinstance(model, str) and model else {}
        return DeviceInfo(
            identifiers={self._device_identifier},
            manufacturer="ConnectPro",
            name=self._device_name,
            **model_info,
        )

    @property
    def available(self) -> bool:
        """Return whether the serial connection is available."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to serial state and connection updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self._client.add_listener(self._async_handle_update))

    @callback
    def _async_handle_update(self) -> None:
        """Publish an update received on the Home Assistant event loop."""
        self.async_write_ha_state()

    async def _async_send_command(self, command: str) -> None:
        """Send a command and expose actionable Home Assistant errors."""
        try:
            await self._client.async_send_command(command)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        except OSError as err:
            raise HomeAssistantError(
                f"Unable to send ConnectPro command: {err}"
            ) from err
