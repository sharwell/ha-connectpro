# ConnectPro KVM (Home Assistant)

Control a serial-connected ConnectPro KVM from Home Assistant. The
integration provides native controls for channel selection, display reset,
hotkeys, audio/video/USB routing, auto-scan, the buzzer, and mouse channel
switching. It configures the serial port and updates entity state from
device feedback.

The integration represents one device per serial connection. For linked
KVMs, its entities report feedback on that connection. The hardware
observations come from one installation. See the [command reference](docs/commands.md)
and its [hardware verification gaps](docs/commands.md#hardware-verification-gaps).

## HACS installation (custom repo)

Requires Home Assistant **2024.12.0 or newer**.

1. In HACS, add this repository as a custom integration.
2. Install **ConnectPro KVM**.
3. Restart Home Assistant.
4. Follow the [setup instructions](#setup).

For a manual installation, copy `custom_components/connectpro` into your
Home Assistant configuration's `custom_components` directory, then restart
Home Assistant.

## Moving from the existing YAML setup

Only one integration or application should own the serial port. Before
adding ConnectPro KVM:

1. Disable the old serial sensor and restart Home Assistant to release the
   port.
2. Disable `Configure serial port when Home Assistant starts` and
   `Process serial sensor inputs`.
3. Stop calling the old serial `shell_command` actions, including the
   channel script and dashboard buttons that use them.
4. [Set up ConnectPro KVM](#setup), then update dashboards and automations
   to use its entities and actions.

The integration creates its own entities. You can remove
`sensor.serial_sensor`, `input_select.kvm_*`, and `input_boolean.kvm_*`
once nothing references them.

### Updating from an earlier prerelease

Update dashboards and automations that used the earlier routing sensors or
audio/video Sync buttons to use the [routing selects](#entities-and-actions).
Setup removes the obsolete routing entries for this integration. The
hotkey, buzzer, and mouse channel switching controls also report their
observed state. The renamed **Reset displays** button retains its entity
identity.

## Setup

1. Go to **Settings > Devices & services > Add integration** and choose
   **ConnectPro KVM**.
2. Choose an available serial port or enter your adapter's device path.
   On Linux, prefer its stable path under `/dev/serial/by-id/`.
3. Optionally enter a name for the device.

Home Assistant needs permission to open the device. For a container
installation, make the serial device available inside the container.

New entries use **115200 baud, 8 data bits, no parity, and 1 stop bit**,
with software and hardware flow control disabled. The integration reapplies
these settings each time it opens the port, including after reconnecting.
Older entries keep their stored serial settings.

The setup form checks whether the port can be opened with those settings
without sending KVM commands. Use **Reconfigure** on the integration entry
to change the port or name while keeping its entities.

## Entities and actions

Use the controls on the integration's device page.

| Entity | Options and effects |
| --- | --- |
| Channel select | Select **Channel 1** through **Channel 4**. |
| Reset displays button | Sends `W0`. All displays cycled off and on in the [observed exchange](docs/commands.md#debug-capture-after-w0). Computer-side redetection remains unverified. |
| Hotkey select | Select **Ctrl**, **Shift**, **Scroll Lock**, or **Caps Lock**. |
| Audio routing select | Choose **Sync** to follow the selected channel or **Channel 1** through **Channel 4** to route audio independently. |
| Video 1 and Video 2 routing selects | Choose **Sync** or **Channel 1** through **Channel 4** independently for each output. |
| Hub 1 and Hub 2 routing selects | Choose **Channel 1** through **Channel 4** independently. A hub can display **Sync** from feedback, but selecting it raises an error, including in automations. Use **Sync both USB hubs**. |
| Sync both USB hubs button | Returns both hubs to **Sync** together. |
| Auto scan select | Choose **5**, **8**, **15**, **20**, or **30 seconds** to start scanning. Choose **Off** to stop. |
| Buzzer and Mouse channel switching switches | Turn each setting on or off. |

### How entity state updates

Each valid selection or switch request sends its command, even when the last
reported value matches. You can switch to Channel 3 and back to Channel 2
before the first reply arrives. Entity state changes when the integration
receives recognized feedback.

On startup after the entities initialize, and after each successful
reconnect, the integration sends `k1p0` once to request current state.
There is no periodic polling. Entities become unavailable on connection
failure. The integration retries automatically, and individual settings
stay unknown on the new connection until matching feedback arrives. The
status reports observed so far include no auto-scan settings. The Auto scan
select needs explicit off feedback or both on feedback and a known interval.
While scanning, it keeps showing the last reported duration until a new
interval arrives. A channel change alone does not establish that scanning
stopped.

If the reply includes the confirmed `UDP2_14AP_U3` identifier, Home
Assistant displays **UDP2-14AP** as the device model. The model persists
through disconnects. Other model identifiers remain unmapped, and component
version numbers remain protocol diagnostics. See the
[status query](docs/commands.md#automatic-state-initialization) and
[model identification](docs/commands.md#model-identification) details.

### Using controls in automations

Replace the entity IDs with those created in your installation. Use
`select.select_option` for channels, hotkeys, routing, and auto-scan.
Quote `"Off"` when writing that auto-scan option in YAML.

```yaml
action: select.select_option
target:
  entity_id: select.your_kvm_channel
data:
  option: Channel 2
```

Use `button.press` for **Reset displays** or **Sync both USB hubs**. Use
`switch.turn_on` or `switch.turn_off` for the buzzer and mouse channel
switching.

```yaml
action: button.press
target:
  entity_id: button.your_kvm_sync_usb_hubs
```

```yaml
action: switch.turn_off
target:
  entity_id: switch.your_kvm_buzzer
```

### Sending a manual command

For a command known to work with your hardware, use **ConnectPro KVM: Send
command** (`connectpro.send_command`). Select the ConnectPro device in the
action editor. In YAML, provide its device registry ID in `data.device_id`
and a single nonblank printable ASCII line in `data.command`. Preserve
command case and omit line endings. The integration appends `\r\n`.

```yaml
action: connectpro.send_command
data:
  device_id: YOUR_CONNECTPRO_DEVICE_ID
  command: Ch2
```

The action rejects invalid input or a non-ConnectPro device and reports an
error if the connection cannot send. A successful write means the command
was accepted by the serial transport. Entity state still depends on
recognized feedback. In a tested two-KVM chain, `K1P1` and `K2P1` switched
different units without updating the Channel entity. See the
[targeted channel evidence](docs/commands.md#targeted-channel-switching-in-a-two-kvm-chain)
and [command catalog](docs/commands.md#command-catalog) for observed
replies and legacy commands.

## Debugging serial communication

### Dependency errors after a Home Assistant update

If setup reports `Requirements for connectpro not found` and the
installation log shows an old `serialx==1.10.0` pin, update ConnectPro and
restart Home Assistant. For a manual installation, replace
`custom_components/connectpro` in your Home Assistant configuration
directory. The update uses your existing device settings and entities.

Home Assistant 2026.10.2
[requires `serialx==1.11.0`](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/package_constraints.txt#L68).
Older ConnectPro releases require exactly 1.10.0. The current
`serialx>=1.10.0,<2.0.0` range lets Home Assistant keep its compatible
version and reserves a new major release for compatibility review.

A requirement failure occurs before ConnectPro loads. If setup still
fails after the update, check the preceding package-installation log
for the cause.

### Communication logs

1. Open **Settings > Devices & services > ConnectPro KVM**.
2. In the three-dot menu, choose **Enable debug logging**.
3. Reproduce the issue. To collect protocol evidence, capture startup and
   then one action at a time. Note the KVM model, firmware version, and
   observed result.
4. Choose **Disable debug logging** to download the log. Before sharing it,
   redact device paths and other installation identifiers. Keep the command
   and reply bytes, read order, and relevant timing.

See [Home Assistant's debug logging instructions](https://www.home-assistant.io/docs/configuration/troubleshooting/#enabling-debug-logging).
You can also add or merge the following into `configuration.yaml` and
restart Home Assistant. Remove the setting when finished.

```yaml
logger:
  logs:
    custom_components.connectpro: debug
```

The log records the device path, the `TX` or `RX` direction, and escaped
bytes such as the `\r\n` terminator of `Ch2`. A reply may span multiple
reads. Unrecognized messages appear in the log while state processing
continues. These are host-side logs of serial I/O. The
[`K1P0` capture](docs/commands.md#debug-capture-after-k1p0) shows how to read
fragmented replies and trailing whitespace.

## Development notes

From the repository root, use Python 3.12 to create a virtual environment
and run the checks. On Windows, run these commands in PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-test.txt
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
```

On Linux or macOS, use `.venv/bin/python` in place of
`.\.venv\Scripts\python` after creating the environment.

Local development uses the same baseline as the minimum CI job. The
[Tests workflow](.github/workflows/tests.yml) runs the full simulated suite
on two environments:

| Job | Home Assistant | Python and serialx |
| --- | --- | --- |
| Minimum | The declared support floor, 2024.12.0 | Python 3.12 and ConnectPro's `serialx==1.10.0` floor |
| Recent | A pinned stable release | The selected release's `.python-version` and package constraints |

CI verifies the installed versions before pytest. The dependency-loading
tests verify that Home Assistant keeps an installed compatible version.
See the [command reference](docs/commands.md) for physical verification.

Keep `serialx>=1.10.0,<2.0.0` in sync between the integration manifest and
`requirements-test-common.txt`. Exact pins in test environments exercise
specific combinations. The integration's range lets Home Assistant keep
its own compatible version during an upgrade.

### Local Codex initialization prompt

> Read AGENTS.md and README.md to familiarize yourself with this repository. After performing any work which resulted in uncommitted changes to repository files, provide a commit message for the work. Commit messages should be provided in fenced code blocks for easy copy/paste.
