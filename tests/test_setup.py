"""Entry lifecycle, migration, and command routing through real HA APIs."""

import asyncio

import pytest
import voluptuous as vol

from custom_components.connectpro import client
from custom_components.connectpro.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

STARTUP_QUERY = b"k1p0\r\n"
MODEL_REPORT = b"UDP2_14AP_U3 : Version_Number - 0009 - D1223\r\n"


def get_device(hass, entry):
    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    return device


def register_entity(hass, entry, domain, key, **kwargs):
    return er.async_get(hass).async_get_or_create(
        domain, DOMAIN, f"{entry.entry_id}_{key}", config_entry=entry, **kwargs
    )


async def send(hass, device_id, command="Ch2"):
    await hass.services.async_call(
        DOMAIN,
        "send_command",
        {"device_id": device_id, "command": command},
        blocking=True,
    )


async def test_setup_queries_once_after_entity_registration_and_closes_on_stop(
    hass, add_entry, serial_ports, monkeypatch
):
    ready_at_query = []

    async def open_serial(**settings):
        reader, writer = await serial_ports.open(**settings)
        original_write = writer.write

        def write(data):
            original_write(data)
            if data == STARTUP_QUERY:
                ready_at_query.append(
                    {
                        registered.translation_key
                        for registered in er.async_get(hass).entities.values()
                        if hass.states.get(registered.entity_id) is not None
                    }
                )

        writer.write = write
        return reader, writer

    monkeypatch.setattr(client, "open_serial_connection", open_serial)
    entry = await add_entry()
    (port,) = serial_ports.sessions["test-kvm"]
    await asyncio.wait_for(port.reader.reading.wait(), 2)

    assert entry.state is ConfigEntryState.LOADED
    assert [url for url, settings in serial_ports.attempts] == ["test-kvm"]
    assert port.writes == [STARTUP_QUERY]
    assert ready_at_query == [
        {
            "channel",
            "hotkey",
            "auto_scan",
            "audio",
            "video1",
            "video2",
            "hub1",
            "hub2",
            "reset",
            "sync_usb_hubs",
            "buzzer",
            "mouse_change_channel",
        }
    ]
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert port.closed


async def test_unavailable_port_requests_ha_retry_and_preserves_legacy_registry(
    hass, add_entry, serial_ports
):
    entry = await add_entry(disabled=True)
    old_entity = register_entity(hass, entry, "sensor", "audio")
    serial_ports.open_errors["test-kvm"] = OSError("port unavailable")

    assert not await hass.config_entries.async_set_disabled_by(entry.entry_id, None)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert "port unavailable" in entry.reason
    assert serial_ports.sessions == {}
    assert er.async_get(hass).async_get(old_entity.entity_id) is not None


async def test_forwarding_exception_closes_serial_port_without_migrating_entities(
    hass, add_entry, serial_ports, monkeypatch
):
    entry = await add_entry(disabled=True)
    old_entity = register_entity(hass, entry, "button", "sync_video1")

    async def fail_forwarding(entry, platforms):
        raise RuntimeError("platform forwarding failed")

    # Force the exceptional return from HA's forwarding API. A normal
    # platform-specific failure is handled inside the framework.
    monkeypatch.setattr(
        hass.config_entries, "async_forward_entry_setups", fail_forwarding
    )

    assert not await hass.config_entries.async_set_disabled_by(entry.entry_id, None)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    (port,) = serial_ports.sessions["test-kvm"]
    assert port.closed and port.writes == []
    assert er.async_get(hass).async_get(old_entity.entity_id) is not None


async def test_setup_removes_only_replaced_routing_registry_entries(hass, add_entry):
    entry = await add_entry(disabled=True)
    other_entry = await add_entry("other-kvm", disabled=True)
    registry = er.async_get(hass)
    obsolete = [
        register_entity(hass, entry, domain, key, suggested_object_id=f"legacy_{key}")
        for domain, keys in (
            ("sensor", ("audio", "hub1", "hub2", "video1")),
            ("button", ("sync_audio", "sync_video1", "sync_video_outputs")),
        )
        for key in keys
    ]
    preserved = [
        register_entity(hass, entry, "button", "reset"),
        register_entity(hass, entry, "button", "sync_usb_hubs"),
        register_entity(hass, entry, "sensor", "unrelated"),
        register_entity(hass, entry, "binary_sensor", "audio"),
        register_entity(hass, other_entry, "sensor", "audio"),
        registry.async_get_or_create(
            "sensor", "other", f"{entry.entry_id}_audio", config_entry=entry
        ),
    ]

    assert await hass.config_entries.async_set_disabled_by(entry.entry_id, None)

    assert all(registry.async_get(old.entity_id) is None for old in obsolete)
    assert all(registry.async_get(old.entity_id) is not None for old in preserved)
    for key in ("audio", "hub1", "hub2", "video1", "video2"):
        entity_id = registry.async_get_entity_id(
            "select", DOMAIN, f"{entry.entry_id}_{key}"
        )
        assert entity_id and hass.states.get(entity_id) is not None


