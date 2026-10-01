"""Configuration flows using Home Assistant's real flow and entry classes."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from custom_components.connectpro.client import SerialSettings
from custom_components.connectpro.config_flow import ConnectProConfigFlow
from custom_components.connectpro.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_DEVICE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntries,
    ConfigEntry,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

FLOW_MODULE = "custom_components.connectpro.config_flow"


@pytest_asyncio.fixture
async def hass(tmp_path: Path) -> AsyncGenerator[HomeAssistant]:
    """Provide the real config entry manager without loading integrations."""
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    try:
        yield instance
    finally:
        await instance.async_stop(force=True)


@pytest.fixture
def flow(hass: HomeAssistant) -> ConnectProConfigFlow:
    """Return a user-initiated flow connected to Home Assistant."""
    instance = ConnectProConfigFlow()
    instance.hass = hass
    instance.handler = DOMAIN
    instance.context = {"source": SOURCE_USER}
    return instance


@pytest.fixture(autouse=True)
def list_ports() -> Generator[AsyncMock]:
    """Do not enumerate the test host's physical ports."""
    with patch(
        f"{FLOW_MODULE}.async_list_serial_ports", new_callable=AsyncMock
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def client_class() -> Generator[MagicMock]:
    """Replace only the serial client at the hardware boundary."""
    with patch(f"{FLOW_MODULE}.ConnectProClient") as mock:
        mock.return_value.async_connect = AsyncMock()
        mock.return_value.async_close = AsyncMock()
        yield mock


def add_entry(
    hass: HomeAssistant, data: dict, title: str = "Original KVM"
) -> ConfigEntry:
    """Register an existing entry without starting its physical serial reader."""
    entry = ConfigEntry(
        domain=DOMAIN,
        title=title,
        data=data,
        options={},
        source=SOURCE_USER,
        unique_id=data[CONF_DEVICE],
        version=1,
        minor_version=1,
        discovery_keys=MappingProxyType({}),
    )
    hass.config_entries._entries[entry.entry_id] = entry
    return entry


@pytest.mark.asyncio
async def test_user_form_only_requests_device_and_name(
    flow: ConnectProConfigFlow, list_ports: AsyncMock
) -> None:
    """Users select a port while serial framing remains automatic."""
    list_ports.return_value = [
        SimpleNamespace(device="COM9", product="USB serial", manufacturer="Example"),
    ]
    result = await flow.async_step_user()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    fields = {
        key.schema: selector for key, selector in result["data_schema"].schema.items()
    }
    assert set(fields) == {CONF_DEVICE, CONF_NAME}
    assert fields[CONF_DEVICE].config["custom_value"] is True
    assert fields[CONF_DEVICE].config["options"] == [
        {"value": "COM9", "label": "COM9 (USB serial)"}
    ]
    validated = result["data_schema"]({CONF_DEVICE: "COM9"})
    assert validated[CONF_NAME] == DEFAULT_NAME


@pytest.mark.asyncio
async def test_port_enumeration_failure_still_allows_manual_path(
    flow: ConnectProConfigFlow, list_ports: AsyncMock
) -> None:
    """Discovery failure does not prevent entering a known serial path."""
    list_ports.side_effect = OSError("enumeration unavailable")
    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"]({CONF_DEVICE: "COM9"})[CONF_DEVICE] == "COM9"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", [None, "", "  ", "  Desk KVM  "])
