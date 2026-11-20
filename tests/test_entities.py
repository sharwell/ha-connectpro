"""Observe ConnectPro through HA services, state, events, and registries."""

import asyncio

import pytest

from custom_components.connectpro.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

STARTUP_QUERY = b"k1p0\r\n"
CHANNELS = [f"Channel {n}" for n in range(1, 5)]
HOTKEYS = [
    ("Ctrl", b"ctrl", b"Hot KEY : CTRL"),
    ("Shift", b"shift", b"Hot KEY : SHIFT"),
    ("Scroll Lock", b"scroll", b"Hot KEY : SCROLL"),
    ("Caps Lock", b"caps", b"Hot KEY : CAPS"),
]
SCAN_SETTINGS = [
    ("Off", b"s0", b"Auto Scan : OFF"),
    ("5 seconds", b"s1", b"Auto Scan : ON\r\nAuto Scan : 1(5sec)"),
    ("8 seconds", b"s2", b"Auto Scan : ON\r\nAuto Scan : 2(8Sec)"),
    ("15 seconds", b"s3", b"Auto Scan : ON\r\nAuto Scan : 3(15Sec)"),
    ("20 seconds", b"s4", b"Auto Scan : ON\r\nAuto Scan : 4(20Sec)"),
    ("30 seconds", b"s5", b"Auto Scan : ON\r\nAuto Scan : 5(30Sec)"),
]
# Request and reply spellings are protocol expectations, independent of
# the integration's command lookup tables and parser.
ROUTES = [
    ("audio", "o", "AUDIO : CHANNEL{}", "AUDIO : Sync"),
    ("video1", "v1p", "Video1 : ASYNC-mode-Port{}", "Video1 : SYNC-mode"),
    ("video2", "v2p", "Video2 : ASYNC-mode-Port{}", "Video2 : SYNC-mode"),
    ("hub1", "h1p", "HUB1 : Async-> Channel {}", "HUB1 : Sync"),
    ("hub2", "h2p", "HUB2 : Async-> Channel {}", "HUB2 : Sync"),
]
SWITCHES = [
    ("buzzer", b"BZON", b"BZOFF", b"BZON", b"BZOFF"),
    (
        "mouse_change_channel",
        b"M1",
        b"M0",
        b"Mouse change channel : ON",
        b"Mouse change channel : OFF",
    ),
]


@pytest.fixture
async def kvm(hass, add_entry, serial_ports):
    entry = await add_entry()
    assert entry.state is ConfigEntryState.LOADED, entry.reason
    (port,) = serial_ports.sessions["test-kvm"]
    await asyncio.wait_for(port.reader.reading.wait(), 2)
    return entry, port


def find_entity(hass, entry, domain, key):
    entity_id = er.async_get(hass).async_get_entity_id(
        domain, DOMAIN, f"{entry.entry_id}_{key}"
    )
    assert entity_id is not None, f"Missing {domain} entity for {key}"
    return entity_id


def state(hass, entity_id):
    return hass.states.get(entity_id).state


async def call(hass, entity_id, action, **data):
    domain = entity_id.split(".", 1)[0]
    await hass.services.async_call(
        domain, action, {"entity_id": entity_id, **data}, blocking=True
    )


@pytest.mark.parametrize("channel", range(1, 5))
async def test_channel_selection_waits_for_feedback(hass, kvm, channel):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "select", "channel")
    assert hass.states.get(entity_id).attributes["options"] == CHANNELS
    assert state(hass, entity_id) == STATE_UNKNOWN

    await call(hass, entity_id, "select_option", option=f"Channel {channel}")

    assert port.writes == [STARTUP_QUERY, f"Ch{channel}\r\n".encode()]
    assert state(hass, entity_id) == STATE_UNKNOWN
    await port.reader.receive(f"CH-{channel}\r\n".encode())
    assert state(hass, entity_id) == f"Channel {channel}"


@pytest.mark.parametrize(("option", "command", "reply"), HOTKEYS)
@pytest.mark.parametrize("initial", [STATE_UNKNOWN, "Ctrl"])
async def test_hotkey_waits_for_reported_mode(
    hass, kvm, option, command, reply, initial
):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "select", "hotkey")
    assert hass.states.get(entity_id).attributes["options"] == [
        row[0] for row in HOTKEYS
    ]
    if initial == "Ctrl":
        await port.reader.receive(b"Hot KEY : CTRL\r\n")
    assert state(hass, entity_id) == initial

    await call(hass, entity_id, "select_option", option=option)

    assert port.writes == [STARTUP_QUERY, command + b"\r\n"]
    assert state(hass, entity_id) == initial
    await port.reader.receive(reply + b"\r\n")
    assert state(hass, entity_id) == option