async def test_model_report_updates_existing_device_with_all_entities_disabled(
    hass, add_entry, serial_ports
):
    entry = await add_entry(disabled=True)
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="ConnectPro",
        name=entry.title,
    )
    registry.async_update_device(device.id, name_by_user="My desk KVM")
    for domain, keys in (
        (
            "select",
            (
                "channel",
                "hotkey",
                "auto_scan",
                "audio",
                "video1",
                "video2",
                "hub1",
                "hub2",
            ),
        ),
        ("button", ("reset", "sync_usb_hubs")),
        ("switch", ("buzzer", "mouse_change_channel")),
    ):
        for key in keys:
            register_entity(
                hass,
                entry,
                domain,
                key,
                disabled_by=er.RegistryEntryDisabler.USER,
                device_id=device.id,
            )

    assert await hass.config_entries.async_set_disabled_by(entry.entry_id, None)
    controls = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert all(
        control.disabled and hass.states.get(control.entity_id) is None
        for control in controls
    )
    (port,) = serial_ports.sessions["test-kvm"]
    model_updates = []

    @callback
    def record(event):
        if event.data["device_id"] == device.id and "model" in event.data.get(
            "changes", {}
        ):
            model_updates.append(get_device(hass, entry).model)

    unsubscribe = hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, record)
    try:
        await port.reader.receive(b"UDP2_14AP_U3 : Version_Number - \r\n")
        assert get_device(hass, entry).model is None
        await port.reader.receive(MODEL_REPORT)
        await port.reader.receive(MODEL_REPORT)
        await hass.async_block_till_done()

        updated = get_device(hass, entry)
        assert updated.id == device.id
        assert updated.model == "UDP2-14AP"
        assert updated.identifiers == {(DOMAIN, entry.entry_id)}
        assert updated.manufacturer == "ConnectPro"
        assert updated.name == entry.title
        assert updated.name_by_user == "My desk KVM"
        assert model_updates == ["UDP2-14AP"]

        port.reader.feed_eof()
        await asyncio.wait_for(port.closed_event.wait(), 2)
        assert get_device(hass, entry).model == "UDP2-14AP"
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert model_updates == ["UDP2-14AP"]
    finally:
        unsubscribe()


async def test_model_report_does_not_recreate_a_removed_device(
    hass, add_entry, serial_ports
):
    entry = await add_entry()
    registry = dr.async_get(hass)
    registry.async_remove_device(get_device(hass, entry).id)
    (port,) = serial_ports.sessions["test-kvm"]

    await port.reader.receive(MODEL_REPORT)

    assert not dr.async_entries_for_config_entry(registry, entry.entry_id)
    assert not port.closed


async def test_unload_closes_serial_and_removes_states(hass, add_entry, serial_ports):
    entry = await add_entry()
    (port,) = serial_ports.sessions["test-kvm"]
    await port.reader.receive(b"CH-2\r\n")

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert port.closed
    assert entry.state is ConfigEntryState.NOT_LOADED
    channel = er.async_get(hass).async_get_entity_id(
        "select", DOMAIN, f"{entry.entry_id}_channel"
    )
    assert hass.states.get(channel).state == "unavailable"


async def test_refused_platform_unload_preserves_serial_session(
    hass, add_entry, serial_ports, monkeypatch
):
    entry = await add_entry()
    (port,) = serial_ports.sessions["test-kvm"]

    async def refuse_unload(entry, platforms):
        return False

    # Inject a failed framework unload to exercise the port ownership guard.
    with monkeypatch.context() as context:
        context.setattr(hass.config_entries, "async_unload_platforms", refuse_unload)
        assert not await hass.config_entries.async_unload(entry.entry_id)
        assert not port.closed

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert port.closed


async def test_command_action_is_registered_before_any_entry_loads(hass):
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "send_command")

    with pytest.raises(ServiceValidationError, match="does not exist"):
        await send(hass, "missing")


async def test_command_action_targets_only_the_selected_device(
    hass, add_entry, serial_ports
):
    first = await add_entry("first-port")
    await add_entry("second-port")
    first_port = serial_ports.sessions["first-port"][0]
    second_port = serial_ports.sessions["second-port"][0]
    await asyncio.wait_for(first_port.reader.reading.wait(), 2)
    await asyncio.wait_for(second_port.reader.reading.wait(), 2)

    await send(hass, get_device(hass, first).id)

    assert first_port.writes == [STARTUP_QUERY, b"Ch2\r\n"]
    assert second_port.writes == [STARTUP_QUERY]


async def test_command_action_rejects_another_integrations_device(hass, add_entry):
    other = await add_entry(domain="input_boolean", disabled=True)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={(other.domain, "other-device")},
    )
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError, match="belonging to ConnectPro"):
        await send(hass, device.id)


async def test_command_action_reports_unloaded_device(hass, add_entry, serial_ports):
    entry = await add_entry(disabled=True)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, entry.entry_id)}
    )

    with pytest.raises(HomeAssistantError, match="not loaded"):
        await send(hass, device.id)
    assert serial_ports.attempts == []


async def test_command_action_rejects_invalid_payload_without_a_write(
    hass, add_entry, serial_ports
):
    entry = await add_entry()
    (port,) = serial_ports.sessions["test-kvm"]
    await asyncio.wait_for(port.reader.reading.wait(), 2)

    with pytest.raises(ServiceValidationError, match="printable ASCII"):
        await send(hass, get_device(hass, entry).id, "Ch2\r\nW0")

    assert port.writes == [STARTUP_QUERY]
    assert not port.closed


async def test_command_action_surfaces_transport_failure(hass, add_entry, serial_ports):
    entry = await add_entry()
    (port,) = serial_ports.sessions["test-kvm"]
    await asyncio.wait_for(port.reader.reading.wait(), 2)
    port.drain_error = OSError("disconnected")

    with pytest.raises(HomeAssistantError, match="disconnected"):
        await send(hass, get_device(hass, entry).id)

    assert port.closed


async def test_command_action_requires_explicit_device(hass):
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "send_command", {"command": "Ch2"}, blocking=True
        )
