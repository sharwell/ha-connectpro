"""Configuration and reconfiguration through Home Assistant's flow manager."""

import asyncio
import os

import pytest
from serialx import Parity, SerialPortInfo, StopBits

from custom_components.connectpro.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType

DEFAULT_SETTINGS = {
    "baudrate": 115200,
    "byte_size": 8,
    "parity": Parity.NONE,
    "stopbits": StopBits.ONE,
    "xonxoff": False,
    "rtscts": False,
    "dsrdtr": False,
}
LEGACY_DATA = {"baudrate": 9600, "bytesize": 7, "parity": "E", "stopbits": 2}
LEGACY_SETTINGS = DEFAULT_SETTINGS | {
    "baudrate": 9600,
    "byte_size": 7,
    "parity": Parity.EVEN,
    "stopbits": StopBits.TWO,
}


async def submit(hass, data, *, entry=None):
    """Complete a form through the same flow manager the UI uses."""
    context = {"source": SOURCE_USER}
    if entry is not None:
        context = {"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    form = await hass.config_entries.flow.async_init(DOMAIN, context=context)
    assert form["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(form["flow_id"], data)


@pytest.fixture(params=["same path", "symlink"])
def port_paths(tmp_path, request, monkeypatch):
    port = tmp_path / "serial-port"
    port.touch()
    if request.param == "same path":
        return str(port), str(port)
    alias = tmp_path / "serial-alias"
    try:
        alias.symlink_to(port)
    except OSError as error:
        if getattr(error, "winerror", None) != 1314:
            raise
        # Windows hosts without symlink privileges can still exercise the
        # flow's handling of two paths resolved to the same serial device.
        realpath = os.path.realpath

        def resolve(path, *args, **kwargs):
            if path == str(alias):
                path = port
            return realpath(path, *args, **kwargs)

        monkeypatch.setattr(os.path, "realpath", resolve)
    return str(port), str(alias)


async def test_user_form_only_requests_device_and_name(hass, serial_ports):
    serial_ports.ports = [
        SerialPortInfo(
            device="COM9",
            resolved_device="COM9",
            vid=None,
            pid=None,
            serial_number=None,
            manufacturer="Example",
            product="USB serial",
            bcd_device=None,
            interface_description=None,
            interface_num=None,
        )
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    fields = {
        key.schema: selector for key, selector in result["data_schema"].schema.items()
    }
    assert set(fields) == {"device", CONF_NAME}
    assert fields["device"].config["custom_value"] is True
    assert fields["device"].config["options"] == [
        {"value": "COM9", "label": "COM9 (USB serial)"}
    ]
    assert result["data_schema"]({"device": "COM9"})[CONF_NAME] == "ConnectPro KVM"


async def test_port_enumeration_failure_still_allows_manual_path(hass, serial_ports):
    serial_ports.list_error = OSError("enumeration unavailable")
    result = await submit(hass, {"device": "COM9"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].state is ConfigEntryState.LOADED


@pytest.mark.parametrize("name", [None, "", "  ", "  Desk KVM  "])
async def test_success_uses_defaults_and_closes_probe(hass, serial_ports, name):
    user_input = {"device": " COM9 "}
    if name is not None:
        user_input[CONF_NAME] = name
    result = await submit(hass, user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert hass.config_entries.async_get_entry(entry.entry_id) is entry
    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == ("Desk KVM" if name == "  Desk KVM  " else "ConnectPro KVM")
    assert entry.data == {
        "device": "COM9",
        CONF_NAME: entry.title,
        "baudrate": 115200,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
    }
    assert entry.unique_id == "COM9"
    assert serial_ports.attempts == [("COM9", DEFAULT_SETTINGS)] * 2
    probe, connection = serial_ports.sessions["COM9"]
    assert probe.closed and probe.writes == []
    await asyncio.wait_for(connection.reader.reading.wait(), 2)
    assert connection.writes == [b"k1p0\r\n"]


@pytest.mark.parametrize(
    "error",
    [OSError("missing port"), TimeoutError("timeout"), ValueError("bad settings")],
)
async def test_failed_probe_does_not_create_entry(hass, serial_ports, error):
    serial_ports.open_errors["COM9"] = error
    result = await submit(hass, {"device": "COM9"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries(DOMAIN) == []
    assert serial_ports.attempts == [("COM9", DEFAULT_SETTINGS)]
    assert "COM9" not in serial_ports.sessions


async def test_empty_path_never_opens_serial(hass, serial_ports):
    result = await submit(hass, {"device": "  "})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"device": "invalid_device"}
    assert serial_ports.attempts == []


async def test_duplicate_path_or_symlink_never_opens_serial(
    hass, serial_ports, add_entry, port_paths
):
    original, requested = port_paths
    entry = await add_entry(original)
    result = await submit(hass, {"device": requested})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert serial_ports.attempts == [(original, DEFAULT_SETTINGS)]


async def test_reconfigure_own_port_reloads_without_a_probe(
    hass, serial_ports, add_entry, port_paths
):
    original, requested = port_paths
    entry = await add_entry(original, settings=LEGACY_DATA, title="Original KVM")
    old_connection = serial_ports.sessions[original][0]
    result = await submit(
        hass, {"device": requested, CONF_NAME: "Renamed KVM"}, entry=entry
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == "Renamed KVM"
    assert entry.data == LEGACY_DATA | {"device": requested, CONF_NAME: "Renamed KVM"}
    assert serial_ports.attempts == [
        (original, LEGACY_SETTINGS),
        (requested, LEGACY_SETTINGS),
    ]
    assert old_connection.closed
    connection = serial_ports.sessions[requested][-1]
    assert connection is not old_connection and not connection.closed


async def test_reconfigure_new_port_probes_with_stored_settings(
    hass, serial_ports, add_entry
):
    entry = await add_entry("COM9", settings=LEGACY_DATA)
    result = await submit(hass, {"device": "COM10"}, entry=entry)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data["device"] == "COM10"
    assert serial_ports.attempts == [
        ("COM9", LEGACY_SETTINGS),
        ("COM10", LEGACY_SETTINGS),
        ("COM10", LEGACY_SETTINGS),
    ]
    assert serial_ports.sessions["COM9"][0].closed
    probe, connection = serial_ports.sessions["COM10"]
    assert probe.closed and probe.writes == []
    assert not connection.closed


async def test_failed_reconfigure_keeps_original_entry(hass, serial_ports, add_entry):
    entry = await add_entry(
        "COM9", title="Original KVM", settings={CONF_NAME: "Original KVM"}
    )
    serial_ports.open_errors["COM10"] = OSError("unavailable")
    result = await submit(hass, {"device": "COM10", CONF_NAME: "New KVM"}, entry=entry)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == {"device": "COM9", CONF_NAME: "Original KVM"}
    assert entry.title == "Original KVM"
    assert not serial_ports.sessions["COM9"][0].closed
    assert serial_ports.attempts == [
        ("COM9", DEFAULT_SETTINGS),
        ("COM10", DEFAULT_SETTINGS),
    ]


async def test_reconfigure_rejects_other_entrys_port(hass, serial_ports, add_entry):
    entry = await add_entry("COM9")
    await add_entry("COM10")
    result = await submit(hass, {"device": "COM10"}, entry=entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["device"] == "COM9"
    assert serial_ports.attempts == [
        ("COM9", DEFAULT_SETTINGS),
        ("COM10", DEFAULT_SETTINGS),
    ]
