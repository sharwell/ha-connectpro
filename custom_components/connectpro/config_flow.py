"""User setup for a ConnectPro KVM serial connection."""

from __future__ import annotations

import logging
import os

import voluptuous as vol
from serialx import async_list_serial_ports

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from . import serial_settings
from .client import ConnectProClient
from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_DEVICE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ConnectProConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure and verify a serial port with known working defaults."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Choose a port; configure it automatically before creating an entry."""
        return await self._async_configure("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Change the port or device name without recreating entities."""
        return await self._async_configure("reconfigure", user_input)

    async def _async_configure(
        self, step_id: str, user_input: dict | None
    ) -> FlowResult:
        entry = self._get_reconfigure_entry() if step_id == "reconfigure" else None
        values = dict(entry.data) if entry is not None else {}
        errors: dict[str, str] = {}

        if user_input is not None:
            values.update(user_input)
            values[CONF_DEVICE] = values[CONF_DEVICE].strip()
            values.setdefault(CONF_BAUDRATE, DEFAULT_BAUDRATE)
            values.setdefault(CONF_BYTESIZE, DEFAULT_BYTESIZE)
            values.setdefault(CONF_PARITY, DEFAULT_PARITY)
            values.setdefault(CONF_STOPBITS, DEFAULT_STOPBITS)
            title = values.get(CONF_NAME, "").strip() or DEFAULT_NAME
            values[CONF_NAME] = title

            if not values[CONF_DEVICE]:
                errors[CONF_DEVICE] = "invalid_device"
            elif await self._async_is_duplicate(values[CONF_DEVICE], entry):
                return self.async_abort(reason="already_configured")
            else:
                # Reopening a loaded port just to rename the entry would
                # contend with the existing serial reader.
                needs_probe = entry is None or not await self._async_same_device(
                    entry.data[CONF_DEVICE], values[CONF_DEVICE]
                )
                if needs_probe:
                    client = ConnectProClient(serial_settings(values))
                    try:
                        await client.async_connect()
                    except (OSError, TimeoutError, ValueError):
                        _LOGGER.debug("Unable to verify the serial port", exc_info=True)
                        errors["base"] = "cannot_connect"
                    finally:
                        await client.async_close()

                if not errors:
                    if entry is not None:
                        return self.async_update_reload_and_abort(
                            entry,
                            unique_id=values[CONF_DEVICE],
                            title=title,
                            data=values,
                        )
                    await self.async_set_unique_id(values[CONF_DEVICE])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=title, data=values)

        options = []
        try:
            for port in await async_list_serial_ports():
                label = port.product or port.manufacturer or port.device
                options.append(
                    {"value": port.device, "label": f"{port.device} ({label})"}
                )
        except OSError:
            _LOGGER.debug(
                "Unable to list serial ports; manual paths still work", exc_info=True
            )

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE, default=values.get(CONF_DEVICE, "")
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            custom_value=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_NAME, default=values.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _async_is_duplicate(
        self, device: str, entry: config_entries.ConfigEntry | None
    ) -> bool:
        """Prevent two entries using the same port, including symlink aliases."""
        for other in self._async_current_entries():
            if entry is not None and other.entry_id == entry.entry_id:
                continue
            if await self._async_same_device(device, other.data[CONF_DEVICE]):
                return True
        return False

    async def _async_same_device(self, first: str, second: str) -> bool:
        """Compare port aliases without changing the persistent saved path."""
        first_resolved = await self.hass.async_add_executor_job(os.path.realpath, first)
        second_resolved = await self.hass.async_add_executor_job(
            os.path.realpath, second
        )
        return os.path.normcase(first_resolved) == os.path.normcase(second_resolved)
