"""Entity behavior against Home Assistant's real entity classes."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import pytest_asyncio

from custom_components.connectpro import (
    PLATFORMS,
    button,
    select,
    sensor,
    switch,
)
from custom_components.connectpro.button import (
    ConnectProResetButton,
    ConnectProRoutingSyncButton,
)
from custom_components.connectpro.const import DOMAIN
from custom_components.connectpro.entity import ConnectProEntity
from custom_components.connectpro.select import (
    ConnectProAutoScanSelect,
    ConnectProChannelSelect,
    ConnectProHotkeySelect,
)
from custom_components.connectpro.sensor import ConnectProSensor
from custom_components.connectpro.switch import (
    ConnectProBuzzerSwitch,
    ConnectProMouseChannelSwitch,
)
from homeassistant.const import EntityCategory, Platform
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
@pytest.mark.parametrize("initial_state", [None, "Ctrl"])
@pytest.mark.parametrize(
    ("option", "command"),
    [
        ("Ctrl", "ctrl"),
        ("Shift", "shift"),
        ("Scroll Lock", "scroll"),
        ("Caps Lock", "caps"),
    ],
)
async def test_hotkey_selection_sends_tested_commands_and_waits_for_feedback(
    entry: SimpleNamespace,
    client: FakeClient,
    initial_state: str | None,
    option: str,
    command: str,
) -> None:
    """Exact lowercase commands never optimistically replace observed state."""
    if initial_state is not None:
        client.state["hotkey"] = initial_state
    entity = ConnectProHotkeySelect(entry)
    assert entity.options == ["Ctrl", "Shift", "Scroll Lock", "Caps Lock"]
    assert entity.current_option == initial_state

    await entity.async_select_option(option)

    assert client.commands == [command]
    assert entity.current_option == initial_state
    client.state["hotkey"] = option
    assert entity.current_option == option


@pytest.mark.asyncio
async def test_hotkey_change_back_before_feedback_is_not_dropped(
    entry: SimpleNamespace, client: FakeClient
) -> None:
    """A request matching stale feedback still follows the intervening request."""
    client.state["hotkey"] = "Ctrl"
    entity = ConnectProHotkeySelect(entry)

    await entity.async_select_option("Shift")
    await entity.async_select_option("Ctrl")

    assert client.commands == ["shift", "ctrl"]
    assert entity.current_option == "Ctrl"


@pytest.mark.asyncio
@pytest.mark.parametrize("option", ["ctrl", "CTRL", "Scroll", "Alt", "", "shift\r\n"])
async def test_hotkey_rejects_invalid_options_without_writing(
    entry: SimpleNamespace, client: FakeClient, option: str
) -> None:
    """Only the four supported options can produce a hotkey command."""
    with pytest.raises(ServiceValidationError, match="Unsupported ConnectPro hotkey"):
        await ConnectProHotkeySelect(entry).async_select_option(option)
    assert client.commands == []


@pytest.mark.parametrize("value", ["ALT", "CTRL", "", True, False])
def test_hotkey_unrecognized_state_remains_unknown(
    entry: SimpleNamespace, client: FakeClient, value: str | bool
) -> None:
    """Unsupported observed values are not exposed as selectable options."""
    client.state["hotkey"] = value
    assert ConnectProHotkeySelect(entry).current_option is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "option"),
    [
        (ConnectProChannelSelect, "Channel 3"),
        (ConnectProHotkeySelect, "Shift"),
        (ConnectProAutoScanSelect, "8 seconds"),
    ],
)
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
    entity_type: type,
    option: str,
    error: Exception,
    expected_type: type[HomeAssistantError],
) -> None:
    """Transport failures reach callers without optimistic state changes."""
    client.send_error = error
    entity = entity_type(entry)

    with pytest.raises(expected_type, match=str(error)) as raised:
        await entity.async_select_option(option)

    assert raised.value.__cause__ is error
    assert entity.current_option is None
    assert client.commands == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("option", "command"),
    [
        ("Off", "s0"),
        ("5 seconds", "s1"),
        ("8 seconds", "s2"),
        ("15 seconds", "s3"),
        ("20 seconds", "s4"),
        ("30 seconds", "s5"),
    ],
)
async def test_auto_scan_sends_tested_commands_and_waits_for_feedback(
    entry: SimpleNamespace, client: FakeClient, option: str, command: str
) -> None:
    """Every valid selection sends its exact command without optimistic state."""
    client.state.update({"auto_scan": True, "auto_scan_interval": "5 seconds"})
    entity = ConnectProAutoScanSelect(entry)
    assert entity.options == [
        "Off",
        "5 seconds",
        "8 seconds",
        "15 seconds",
        "20 seconds",
        "30 seconds",
    ]
    before = client.state.copy()

    await entity.async_select_option(option)

    assert client.commands == [command]
    assert client.state == before
    assert entity.current_option == "5 seconds"
    client.state["auto_scan"] = option != "Off"
    if option != "Off":
        client.state["auto_scan_interval"] = option
    assert entity.current_option == option


@pytest.mark.parametrize(
    ("observed_state", "expected"),
    [
        ({}, None),
        ({"auto_scan": True}, None),
        ({"auto_scan_interval": "5 seconds"}, None),
        ({"auto_scan": False, "auto_scan_interval": "8 seconds"}, "Off"),
        ({"auto_scan": True, "auto_scan_interval": "15 seconds"}, "15 seconds"),
        ({"auto_scan": True, "auto_scan_interval": "Off"}, None),
        ({"auto_scan": True, "auto_scan_interval": "1 minute"}, None),
    ],
)
def test_auto_scan_requires_explicit_scan_state_and_recognized_timing(
    entry: SimpleNamespace,
    client: FakeClient,
    observed_state: dict[str, str | bool],
    expected: str | None,
) -> None:
    """Partial feedback remains unknown; explicit Off overrides cached timing."""
    client.state.update(observed_state)
    assert ConnectProAutoScanSelect(entry).current_option == expected
    assert client.commands == []


@pytest.mark.asyncio
async def test_auto_scan_change_back_before_feedback_is_not_dropped(
    entry: SimpleNamespace, client: FakeClient
) -> None:
    """A stale reported interval never suppresses the latest request."""
    client.state.update({"auto_scan": True, "auto_scan_interval": "5 seconds"})
    entity = ConnectProAutoScanSelect(entry)

    await entity.async_select_option("8 seconds")
    await entity.async_select_option("5 seconds")

    assert client.commands == ["s2", "s1"]
    assert entity.current_option == "5 seconds"


@pytest.mark.asyncio
@pytest.mark.parametrize("option", ["On", "off", "5", "6 seconds", ""])
async def test_auto_scan_rejects_unconfirmed_options(
    entry: SimpleNamespace, client: FakeClient, option: str
) -> None:
    """Invalid names cannot produce guessed timing commands."""
    with pytest.raises(
        ServiceValidationError, match="Unsupported ConnectPro scan setting"
    ):
        await ConnectProAutoScanSelect(entry).async_select_option(option)
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


@pytest.mark.asyncio
@pytest.mark.parametrize("has_observed_state", [False, True])
@pytest.mark.parametrize(
    ("key", "command"),
    [
        ("sync_audio", "o0"),
        ("sync_usb_hubs", "h0p0"),
        ("sync_video1", "v1p0"),
        ("sync_video_outputs", "v0p0"),
    ],
)
async def test_routing_sync_buttons_send_exact_scoped_command_without_state_changes(
    entry: SimpleNamespace,
    client: FakeClient,
    has_observed_state: bool,
    key: str,
    command: str,
) -> None:
    """Each button sends only its tested command, preserving unknown/observed state."""
    if has_observed_state:
        client.state.update(
            {
                "audio": "Channel 1",
                "hub1": "Channel 2",
                "hub2": "Sync",
                "video1": "Channel 2",
            }
        )
    before = client.state.copy()
    entity = ConnectProRoutingSyncButton(entry, key)

    await entity.async_press()

    assert client.commands == [command]
    assert client.state == before
    assert entity.unique_id == f"entry-1_{key}"
    assert entity.translation_key == key
    assert entity.entity_category is EntityCategory.CONFIG
    assert entity.entity_registry_enabled_default is True
    assert entity.device_class is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key", ["sync_audio", "sync_usb_hubs", "sync_video1", "sync_video_outputs"]
)
@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (ConnectionError("disconnected"), HomeAssistantError),
        (OSError("write failed"), HomeAssistantError),
        (TimeoutError("write timed out"), HomeAssistantError),
        (ValueError("invalid command"), ServiceValidationError),
    ],
)
async def test_routing_sync_failure_surfaces_without_changing_state(
    entry: SimpleNamespace,
    client: FakeClient,
    key: str,
    error: Exception,
    expected_type: type[HomeAssistantError],
) -> None:
    """A failed sync action preserves every routing observation."""
    client.state.update(
        {
            "audio": "Channel 1",
            "hub1": "Channel 2",
            "hub2": "Sync",
            "video1": "Channel 2",
        }
    )
    before = client.state.copy()
    client.send_error = error

    with pytest.raises(expected_type, match=str(error)) as raised:
        await ConnectProRoutingSyncButton(entry, key).async_press()

    assert raised.value.__cause__ is error
    assert client.state == before
    assert client.commands == []


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_state", [None, False, True])
@pytest.mark.parametrize(
    ("entity_type", "state_key", "action", "command", "reported_state"),
    [
        (ConnectProBuzzerSwitch, "buzzer", "async_turn_on", "BZON", True),
        (ConnectProBuzzerSwitch, "buzzer", "async_turn_off", "BZOFF", False),
        (
            ConnectProMouseChannelSwitch,
            "mouse_change_channel",
            "async_turn_on",
            "M1",
            True,
        ),
        (
            ConnectProMouseChannelSwitch,
            "mouse_change_channel",
            "async_turn_off",
            "M0",
            False,
        ),
    ],
)
async def test_switch_waits_for_feedback_even_when_request_matches_state(
    entry: SimpleNamespace,
    client: FakeClient,
    entity_type: type,
    state_key: str,
    initial_state: bool | None,
    action: str,
    command: str,
    reported_state: bool,
) -> None:
    """Every request sends its command; only received state changes the switch."""
    if initial_state is not None:
        client.state[state_key] = initial_state
    entity = entity_type(entry)
    assert entity.is_on is initial_state

    await getattr(entity, action)()

    assert client.commands == [command]
    assert entity.is_on is initial_state
    client.state[state_key] = reported_state
    assert entity.is_on is reported_state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "state_key"),
    [
        (ConnectProBuzzerSwitch, "buzzer"),
        (ConnectProMouseChannelSwitch, "mouse_change_channel"),
    ],
)
@pytest.mark.parametrize("action", ["async_turn_on", "async_turn_off"])
@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (ConnectionError("disconnected"), HomeAssistantError),
        (OSError("write failed"), HomeAssistantError),
        (TimeoutError("write timed out"), HomeAssistantError),
        (ValueError("invalid command"), ServiceValidationError),
    ],
)
async def test_switch_surfaces_command_failures_without_changing_state(
    entry: SimpleNamespace,
    client: FakeClient,
    entity_type: type,
    state_key: str,
    action: str,
    error: Exception,
    expected_type: type[HomeAssistantError],
) -> None:
    """A failed switch request preserves observed state and reaches the caller."""
    client.state[state_key] = False
    client.send_error = error
    entity = entity_type(entry)

    with pytest.raises(expected_type, match=str(error)) as raised:
        await getattr(entity, action)()

    assert raised.value.__cause__ is error
    assert entity.is_on is False
    assert client.commands == []


@pytest.mark.parametrize(
    ("entity_type", "key"),
    [
        (ConnectProAutoScanSelect, "auto_scan"),
        (ConnectProHotkeySelect, "hotkey"),
        (ConnectProBuzzerSwitch, "buzzer"),
        (ConnectProMouseChannelSwitch, "mouse_change_channel"),
    ],
)
def test_setting_controls_are_enabled_configuration_entities(
    entry: SimpleNamespace, entity_type: type, key: str
) -> None:
    """Controls belong to the shared device and expose configuration settings."""
    control = entity_type(entry)

    assert control.unique_id == f"entry-1_{key}"
    assert control.translation_key == key
    assert control.entity_category is EntityCategory.CONFIG
    assert control.entity_registry_enabled_default is True


@pytest.mark.asyncio
async def test_mouse_switch_change_back_before_feedback_is_not_dropped(
    entry: SimpleNamespace, client: FakeClient
) -> None:
    """Turning off again must follow the pending on request, despite stale off state."""
    client.state["mouse_change_channel"] = False
    entity = ConnectProMouseChannelSwitch(entry)

    await entity.async_turn_on()
    await entity.async_turn_off()

    assert client.commands == ["M1", "M0"]
    assert entity.is_on is False


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("audio", "Sync"),
        ("audio", "Channel 1"),
        ("hub1", "Sync"),
        ("hub1", "Channel 2"),
        ("hub2", "Sync"),
        ("video1", "Sync"),
        ("video1", "Channel 2"),
    ],
)
def test_text_sensors_expose_only_observed_values(
    entry: SimpleNamespace, client: FakeClient, key: str, value: str
) -> None:
    """Routing sensors show received values without sending commands."""
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
    platforms = {
        Platform.SELECT: select,
        Platform.BUTTON: button,
        Platform.SENSOR: sensor,
        Platform.SWITCH: switch,
    }
    assert set(PLATFORMS) == set(platforms)
    entities_by_platform = {}
    for domain, platform in platforms.items():
        entities_by_platform[domain] = []
        await platform.async_setup_entry(
            hass, entry, entities_by_platform[domain].extend
        )

    expected_keys = {
        Platform.SELECT: {"channel", "hotkey", "auto_scan"},
        Platform.BUTTON: {
            "reset",
            "sync_audio",
            "sync_usb_hubs",
            "sync_video1",
            "sync_video_outputs",
        },
        Platform.SENSOR: {"audio", "hub1", "hub2", "video1"},
        Platform.SWITCH: {"buzzer", "mouse_change_channel"},
    }
    identities = []
    for domain, platform_entities in entities_by_platform.items():
        assert len(platform_entities) == len(expected_keys[domain])
        assert {
            entity.translation_key for entity in platform_entities
        } == expected_keys[domain]
        assert {entity.unique_id for entity in platform_entities} == {
            f"entry-1_{key}" for key in expected_keys[domain]
        }
        identities.extend((domain, entity.unique_id) for entity in platform_entities)
    assert len(set(identities)) == len(identities)
    entities = [
        entity
        for platform_entities in entities_by_platform.values()
        for entity in platform_entities
    ]
    assert len(entities) == 14
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


@pytest.mark.parametrize("model", [None, "", False, "UDP2-14AP"])
def test_device_info_includes_only_reported_model_metadata(
    entry: SimpleNamespace, client: FakeClient, model: str | bool | None
) -> None:
    """Entities created after detection include the model without a default guess."""
    if model is not None:
        client.state["model"] = model
    device_info = ConnectProChannelSelect(entry).device_info
    if model == "UDP2-14AP":
        assert device_info["model"] == "UDP2-14AP"
    else:
        assert "model" not in device_info


def test_delayed_model_is_included_without_entity_subscription(
    entry: SimpleNamespace, client: FakeClient
) -> None:
    """DeviceInfo follows reported metadata even before an entity is registered."""
    entity = ConnectProChannelSelect(entry)
    assert "model" not in entity.device_info
    client.state["model"] = "UDP2-14AP"
    assert entity.device_info["model"] == "UDP2-14AP"
    client.state.clear()
    assert "model" not in entity.device_info
    assert client.listeners == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_factory", "entity_id"),
    [
        (ConnectProChannelSelect, "select.connectpro_channel"),
        (ConnectProHotkeySelect, "select.connectpro_hotkey"),
        (ConnectProAutoScanSelect, "select.connectpro_auto_scan"),
        (ConnectProBuzzerSwitch, "switch.connectpro_buzzer"),
        (ConnectProMouseChannelSwitch, "switch.connectpro_mouse_channel_switching"),
        (
            lambda entry: ConnectProSensor(entry, "video1"),
            "sensor.connectpro_video1_routing",
        ),
    ],
)
async def test_entity_listener_updates_state_and_unsubscribes_on_removal(
    hass: HomeAssistant,
    entry: SimpleNamespace,
    client: FakeClient,
    entity_factory: Callable[[SimpleNamespace], ConnectProEntity],
    entity_id: str,
) -> None:
    """Serial updates publish state only while the entity is registered."""
    entity = entity_factory(entry)
    entity.hass = hass
    entity.entity_id = entity_id
    assert client.listeners == []

    with patch.object(entity, "async_write_ha_state", new=Mock()) as write_state:
        await entity.async_added_to_hass()
        assert len(client.listeners) == 1

        client.state.update(
            {
                "channel": "Channel 3",
                "hotkey": "Shift",
                "auto_scan": True,
                "auto_scan_interval": "8 seconds",
                "buzzer": True,
                "mouse_change_channel": True,
                "video1": "Channel 2",
            }
        )
        client.notify()
        write_state.assert_called_once_with()

        client.connected = False
        client.notify()
        assert not entity.available
        assert write_state.call_count == 2

        await entity.async_remove(force_remove=True)
        assert client.listeners == []
        client.notify()
        assert write_state.call_count == 2