async def test_success_uses_defaults_and_closes_probe(
    flow: ConnectProConfigFlow, client_class: MagicMock, name: str | None
) -> None:
    """A successful probe stores normalized input and the known serial settings."""
    user_input = {CONF_DEVICE: " COM9 "}
    if name is not None:
        user_input[CONF_NAME] = name
    result = await flow.async_step_user(user_input)

    client_class.assert_called_once_with(SerialSettings(device="COM9"))
    client_class.return_value.async_connect.assert_awaited_once_with()
    client_class.return_value.async_close.assert_awaited_once_with()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ("Desk KVM" if name == "  Desk KVM  " else DEFAULT_NAME)
    assert result["data"] == {
        CONF_DEVICE: "COM9",
        CONF_NAME: result["title"],
        CONF_BAUDRATE: 115200,
        CONF_BYTESIZE: 8,
        CONF_PARITY: "N",
        CONF_STOPBITS: 1,
    }
    assert flow.unique_id == "COM9"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [OSError("missing port"), TimeoutError("timeout"), ValueError("bad settings")],
)
async def test_failed_probe_closes_and_does_not_create_entry(
    hass: HomeAssistant,
    flow: ConnectProConfigFlow,
    client_class: MagicMock,
    error: Exception,
) -> None:
    """Every supported connection failure returns a retryable form."""
    client_class.return_value.async_connect.side_effect = error
    result = await flow.async_step_user({CONF_DEVICE: "COM9"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries(DOMAIN) == []
    client_class.return_value.async_close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_empty_path_never_opens_serial(
    flow: ConnectProConfigFlow, client_class: MagicMock
) -> None:
    """Whitespace-only paths are rejected before probing hardware."""
    result = await flow.async_step_user({CONF_DEVICE: "  "})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DEVICE: "invalid_device"}
    client_class.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("requested", ["/dev/ttyUSB0", "/dev/serial/by-id/kvm"])
async def test_duplicate_path_or_symlink_never_opens_serial(
    hass: HomeAssistant,
    flow: ConnectProConfigFlow,
    client_class: MagicMock,
    requested: str,
) -> None:
    """Two entries cannot claim the same physical port under different aliases."""
    add_entry(hass, {CONF_DEVICE: "/dev/ttyUSB0"})
    with patch(f"{FLOW_MODULE}.os.path.realpath", return_value="/dev/ttyUSB0"):
        result = await flow.async_step_user({CONF_DEVICE: requested})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    client_class.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("requested", ["/dev/ttyUSB0", "/dev/serial/by-id/kvm"])
async def test_reconfigure_own_port_preserves_settings_without_reopening(
    hass: HomeAssistant,
    flow: ConnectProConfigFlow,
    client_class: MagicMock,
    requested: str,
) -> None:
    """Renaming or choosing the same port's alias does not contend with its reader."""
    original = {
        CONF_DEVICE: "/dev/ttyUSB0",
        CONF_NAME: "Original KVM",
        CONF_BAUDRATE: 9600,
        CONF_BYTESIZE: 7,
        CONF_PARITY: "E",
        CONF_STOPBITS: 2,
    }
    entry = add_entry(hass, original)
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}

    with (
        patch(f"{FLOW_MODULE}.os.path.realpath", return_value="/dev/ttyUSB0"),
        patch.object(hass.config_entries, "async_schedule_reload") as reload_entry,
    ):
        result = await flow.async_step_reconfigure(
            {CONF_DEVICE: requested, CONF_NAME: "Renamed KVM"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    client_class.assert_not_called()
    assert entry.title == "Renamed KVM"
    assert entry.data == original | {CONF_DEVICE: requested, CONF_NAME: "Renamed KVM"}
    reload_entry.assert_called_once_with(entry.entry_id)


@pytest.mark.asyncio
async def test_reconfigure_new_port_probes_with_stored_settings(
    hass: HomeAssistant, flow: ConnectProConfigFlow, client_class: MagicMock
) -> None:
    """Moving a migrated entry to another port preserves its nondefault framing."""
    entry = add_entry(
        hass,
        {
            CONF_DEVICE: "COM9",
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 7,
            CONF_PARITY: "E",
            CONF_STOPBITS: 2,
        },
    )
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}

    with patch.object(hass.config_entries, "async_schedule_reload"):
        result = await flow.async_step_reconfigure({CONF_DEVICE: "COM10"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    client_class.assert_called_once_with(
        SerialSettings(
            device="COM10", baudrate=9600, bytesize=7, parity="E", stopbits=2
        )
    )
    client_class.return_value.async_connect.assert_awaited_once_with()
    client_class.return_value.async_close.assert_awaited_once_with()
    assert entry.data[CONF_DEVICE] == "COM10"


@pytest.mark.asyncio
async def test_failed_reconfigure_keeps_original_entry(
    hass: HomeAssistant, flow: ConnectProConfigFlow, client_class: MagicMock
) -> None:
    """An unavailable replacement port does not overwrite a working configuration."""
    original = {CONF_DEVICE: "COM9", CONF_NAME: "Original KVM"}
    entry = add_entry(hass, original)
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    client_class.return_value.async_connect.side_effect = OSError("unavailable")

    with patch.object(hass.config_entries, "async_schedule_reload") as reload_entry:
        result = await flow.async_step_reconfigure(
            {CONF_DEVICE: "COM10", CONF_NAME: "New KVM"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == original
    assert entry.title == "Original KVM"
    client_class.return_value.async_close.assert_awaited_once_with()
    reload_entry.assert_not_called()


@pytest.mark.asyncio
async def test_reconfigure_rejects_other_entrys_port(
    hass: HomeAssistant, flow: ConnectProConfigFlow, client_class: MagicMock
) -> None:
    """Reconfiguration still enforces exclusive ownership of another KVM port."""
    entry = add_entry(hass, {CONF_DEVICE: "COM9"})
    add_entry(hass, {CONF_DEVICE: "COM10"})
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}

    result = await flow.async_step_reconfigure({CONF_DEVICE: "COM10"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_DEVICE] == "COM9"
    client_class.assert_not_called()
