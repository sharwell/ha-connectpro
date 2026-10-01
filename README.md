# ConnectPro KVM (Home Assistant)

This custom Home Assistant integration controls a ConnectPro KVM over its
serial connection and reads device feedback into native entities. It
configures the port when it connects, so a startup `stty` automation is no
longer needed.

This is an initial implementation based on the existing installation's
commands and response mappings. It has not been verified against physical
hardware. The [protocol reference](docs/commands.md) records the evidence
and the features that still need confirmation from manuals or captures.

## HACS installation (custom repo)

Requires Home Assistant **2024.12.0 or newer**.

1. In HACS, add this repository as a custom integration.
2. Install "ConnectPro KVM".
3. Restart Home Assistant.
4. Follow the setup instructions below.

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
4. Add this integration, then update dashboards and automations to use its
   entities and actions.

The integration creates native entities; it does not take over the old
`sensor.serial_sensor`, `input_select.kvm_*`, or `input_boolean.kvm_*`
helpers. Keep the old definitions while migrating if useful, then remove
them when nothing references them.

## Setup

1. Go to **Settings > Devices & services > Add integration** and choose
   **ConnectPro KVM**.
2. Choose an available serial port or enter a custom device path,
   preferably your adapter's stable `/dev/serial/by-id/...` path.
3. Optionally enter a name for the device.

Use your own adapter path; the path in the protocol reference belongs to
one installation. Home Assistant must have permission to open the device.
Container installations must also make the serial device available inside
the container.

New entries use **115200 baud, 8 data bits, no parity, and 1 stop bit**.
Software and hardware flow control are disabled. The integration applies
these settings each time it opens the port, including after a reconnect.
Serial settings stored by older config entries remain supported.

Setup checks that the port can be opened and the settings applied. It does
not identify the connected hardware or require a KVM handshake. To change
the port or name later, use **Reconfigure** on the integration entry; its
existing entities are preserved.

## Entities and actions

| Entity | Behavior |
| --- | --- |
| Channel select | Sends `Ch1` through `Ch4`; reports `Channel 1` through `Channel 4` from received feedback. |
| Reset button | Sends `W0`, matching the previous dashboard's Reset action. The scope of this reset is not yet documented. |
| Hotkey sensor | Reports `Ctrl`, `Shift`, `Scroll Lock`, or `Caps Lock` from recognized feedback. |
| Audio, Hub 1, and Hub 2 sensors | Report the confirmed `Sync` feedback. Other modes need protocol evidence. |
| Buzzer binary sensor | Reports the received on/off state. |
| Mouse change channel binary sensor | Reports the received on/off state. |

The sensors describe observed state. Their corresponding controls are not
exposed until the command meanings are confirmed. State remains unknown
until the relevant feedback arrives; sending a command does not establish
that it succeeded. An old email associates `K1P0` with a report containing
all seven known state categories, but its purpose and possible setting
changes remain unconfirmed. The integration therefore sends no automatic
startup or status query. Entities become unavailable on a connection
failure, and the integration retries the connection automatically.

Each channel selection sends the requested command, even when the last
reported channel matches. This keeps rapid requests, such as switching to
Channel 3 and back to Channel 2 before feedback arrives, from being lost.

Use the entities on the integration's device page to select a channel or
press Reset. In an automation, replace the example entity IDs below with
the ones created in your installation:

```yaml
action: select.select_option
target:
  entity_id: select.your_kvm_channel
data:
  option: Channel 2
```

```yaml
action: button.press
target:
  entity_id: button.your_kvm_reset
```

For a command already known to work with your device, use the
**ConnectPro KVM: Send command** action. Select the ConnectPro device in the
action editor. The YAML form uses its device ID inside `data`:

```yaml
action: connectpro.send_command
data:
  device_id: YOUR_CONNECTPRO_DEVICE_ID
  command: Ch2
```

The command must be one printable ASCII line. Preserve its case and omit line
endings; the integration adds `\r\n`. This action sends bytes without
claiming a device acknowledgment. The [command catalog](docs/commands.md#command-catalog)
includes legacy senders whose meanings are still unconfirmed.

## Debugging serial communication

Open **Settings > Devices & services > ConnectPro KVM**, open the three-dot
menu, and choose **Enable debug logging**. Reproduce the issue, then choose
**Disable debug logging** to download the log, following
[Home Assistant's debug logging instructions](https://www.home-assistant.io/docs/configuration/troubleshooting/#enabling-debug-logging).

Alternatively, add or merge this into `configuration.yaml` and restart
Home Assistant:

```yaml
logger:
  logs:
    custom_components.connectpro: debug
```

Debug logs include the serial device path, the direction (`TX` for sent
bytes and `RX` for received bytes), and escaped byte content so that line
endings are visible. Unrecognized incoming messages are logged as well.
A sent `Ch2` command is shown with its `\r\n` terminator; incoming data may
arrive in more than one read. Logs describe what the integration writes
and receives, not an independent electrical capture.

For useful protocol evidence, capture a connection/startup followed by one
action at a time, and note the KVM model, firmware version, and observed
result. This will help establish additional commands and feedback forms.
Turn debug logging off when finished.

## Development notes

The serial protocol reference and remaining information gaps are in
[docs/commands.md](docs/commands.md). The transport uses `serialx==1.10.0`.
Tests cover Home Assistant 2024.12.5 and simulated
serial communication; they do not replace hardware verification.

Create a virtual environment and run the checks from the repository root
(PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-test.txt
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
```

On Linux or macOS, use `.venv/bin/python` in place of
`.\.venv\Scripts\python` after creating the environment.

### Local Codex initialization prompt

> Read AGENTS.md and README.md to familiarize yourself with this repository. After performing any work which resulted in uncommitted changes to repository files, provide a commit message for the work. Commit messages should be provided in fenced code blocks for easy copy/paste.
