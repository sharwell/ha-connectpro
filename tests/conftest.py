"""Home Assistant fixtures using real integration setup and simulated serial I/O."""

from types import MappingProxyType

import pytest
from serial_peer import SerialReader, SerialWriter
from serialx import SerialPortInfo

from custom_components.connectpro import client, config_flow
from custom_components.connectpro.const import DOMAIN
from homeassistant import loader
from homeassistant.config_entries import (
    ConfigEntries,
    ConfigEntry,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry,
    entity,
    entity_registry,
    issue_registry,
    restore_state,
    translation,
)


class SerialPorts:
    """Expose only explicitly simulated serial connections and port listings."""

    def __init__(self) -> None:
        self.attempts: list[tuple[str, dict]] = []
        self.sessions: dict[str, list[SerialWriter]] = {}
        self.open_errors: dict[str, Exception] = {}
        self.ports: list[SerialPortInfo] = []
        self.list_error: OSError | None = None

    async def open(self, *, url: str, **settings) -> tuple[SerialReader, SerialWriter]:
        self.attempts.append((url, settings))
        if url in self.open_errors:
            raise self.open_errors[url]
        sessions = self.sessions.setdefault(url, [])
        if sessions and not sessions[-1].closed:
            raise OSError(f"Serial port {url} is already open")
        reader = SerialReader()
        writer = SerialWriter(reader)
        sessions.append(writer)
        return reader, writer

    async def list(self) -> list[SerialPortInfo]:
        if self.list_error is not None:
            raise self.list_error
        return self.ports


@pytest.fixture
def serial_ports(monkeypatch):
    ports = SerialPorts()
    monkeypatch.setattr(client, "open_serial_connection", ports.open)
    monkeypatch.setattr(config_flow, "async_list_serial_ports", ports.list)
    return ports


@pytest.fixture
async def hass(tmp_path, serial_ports):
    """Initialize HA's loader, entry manager, registries, and state storage."""
    instance = HomeAssistant(str(tmp_path))
    instance.config.skip_pip = True
    loader.async_setup(instance)
    entity.async_setup(instance)
    translation.async_setup(instance)
    await device_registry.async_load(instance)
    await issue_registry.async_load(instance)
    instance.config_entries = ConfigEntries(instance, {})
    await instance.config_entries.async_initialize()
    await entity_registry.async_load(instance)
    await restore_state.async_load(instance)
    try:
        yield instance
    finally:
        for entry in instance.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.LOADED:
                await instance.config_entries.async_unload(entry.entry_id)
        await instance.async_stop(force=True)


@pytest.fixture
def add_entry(hass):
    async def create(
        port="test-kvm",
        *,
        title="Desk KVM",
        settings=None,
        disabled=False,
        domain=DOMAIN,
    ) -> ConfigEntry:
        entry = ConfigEntry(
            domain=domain,
            title=title,
            data={"device": port, **(settings or {})},
            options={},
            source="user",
            unique_id=port,
            version=1,
            minor_version=1,
            discovery_keys=MappingProxyType({}),
            disabled_by=ConfigEntryDisabler.USER if disabled else None,
        )
        await hass.config_entries.async_add(entry)
        return entry

    return create
