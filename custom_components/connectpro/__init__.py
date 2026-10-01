"""ConnectPro KVM integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .client import ConnectProClient, SerialSettings
from .const import (
    ATTR_COMMAND,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_DEVICE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
    SERVICE_SEND_COMMAND,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [
    Platform.SELECT,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

type ConnectProConfigEntry = ConfigEntry[ConnectProClient]


def serial_settings(data: dict) -> SerialSettings:
    """Read connection settings, including entries made by the scaffold."""
    return SerialSettings(
        device=data[CONF_DEVICE],
        baudrate=data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
        bytesize=data.get(CONF_BYTESIZE, DEFAULT_BYTESIZE),
        parity=data.get(CONF_PARITY, DEFAULT_PARITY),
        stopbits=data.get(CONF_STOPBITS, DEFAULT_STOPBITS),
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the advanced command action independently of loaded devices."""

    async def async_send_command(call: ServiceCall) -> None:
        device = dr.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
        if device is None:
            raise ServiceValidationError("The selected KVM device does not exist")

        entries = [
            entry
            for entry_id in device.config_entries
            if (entry := hass.config_entries.async_get_entry(entry_id)) is not None
            and entry.domain == DOMAIN
        ]
        if len(entries) != 1:
            raise ServiceValidationError("Select a device belonging to ConnectPro KVM")
        entry = entries[0]
        if entry.state is not ConfigEntryState.LOADED:
            raise HomeAssistantError("The KVM connection is not loaded")

        try:
            await entry.runtime_data.async_send_command(call.data[ATTR_COMMAND])
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        except OSError as err:
            raise HomeAssistantError(f"Unable to send the KVM command: {err}") from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        async_send_command,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_COMMAND): cv.string,
            }
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConnectProConfigEntry) -> bool:
    """Configure the port and start a shared reader for all KVM entities."""
    client = ConnectProClient(serial_settings(entry.data))
    try:
        await client.async_connect()
    except (OSError, TimeoutError, ValueError) as err:
        await client.async_close()
        raise ConfigEntryNotReady(f"Unable to open the KVM serial port: {err}") from err

    entry.runtime_data = client
    setup_complete = False
    unsubscribe_metadata = None
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        @callback
        def async_update_device_metadata() -> None:
            """Keep reported device metadata even when all entities are disabled."""
            model = client.state.get("model")
            if not isinstance(model, str) or not model:
                return
            registry = dr.async_get(hass)
            device = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
            if device is not None and device.model != model:
                registry.async_update_device(device.id, model=model)

        unsubscribe_metadata = client.add_listener(async_update_device_metadata)
        entry.async_on_unload(unsubscribe_metadata)
        async_update_device_metadata()
        entry.async_create_background_task(
            hass, client.async_run(initialize_state=True), "ConnectPro reader"
        )

        async def async_stop(event: Event) -> None:
            await client.async_close()

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop)
        )
        setup_complete = True
    finally:
        if not setup_complete:
            if unsubscribe_metadata is not None:
                unsubscribe_metadata()
            await client.async_close()
    _LOGGER.debug("ConnectPro entities ready for %s", entry.data[CONF_DEVICE])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConnectProConfigEntry) -> bool:
    """Unload entities and close the serial connection."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_close()
        return True
    return False
