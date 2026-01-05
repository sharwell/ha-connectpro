"""Config flow for ConnectPro KVM."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import (
    BYTESIZE_OPTIONS,
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
    PARITY_OPTIONS,
    STOPBITS_OPTIONS,
)


class ConnectProConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ConnectPro KVM."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            title = user_input.get(CONF_NAME) or user_input[CONF_DEVICE]
            return self.async_create_entry(title=title, data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE): str,
                vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.Coerce(
                    int
                ),
                vol.Optional(CONF_BYTESIZE, default=DEFAULT_BYTESIZE): vol.In(
                    BYTESIZE_OPTIONS
                ),
                vol.Optional(CONF_PARITY, default=DEFAULT_PARITY): vol.In(
                    PARITY_OPTIONS
                ),
                vol.Optional(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.In(
                    STOPBITS_OPTIONS
                ),
                vol.Optional(CONF_NAME): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)