@pytest.mark.parametrize(("option", "command", "reply"), SCAN_SETTINGS)
async def test_scan_selection_waits_for_feedback(hass, kvm, option, command, reply):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "select", "auto_scan")
    assert hass.states.get(entity_id).attributes["options"] == [
        row[0] for row in SCAN_SETTINGS
    ]
    await port.reader.receive(b"Auto Scan : ON\r\nAuto Scan : 1(5sec)\r\n")

    await call(hass, entity_id, "select_option", option=option)

    assert port.writes == [STARTUP_QUERY, command + b"\r\n"]
    assert state(hass, entity_id) == "5 seconds"
    await port.reader.receive(reply + b"\r\n")
    assert state(hass, entity_id) == option


@pytest.mark.parametrize(
    ("feedback", "expected"),
    [
        (b"Auto Scan : ON", STATE_UNKNOWN),
        (b"Auto Scan : 1(5sec)", STATE_UNKNOWN),
        (b"Auto Scan : 2(8Sec)\r\nAuto Scan : OFF", "Off"),
        (b"Auto Scan : ON\r\nAuto Scan : 3(15Sec)", "15 seconds"),
        (b"Auto Scan : ON\r\nAuto Scan : 6(1Min)", STATE_UNKNOWN),
    ],
)
async def test_scan_needs_explicit_enabled_state_and_supported_interval(
    hass, kvm, feedback, expected
):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "select", "auto_scan")

    await port.reader.receive(feedback + b"\r\n")

    assert state(hass, entity_id) == expected
    assert port.writes == [STARTUP_QUERY]


@pytest.mark.parametrize(
    ("key", "invalid"),
    [
        ("channel", ["Channel 0", "Channel 5", "channel 1", "Ch1", ""]),
        ("hotkey", ["ctrl", "CTRL", "Scroll", "Alt", "", "shift\r\n"]),
        ("auto_scan", ["On", "off", "5", "6 seconds", ""]),
        ("audio", ["Channel 0"]),
        ("video1", ["Channel 5"]),
        ("video2", ["sync"]),
        ("hub1", ["Ch2"]),
        ("hub2", [""]),
    ],
)
async def test_select_service_rejects_unsupported_options_without_writing(
    hass, kvm, key, invalid
):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "select", key)

    for option in invalid:
        with pytest.raises(ServiceValidationError, match="option"):
            await call(hass, entity_id, "select_option", option=option)

    assert port.writes == [STARTUP_QUERY]
    assert state(hass, entity_id) == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("key", "feedback", "initial", "intervening", "commands"),
    [
        ("channel", b"CH-2", "Channel 2", "Channel 3", [b"Ch3", b"Ch2"]),
        ("hotkey", b"Hot KEY : CTRL", "Ctrl", "Shift", [b"shift", b"ctrl"]),
        (
            "auto_scan",
            b"Auto Scan : ON\r\nAuto Scan : 1(5sec)",
            "5 seconds",
            "8 seconds",
            [b"s2", b"s1"],
        ),
        (
            "video2",
            b"Video2 : ASYNC-mode-Port2",
            "Channel 2",
            "Channel 3",
            [b"v2p3", b"v2p2"],
        ),
    ],
)
async def test_select_accepts_a_request_matching_stale_feedback(
    hass, kvm, key, feedback, initial, intervening, commands
):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "select", key)
    await port.reader.receive(feedback + b"\r\n")

    await call(hass, entity_id, "select_option", option=intervening)
    await call(hass, entity_id, "select_option", option=initial)

    assert port.writes == [STARTUP_QUERY, *(command + b"\r\n" for command in commands)]
    assert state(hass, entity_id) == initial


@pytest.mark.parametrize(("key", "prefix", "reply", "sync"), ROUTES)
@pytest.mark.parametrize("channel", range(1, 5))
async def test_routing_select_waits_for_feedback(
    hass, kvm, key, prefix, reply, sync, channel
):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "select", key)
    assert hass.states.get(entity_id).attributes["options"] == ["Sync", *CHANNELS]
    assert state(hass, entity_id) == STATE_UNKNOWN
    await port.reader.receive(reply.format(5).encode() + b"\r\n")
    assert state(hass, entity_id) == STATE_UNKNOWN
    await port.reader.receive(sync.encode() + b"\r\n")

    await call(hass, entity_id, "select_option", option=f"Channel {channel}")

    assert port.writes == [STARTUP_QUERY, f"{prefix}{channel}\r\n".encode()]
    assert state(hass, entity_id) == "Sync"
    await port.reader.receive(reply.format(channel).encode() + b"\r\n")
    assert state(hass, entity_id) == f"Channel {channel}"


