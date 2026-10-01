"""Entity behavior against Home Assistant's real entity classes."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import pytest_asyncio

from custom_components.connectpro import binary_sensor, button, select, sensor
from custom_components.connectpro.binary_sensor import ConnectProBinarySensor
from custom_components.connectpro.button import ConnectProResetButton
from custom_components.connectpro.const import DOMAIN
from custom_components.connectpro.select import ConnectProChannelSelect
from custom_components.connectpro.sensor import ConnectProSensor
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


@dataclass
class FakeClient:
    """Provide the serial client's state and subscription contract."""

    connected: bool = True
    state: dict[str, str | bool] = field(default_factory=dict)
    commands: list[str] = field(default_factory=list)
    listeners: list[Callable[[], None]] = field(default_factory=list)
    send_error: Exception | None = None

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Record a subscription and return its cleanup callback."""
        self.listeners.append(callback)

        def unsubscribe() -> None:
            self.listeners.remove(callback)

        return unsubscribe

    async def async_send_command(self, command: str) -> None:
        """Record a command or simulate a transport error."""
        if self.send_error is not None:
            raise self.send_error
        self.commands.append(command)

    def notify(self) -> None:
        """Deliver an observed state or connection update."""
        for callback in tuple(self.listeners):
            callback()


@pytest.fixture
def client() -> FakeClient:
    """Return a connected client without observed state."""
    return FakeClient()


@pytest.fixture
def entry(client: FakeClient) -> SimpleNamespace:
    """Return only the config entry fields the entities consume."""
    return SimpleNamespace(entry_id="entry-1", title="Desktop KVM", runtime_data=client)


@pytest_asyncio.fixture
async def hass(tmp_path: Path) -> AsyncGenerator[HomeAssistant]:
    """Provide Home Assistant for entity lifecycle cleanup."""
    instance = HomeAssistant(str(tmp_path))
    try:
        yield instance
    finally:
        await instance.async_stop(force=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("channel", range(1, 5))
async def test_channel_selection_waits_for_observed_state(
    entry: SimpleNamespace, client: FakeClient, channel: int
) -> None:
    """Commands use the confirmed spelling without changing cached state."""
    entity = ConnectProChannelSelect(entry)
    assert entity.options == ["Channel 1", "Channel 2", "Channel 3", "Channel 4"]
    assert entity.current_option is None

    await entity.async_select_option(f"Channel {channel}")

    assert client.commands == [f"Ch{channel}"]
    assert entity.current_option is None
    client.state["channel"] = f"Channel {channel}"
    assert entity.current_option == f"Channel {channel}"


@pytest.mark.asyncio
async def test_channel_change_back_before_confirmation_is_not_dropped(
    entry: SimpleNamespace, client: FakeClient
) -> None:
    """The latest selection wins even when it equals a stale observed channel."""
    client.state["channel"] = "Channel 2"
    entity = ConnectProChannelSelect(entry)

    await entity.async_select_option("Channel 3")
    await entity.async_select_option("Channel 2")
    assert client.commands == ["Ch3", "Ch2"]
    assert entity.current_option == "Channel 2"


@pytest.mark.asyncio
@pytest.mark.parametrize("option", ["Channel 0", "Channel 5", "channel 1", "Ch1", ""])
async def test_channel_rejects_invalid_options_without_writing(
    entry: SimpleNamespace, client: FakeClient, option: str
) -> None:
    """Invalid options never become arbitrary serial commands."""
    with pytest.raises(ServiceValidationError, match="Unsupported ConnectPro channel"):
        await ConnectProChannelSelect(entry).async_select_option(option)
    assert client.commands == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (ConnectionError("disconnected"), HomeAssistantError),
        (OSError("write failed"), HomeAssistantError),
        (TimeoutError("write timed out"), HomeAssistantError),
        (ValueError("invalid command"), ServiceValidationError),
    ],
)
async def test_command_errors_are_exposed_as_home_assistant_errors(
    entry: SimpleNamespace,
    client: FakeClient,
    error: Exception,
    expected_type: type[HomeAssistantError],
) -> None:
    """Transport failures reach callers without optimistic state changes."""
    client.send_error = error
    entity = ConnectProChannelSelect(entry)

    with pytest.raises(expected_type, match=str(error)) as raised:
        await entity.async_select_option("Channel 3")

    assert raised.value.__cause__ is error
    assert entity.current_option is None
    assert client.commands == []


@pytest.mark.asyncio
async def test_reset_button_sends_exact_command(
    entry: SimpleNamespace, client: FakeClient
) -> None:
    """The reset button preserves the existing W0 control."""
    entity = ConnectProResetButton(entry)
    await entity.async_press()
    assert client.commands == ["W0"]
    assert entity.entity_category is EntityCategory.CONFIG
    assert entity.entity_registry_enabled_default is True
    assert entity.device_class is None


@pytest.mark.parametrize("key", ["buzzer", "mouse_change_channel"])
def test_binary_sensors_distinguish_unknown_off_and_on(
    entry: SimpleNamespace, client: FakeClient, key: str
) -> None:
    """An unobserved setting remains unknown instead of defaulting to off."""
    entity = ConnectProBinarySensor(entry, key)
    assert entity.is_on is None
    client.state[key] = False
    assert entity.is_on is False
    client.state[key] = True
    assert entity.is_on is True


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("hotkey", "Ctrl"),
        ("hotkey", "Shift"),
        ("hotkey", "Scroll Lock"),
        ("hotkey", "Caps Lock"),
        ("audio", "Sync"),
        ("hub1", "Sync"),
        ("hub2", "Sync"),
    ],
)
def test_text_sensors_expose_only_observed_values(
    entry: SimpleNamespace, client: FakeClient, key: str, value: str
) -> None:
    """Hotkey and routing observations are available without write controls."""
    entity = ConnectProSensor(entry, key)
    assert entity.native_value is None
    client.state[key] = value
    assert entity.native_value == value
    assert client.commands == []


@pytest.mark.asyncio
async def test_platforms_share_device_identity_and_connection_availability(
    hass: HomeAssistant, entry: SimpleNamespace, client: FakeClient
) -> None:
    """Every platform adds the expected entities for one KVM device."""
    entities = []
    for platform in (select, button, binary_sensor, sensor):
        await platform.async_setup_entry(hass, entry, entities.extend)

    keys = {
        "channel",
        "reset",
        "buzzer",
        "mouse_change_channel",
        "hotkey",
        "audio",
        "hub1",
        "hub2",
    }
    assert len(entities) == len(keys)
    assert {entity.translation_key for entity in entities} == keys
    assert {entity.unique_id for entity in entities} == {
        f"entry-1_{key}" for key in keys
    }
    for entity in entities:
        assert entity.has_entity_name is True
        assert entity.should_poll is False
        assert entity.available is True
        assert entity.device_info == {
            "identifiers": {(DOMAIN, "entry-1")},
            "manufacturer": "ConnectPro",
            "name": "Desktop KVM",
        }

    client.connected = False
    assert all(not entity.available for entity in entities)
    client.connected = True
    assert all(entity.available for entity in entities)


def test_device_name_falls_back_when_entry_title_is_empty(
    entry: SimpleNamespace,
) -> None:
    """An untitled entry still has a usable device name."""
    entry.title = ""
    assert ConnectProChannelSelect(entry).device_info["name"] == "ConnectPro KVM"


@pytest.mark.asyncio
async def test_entity_listener_updates_state_and_unsubscribes_on_removal(
    hass: HomeAssistant, entry: SimpleNamespace, client: FakeClient
) -> None:
    """Serial updates publish state only while the entity is registered."""
    entity = ConnectProChannelSelect(entry)
    entity.hass = hass
    entity.entity_id = "select.connectpro_channel"
    assert client.listeners == []

    with patch.object(entity, "async_write_ha_state", new=Mock()) as write_state:
        await entity.async_added_to_hass()
        assert len(client.listeners) == 1

        client.state["channel"] = "Channel 3"
        client.notify()
        assert entity.current_option == "Channel 3"
        write_state.assert_called_once_with()

        client.connected = False
        client.notify()
        assert not entity.available
        assert write_state.call_count == 2

        await entity.async_remove(force_remove=True)
        assert client.listeners == []
        client.notify()
        assert write_state.call_count == 2
