"""Config flow for ConnectPro KVM."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_BAUDRATE, CONF_DEVICE, DEFAULT_BAUDRATE, DOMAIN


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
                vol.Optional(CONF_NAME): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)