@pytest.mark.parametrize(("key", "prefix", "reply", "sync"), ROUTES[:3])
async def test_audio_and_video_can_request_independent_sync(
    hass, kvm, key, prefix, reply, sync
):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "select", key)
    await port.reader.receive(reply.format(2).encode() + b"\r\n")

    await call(hass, entity_id, "select_option", option="Sync")

    assert port.writes == [STARTUP_QUERY, f"{prefix}0\r\n".encode()]
    assert state(hass, entity_id) == "Channel 2"
    await port.reader.receive(sync.encode() + b"\r\n")
    assert state(hass, entity_id) == "Sync"


@pytest.mark.parametrize(("key", "prefix", "reply", "sync"), ROUTES[3:])
@pytest.mark.parametrize("observed", ["Sync", "Channel 2"])
async def test_hub_can_report_sync_but_rejects_request_for_independent_sync(
    hass, kvm, key, prefix, reply, sync, observed
):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "select", key)
    feedback = sync if observed == "Sync" else reply.format(2)
    await port.reader.receive(feedback.encode() + b"\r\n")

    with pytest.raises(ServiceValidationError, match="Sync both USB hubs"):
        await call(hass, entity_id, "select_option", option="Sync")

    assert port.writes == [STARTUP_QUERY]
    assert state(hass, entity_id) == observed


@pytest.mark.parametrize("observed", [False, True])
async def test_shared_sync_writes_once_and_only_feedback_changes_hubs(
    hass, kvm, observed
):
    entry, port = kvm
    hub1 = find_entity(hass, entry, "select", "hub1")
    hub2 = find_entity(hass, entry, "select", "hub2")
    audio = find_entity(hass, entry, "select", "audio")
    if observed:
        await port.reader.receive(
            b"HUB1 : Async-> Channel 2\r\nHUB2 : Async-> Channel 3\r\nAUDIO : CHANNEL1\r\n"
        )
    previous = [state(hass, entity_id) for entity_id in (hub1, hub2, audio)]

    await call(hass, find_entity(hass, entry, "button", "sync_usb_hubs"), "press")

    assert port.writes == [STARTUP_QUERY, b"h0p0\r\n"]
    assert [state(hass, entity_id) for entity_id in (hub1, hub2, audio)] == previous
    await port.reader.receive(b"HUB1 : Sync\r\nHUB2 : Sync\r\n")
    assert [state(hass, entity_id) for entity_id in (hub1, hub2, audio)] == [
        "Sync",
        "Sync",
        previous[2],
    ]


async def test_reset_writes_w0_without_changing_channel(hass, kvm):
    entry, port = kvm
    channel = find_entity(hass, entry, "select", "channel")
    await port.reader.receive(b"CH-2\r\n")

    await call(hass, find_entity(hass, entry, "button", "reset"), "press")

    assert port.writes == [STARTUP_QUERY, b"W0\r\n"]
    await port.reader.receive(b"Wake-Up : DP-ALL\r\n")
    assert state(hass, channel) == "Channel 2"


@pytest.mark.parametrize(("key", "on", "off", "report_on", "report_off"), SWITCHES)
@pytest.mark.parametrize("initial", [STATE_UNKNOWN, STATE_OFF, STATE_ON])
@pytest.mark.parametrize("requested", [STATE_OFF, STATE_ON])
async def test_switch_waits_for_feedback(
    hass, kvm, key, on, off, report_on, report_off, initial, requested
):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "switch", key)
    if initial != STATE_UNKNOWN:
        await port.reader.receive(
            (report_on if initial == STATE_ON else report_off) + b"\r\n"
        )

    await call(hass, entity_id, f"turn_{requested}")

    assert port.writes == [
        STARTUP_QUERY,
        (on if requested == STATE_ON else off) + b"\r\n",
    ]
    assert state(hass, entity_id) == initial
    await port.reader.receive(
        (report_on if requested == STATE_ON else report_off) + b"\r\n"
    )
    assert state(hass, entity_id) == requested


