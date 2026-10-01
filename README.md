# ConnectPro KVM (Home Assistant)

This custom Home Assistant integration controls a ConnectPro KVM over its
serial connection and reads device feedback into native entities. It
configures the port when it connects, so a startup `stty` automation is no
longer needed.

This is an initial implementation based on the existing installation's
commands and response mappings. User-provided captures from physical
hardware confirm manual status, targeted channel, hotkey, buzzer, mouse
channel-switching, USB/video/audio routing, auto-scan, and `W0` exchanges
through the integration. The user observed `W0` cycling all displays off
and on. The native `Ch1` through `Ch4` controls, recovery, and other
hardware configurations still need hardware verification. The
[protocol reference](docs/commands.md) records the evidence and the
features that still need confirmation.

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
not identify the connected hardware or require a KVM handshake. Once the
entry's entities are initialized, the integration sends `k1p0` to obtain
their current state. Serial-port checks in the setup form do not send KVM
commands. To change the port or name later, use **Reconfigure** on the
integration entry; its existing entities are preserved.

When a status report contains the confirmed `UDP2_14AP_U3` identifier,
the integration sets **UDP2-14AP** as the model in Home Assistant's device
information. It updates the existing device after the reply arrives and
retains the identified model through disconnects. Other model identifiers
remain unmapped; component version strings are not used as device firmware
versions. See [model identification](docs/commands.md#model-identification).

## Entities and actions

| Entity | Behavior |
| --- | --- |
| Channel select | Sends `Ch1` through `Ch4`; reports `Channel 1` through `Channel 4` from received feedback. |
| Reset displays button | Sends `W0`, matching the previous dashboard's Reset action. The user observed all displays cycling off and on; the captured reply is `Wake-Up : DP-ALL`. |
| Hotkey select | Selects `Ctrl`, `Shift`, `Scroll Lock`, or `Caps Lock` using `ctrl`, `shift`, `scroll`, or `caps`; reports recognized feedback. |
| Audio routing select | Selects `Sync` or `Channel 1` through `Channel 4` using `o0` through `o4`. |
| Video 1 and Video 2 routing selects | Select `Sync` or `Channel 1` through `Channel 4` using `v1p0`–`v1p4` or `v2p0`–`v2p4`. |
| Hub 1 and Hub 2 routing selects | Select `Channel 1` through `Channel 4` using `h1p1`–`h1p4` or `h2p1`–`h2p4`; display reported `Sync` but reject selecting it individually. |
| Sync both USB hubs button | Sends `h0p0`, restoring both hubs to Sync together. |
| Auto scan select | Selects `Off`, `5 seconds`, `8 seconds`, `15 seconds`, `20 seconds`, or `30 seconds` using `s0` through `s5`. Choosing a duration starts scanning. |
| Buzzer switch | Sends `BZON` or `BZOFF`; reports the received on/off state. |
| Mouse channel switching switch | Sends `M1` to enable or `M0` to disable mouse channel switching; reports the received on/off state. |

Each routing dropdown is a configuration entity and reports its observed
setting. Audio and video accept Sync directly. Hub Sync is a reported
state, but choosing it raises an error directing you to **Sync both USB
hubs**, because independent hub Sync is not established. Home Assistant
does not support graying out one dropdown option, so Sync remains visible
and is blocked when requested, including through automations.

State remains unknown until relevant feedback arrives; sending a command
does not establish that it succeeded. Routing controls replace the earlier
routing sensors and audio/video Sync buttons. Those obsolete entity entries
are removed on setup during this prerelease development; there are no
compatibility copies. Existing dashboards and automations should use the
new selects. Hotkey, buzzer, and mouse channel switching also each have
one control that reports state.

Repeated captures show `K1P0` producing a report
containing the seven original state categories. After `K1P1`, this report
contains `CH-1`, consistent with the first/local KVM's channel. Possible
effects on other settings remain unconfirmed. Observations also confirm
that `K1P1` switches only the first KVM to channel 1 and `K2P1`
switches only the second in the user's two-device chain. These commands
are available through the manual command action; the integration creates
one device per serial connection, without separate channel entities for
linked units. The integration sends lowercase `k1p0` once when its reader
starts on a connection, and once after each successful reconnect. Received
status lines populate recognized settings and model metadata as they arrive;
the latest report also supplies explicit Video 1 and Video 2 routing. There is
no periodic polling or optimistic state update. Entities become unavailable
on a connection failure, and the integration retries automatically before
requesting fresh state. The user has confirmed `k1p0` can obtain current
entity state after initialization; the
[protocol reference](docs/commands.md#automatic-state-initialization)
records this separately from the earlier uppercase captures.

Each channel selection sends the requested command, even when the last
reported channel matches. This keeps rapid requests, such as switching to
Channel 3 and back to Channel 2 before feedback arrives, from being lost.
The other selectors and switches also send every valid request, including
requests matching the last reported state, and wait for feedback before
changing state.

Use the entities on the integration's device page to select a channel or
hotkey, control the buzzer or mouse channel switching, reset displays,
restore USB/video/audio routing to Sync, or configure auto-scan. In an
automation, replace the example entity IDs below with the ones created in
your installation:

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

```yaml
action: switch.turn_off
target:
  entity_id: switch.your_kvm_buzzer
```

```yaml
action: select.select_option
target:
  entity_id: select.your_kvm_hotkey
data:
  option: Scroll Lock
```

```yaml
action: switch.turn_on
target:
  entity_id: switch.your_kvm_mouse_channel_switching
```

```yaml
action: button.press
target:
  entity_id: button.your_kvm_sync_usb_hubs
```

```yaml
action: select.select_option
target:
  entity_id: select.your_kvm_video_1_routing
data:
  option: Sync
```

```yaml
action: select.select_option
target:
  entity_id: select.your_kvm_auto_scan
data:
  option: "Off"
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

The Channel entity retains the last recognized `CH1` / `CH-1` through
`CH4` / `CH-4` report received on the connection. In the
[targeted channel capture](docs/commands.md#targeted-channel-switching-in-a-two-kvm-chain),
`K1P1` returned `OK` and `K2P1` returned `K1P1`, without a channel report.
After these manual commands, the entity can retain an earlier value while
the linked KVMs are on different channels. Neither reply identifies their
individual channel states.

A later [manual status capture](docs/commands.md#local-status-after-targeted-channel-selection)
shows `K1P0` updating the Channel entity to `Channel 1`, followed by a
physical channel-2 button press updating it to `Channel 2`. This does not
provide separate state for linked units. A separate captured `K2P0`
attempt returned `ERROR`, so that command did not retrieve the second
KVM's status in this installation.

The [captured `W0` exchange](docs/commands.md#debug-capture-after-w0)
returned `Wake-Up : DP-ALL`. The user observed all displays cycling off
and on; computer-side redetection has not been verified. The button is
named **Reset displays** to describe this effect. Its existing unique ID
is preserved, and it still sends exactly `W0`. This reply does not update
the integration's observed state. Later `CH1` / `CH2` messages in the log
were unrelated channel feedback, as confirmed by the user.

The [buzzer capture](docs/commands.md#debug-capture-after-buzzer-commands)
shows both `bzon` and `BZON` receiving `BZON`, and `BZOFF` receiving
`BZOFF`. The native switch uses the tested uppercase commands. These
responses update its state; it does not assume that a write succeeded.
The user heard the buzzer and reported that the commands appear to affect
both linked KVMs. The integration reports the feedback received on the
connection rather than separate buzzer states for each unit.

The [hotkey and mouse capture](docs/commands.md#debug-capture-after-hotkey-and-mouse-commands)
shows the four lowercase hotkey commands reporting their selected modes.
Both lowercase and uppercase `m0` / `M0` report mouse channel switching
off; `m1` / `M1` report it on. The controls use the tested lowercase
hotkey commands and uppercase mouse commands. These settings are reported
for one serial connection. The user verified the selected hotkeys and
mouse channel switching in use and confirmed that the changes affect
both linked KVMs in this installation.

The [USB/video routing capture](docs/commands.md#debug-capture-after-usb-hub-and-video-routing-commands)
shows `h1p2` assigning Hub 1 to machine 2 independently of the selected
channel, and `h0p0` reporting both hubs in Sync. The user verified the fixed
Hub 1 assignment on both linked KVMs. `h1p0` returned `ERROR`; the **Sync
both USB hubs** button therefore sends `h0p0` and explicitly affects both
hubs. An independent hub Sync command remains unknown.

For video, `v1p2` reports Video 1 fixed to port 2, `v1p0` reports Video 1
in Sync, and `v0p0` reports all video in Sync. The user verified that
`v1p2` pins Video 1 to machine 2 on both KVMs and `v1p0` restores only
Video 1 while leaving another pinned output unchanged. The routing selects
extend the command families to all four channels and both reported hub/video
endpoints. Those sibling combinations follow the supplied command inventory
and observed reply structures; they have not each been tested on hardware.
The global video command `v0p0` remains available through the manual action,
and its reply sets both Video 1 and Video 2 routing to Sync.

The [latest lowercase status capture](docs/commands.md#status-query-during-auto-scan)
reports `Video1 : SYNC-mode` and `Video2 : SYNC-mode`. These now initialize
both video routing controls when present in a status reply. The bare `V1P0`
/ `V1P1` tokens in older reports remain unknown and do not establish video
state. Routing selections continue to wait for device feedback.

The [audio and scan capture](docs/commands.md#debug-capture-after-audio-and-auto-scan-commands)
shows `o1` reporting audio routed to Channel 1 and `o0` reporting Sync.
The Audio routing select recognizes the same feedback forms and sends
`o0` for Sync or `o1` through `o4` for fixed channels. Destinations beyond
the directly tested Channel 1 follow the command pattern. The user
verified audio from machine 1 with `o1`, audio following the selected
channel with `o0`, and both audio routing and auto-scan affecting both
linked KVMs.

**Auto scan** combines stopping and choosing a scan interval in one
selector. Selecting a duration sends `s1` through `s5` and starts
automatic channel changes; selecting `Off` sends `s0`. The five durations
come from the device's interval replies. Only the 5-second scan has a
captured sequence of channel changes, and the user reported it disrupting
inputs while the monitors adjusted. A physical channel-button press does
not provide an explicit scan-off reply; the selector therefore waits for
`Auto Scan : OFF` to report `Off`.

The selector remains unknown until it receives either an explicit OFF
reply or both ON and a recognized interval. While scanning is on, it shows
the last reported interval; during a change, a new ON reply can arrive
before the new interval. The captured `k1p0` reports do not include scan
settings, so startup does not assume scanning is off.

The [UART board-selection capture](docs/commands.md#debug-capture-after-uart-board-selection-commands)
records `u1` reporting `UART to DP1-Board`, `u2` reporting
`UART to DP2-Board`, and `u0` reporting a return to `USB-Board` with later
diagnostics. These are available through the manual command action. Their
effect on later commands and scope in the daisy chain remain unconfirmed;
they are not exposed as routine controls or sent automatically. The
same capture records `v3p0` returning `ERROR`.

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

The [captured `K1P0` exchange](docs/commands.md#debug-capture-after-k1p0)
illustrates fragmented reads and trailing whitespace. The component version
line beginning `UDP2_14AP_U3` now identifies the device model. The DP
component version line and `V1P0` / `V1P1` remain unrecognized diagnostics;
this does not stop processing state feedback.

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
