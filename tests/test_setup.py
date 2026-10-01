"""Integration lifecycle and device-targeted actions on real HA objects."""

from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from custom_components.connectpro import (
    PLATFORMS,
    async_setup,
    async_setup_entry,
    async_unload_entry,
    serial_settings,
)
from custom_components.connectpro.client import SerialSettings
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr


@pytest.fixture
async def hass(tmp_path):
    """Provide actual HA service, event, entry, and device registries."""
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    await dr.async_load(instance)
    yield instance
    await instance.async_stop(force=True)


def make_entry(domain="connectpro", state=ConfigEntryState.NOT_LOADED):
    return ConfigEntry(
        domain=domain,
        title="Test KVM",
        data={"device": "/dev/test-kvm"},
        options={},
        source="user",
        unique_id="/dev/test-kvm",
        version=1,
        minor_version=1,
        discovery_keys=MappingProxyType({}),
        state=state,
    )


def make_client():
    return SimpleNamespace(
        async_connect=AsyncMock(),
        async_close=AsyncMock(),
        async_run=AsyncMock(),
        async_send_command=AsyncMock(),
    )


def register_device(hass, entry):
    """Model an entry already persisted by the config-entry manager."""
    hass.config_entries._entries[entry.entry_id] = entry
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(entry.domain, entry.entry_id)},
        name=entry.title,
    )


def test_defaults_and_legacy_serial_settings():
    assert serial_settings({"device": "/dev/kvm"}) == SerialSettings("/dev/kvm")
    settings = serial_settings(
        {
            "device": "/dev/kvm",
            "baudrate": 9600,
            "bytesize": 7,
            "parity": "E",
            "stopbits": 2,
        }
    )
    assert (
        settings.baudrate,
        settings.bytesize,
        settings.parity,
        settings.stopbits,
    ) == (9600, 7, "E", 2)


async def test_setup_opens_one_shared_connection_and_closes_on_stop(hass):
    entry, client = make_entry(), make_client()
    with (
        patch(
            "custom_components.connectpro.ConnectProClient", return_value=client
        ) as factory,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ) as forward,
    ):
        assert await async_setup_entry(hass, entry)
        factory.assert_called_once_with(SerialSettings("/dev/test-kvm"))
        client.async_connect.assert_awaited_once()
        assert entry.runtime_data is client
        forward.assert_awaited_once_with(entry, PLATFORMS)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        client.async_close.assert_awaited_once()


async def test_setup_failure_releases_connection_and_requests_ha_retry(hass):
    client = make_client()
    client.async_connect.side_effect = OSError("port unavailable")
    with patch("custom_components.connectpro.ConnectProClient", return_value=client):
        with pytest.raises(ConfigEntryNotReady, match="port unavailable"):
            await async_setup_entry(hass, make_entry())
    client.async_close.assert_awaited_once()


async def test_platform_setup_failure_closes_serial_port(hass):
    client = make_client()
    with (
        patch("custom_components.connectpro.ConnectProClient", return_value=client),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(side_effect=RuntimeError("platform failed")),
        ),
        pytest.raises(RuntimeError, match="platform failed"),
    ):
        await async_setup_entry(hass, make_entry())
    client.async_close.assert_awaited_once()


@pytest.mark.parametrize("unload_ok", [True, False])
async def test_unload_closes_port_only_when_platforms_unload(hass, unload_ok):
    entry = make_entry()
    entry.runtime_data = client = make_client()
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=unload_ok),
    ) as unload:
        assert await async_unload_entry(hass, entry) is unload_ok
        unload.assert_awaited_once_with(entry, PLATFORMS)
    assert client.async_close.await_count == int(unload_ok)


async def test_command_action_is_registered_before_any_entry_loads(hass):
    assert await async_setup(hass, {})
    assert hass.services.has_service("connectpro", "send_command")
    with pytest.raises(ServiceValidationError, match="does not exist"):
        await hass.services.async_call(
            "connectpro",
            "send_command",
            {"device_id": "missing", "command": "Ch2"},
            blocking=True,
        )


async def test_command_action_targets_only_the_selected_device(hass):
    await async_setup(hass, {})
    entry = make_entry(state=ConfigEntryState.LOADED)
    entry.runtime_data = client = make_client()
    device = register_device(hass, entry)
    await hass.services.async_call(
        "connectpro",
        "send_command",
        {"device_id": device.id, "command": "Ch2"},
        blocking=True,
    )
    client.async_send_command.assert_awaited_once_with("Ch2")


async def test_command_action_rejects_another_integrations_device(hass):
    await async_setup(hass, {})
    device = register_device(
        hass, make_entry(domain="other", state=ConfigEntryState.LOADED)
    )
    with pytest.raises(ServiceValidationError, match="belonging to ConnectPro"):
        await hass.services.async_call(
            "connectpro",
            "send_command",
            {"device_id": device.id, "command": "Ch2"},
            blocking=True,
        )


async def test_command_action_reports_unloaded_device(hass):
    await async_setup(hass, {})
    device = register_device(hass, make_entry())
    with pytest.raises(HomeAssistantError, match="not loaded"):
        await hass.services.async_call(
            "connectpro",
            "send_command",
            {"device_id": device.id, "command": "Ch2"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ValueError("invalid command"), ServiceValidationError),
        (OSError("disconnected"), HomeAssistantError),
    ],
)
async def test_command_action_surfaces_validation_and_transport_errors(
    hass, error, expected
):
    await async_setup(hass, {})
    entry = make_entry(state=ConfigEntryState.LOADED)
    entry.runtime_data = client = make_client()
    client.async_send_command.side_effect = error
    device = register_device(hass, entry)
    with pytest.raises(expected, match=str(error)):
        await hass.services.async_call(
            "connectpro",
            "send_command",
            {"device_id": device.id, "command": "Ch2"},
            blocking=True,
        )


async def test_command_action_requires_explicit_device(hass):
    await async_setup(hass, {})
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "connectpro", "send_command", {"command": "Ch2"}, blocking=True
        )