async def test_mouse_switch_accepts_off_before_pending_on_is_confirmed(hass, kvm):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "switch", "mouse_change_channel")
    await port.reader.receive(b"Mouse change channel : OFF\r\n")

    await call(hass, entity_id, "turn_on")
    await call(hass, entity_id, "turn_off")

    assert port.writes == [STARTUP_QUERY, b"M1\r\n", b"M0\r\n"]
    assert state(hass, entity_id) == STATE_OFF


@pytest.mark.parametrize(
    ("domain", "key", "action", "data"),
    [
        ("select", "channel", "select_option", {"option": "Channel 3"}),
        ("select", "hotkey", "select_option", {"option": "Shift"}),
        ("select", "auto_scan", "select_option", {"option": "8 seconds"}),
        ("select", "audio", "select_option", {"option": "Channel 3"}),
        ("select", "video1", "select_option", {"option": "Channel 3"}),
        ("select", "video2", "select_option", {"option": "Channel 3"}),
        ("select", "hub1", "select_option", {"option": "Channel 3"}),
        ("select", "hub2", "select_option", {"option": "Channel 3"}),
        ("switch", "buzzer", "turn_on", {}),
        ("switch", "mouse_change_channel", "turn_off", {}),
        ("button", "sync_usb_hubs", "press", {}),
    ],
)
@pytest.mark.parametrize(
    "error", [OSError("write failed"), TimeoutError("write timed out")]
)
async def test_transport_failure_reaches_the_service_caller_and_marks_entities_unavailable(
    hass, kvm, domain, key, action, data, error
):
    entry, port = kvm
    entity_id = find_entity(hass, entry, domain, key)
    channel = find_entity(hass, entry, "select", "channel")
    await port.reader.receive(b"CH-1\r\n")
    port.drain_error = error

    with pytest.raises(HomeAssistantError, match=str(error)):
        await call(hass, entity_id, action, **data)

    assert port.closed
    assert state(hass, channel) == STATE_UNAVAILABLE
    assert state(hass, entity_id) == STATE_UNAVAILABLE


async def test_platforms_register_a_single_device_and_expected_controls(hass, kvm):
    entry, _ = kvm
    registry = er.async_get(hass)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.name == "Desk KVM"
    assert device.manufacturer == "ConnectPro"
    assert device.model is None
    expected = {
        "select": {
            "channel",
            "hotkey",
            "auto_scan",
            "audio",
            "video1",
            "video2",
            "hub1",
            "hub2",
        },
        "button": {"reset", "sync_usb_hubs"},
        "switch": {"buzzer", "mouse_change_channel"},
    }

    controls = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert {(control.domain, control.translation_key) for control in controls} == {
        (domain, key) for domain, keys in expected.items() for key in keys
    }
    for control in controls:
        assert control.unique_id == f"{entry.entry_id}_{control.translation_key}"
        assert control.device_id == device.id
        assert not control.disabled
        assert state(hass, control.entity_id) != STATE_UNAVAILABLE
        if control.translation_key != "channel":
            assert control.entity_category is EntityCategory.CONFIG


async def test_state_events_follow_feedback_and_unload(hass, kvm, serial_ports):
    entry, port = kvm
    entity_id = find_entity(hass, entry, "select", "channel")
    states = []

    @callback
    def record(event):
        if event.data["entity_id"] == entity_id:
            next_state = event.data["new_state"]
            states.append(next_state.state if next_state is not None else None)

    unsubscribe = hass.bus.async_listen(EVENT_STATE_CHANGED, record)
    try:
        await call(hass, entity_id, "select_option", option="Channel 3")
        await hass.async_block_till_done()
        assert states == []
        await port.reader.receive(b"CH-3\r\n")
        await hass.async_block_till_done()
        assert states == ["Channel 3"]

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert port.closed
        assert state(hass, entity_id) == STATE_UNAVAILABLE

        assert await hass.config_entries.async_setup(entry.entry_id)
        new_port = serial_ports.sessions["test-kvm"][-1]
        assert state(hass, entity_id) == STATE_UNKNOWN
        await new_port.reader.receive(b"CH-4\r\n")
        await hass.async_block_till_done()
        assert states[-1] == "Channel 4"
    finally:
        unsubscribe()


async def test_device_uses_default_name_when_entry_title_is_empty(hass, add_entry):
    entry = await add_entry(title="")
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.name == "ConnectPro KVM"
