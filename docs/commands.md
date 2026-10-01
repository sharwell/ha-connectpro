# ConnectPro KVM command reference

This file records the ConnectPro KVM serial protocol details collected so
far and the behavior of the current Home Assistant automations:

- `Configure serial port when Home Assistant starts`
- `Process serial sensor inputs`

The response mappings below come from those automations. Serial settings
and outgoing commands were recorded in earlier repository notes; the two
automations do not include the shell command definitions or demonstrate
which commands produce which responses.

## Serial settings

Earlier repository notes record these settings for the `stty`
configuration used outside the integration:

- Baudrate: 115200
- Data bits: 8
- Parity: none
- Stop bits: 1

### Home Assistant startup

`Configure serial port when Home Assistant starts` runs on the
`homeassistant` start event, has no conditions, and calls
`shell_command.configure_serial` with no parameters. Its mode is `single`.

The shell command body is not included in the supplied automation, so the
device path, full `stty` arguments (including flow control and terminal
modes), and failure handling still need to be recorded. The automation
does not show how configuration is ordered relative to the serial sensor
opening the port, or what happens after a USB disconnect/reconnect.

## Command format

Commands are ASCII text terminated with `\r\n` (CRLF). Case appears to be
significant for some commands.

## Command catalog

All commands below are sent with `\r\n` appended.

### Generic command

The existing setup supports sending an arbitrary command string by
encoding each character as a hex byte and writing the result to the
serial port.

### Known commands (meaning TBD)

- k1p0
- k1p1
- k1p2
- k1p3
- k1p4
- Ch1
- Ch2
- Ch3
- Ch4
- bzon
- bzoff
- ctrl
- shift
- scroll
- caps
- h0p0
- h1p1
- h1p2
- h1p3
- h1p4
- h2p1
- h2p2
- h2p3
- h2p4
- R0
- O0
- O1
- O2
- O3
- O4
- M1
- M0
- S0
- S1
- S2
- S3
- S4
- S5
- V0P0
- V1P0
- V1P1
- V1P2
- V1P3
- V1P4
- V2P0
- V2P1
- V2P2
- V2P3
- V2P4
- W0
- W1
- W2
- U0
- U1
- U2

## Response formats

### Input processing

`Process serial sensor inputs` uses a state trigger on
`sensor.serial_sensor`, with no `from`/`to` filters or conditions. It reads
`trigger.to_state.state` into `value` and selects the matching branch. Its
mode is `single`, and it retains 20 traces.

The comparisons are exact, including case, spaces, and punctuation. The
automation does not trim whitespace or normalize case. These are sensor
state strings; the supplied automation does not establish the raw serial
response terminator or any preprocessing performed by the sensor.

For select helpers, the automation calls `input_select.select_option` with
the exact option shown below. For boolean helpers, it calls
`input_boolean.turn_on` or `input_boolean.turn_off` as indicated. These
helpers belong to the current hand-rolled setup; the integration scaffold
does not yet expose corresponding entities.

### Channel updates

| Accepted sensor states | Helper | Option |
| --- | --- | --- |
| `CH1`, `CH-1` | `input_select.kvm_channel` | `Channel 1` |
| `CH2`, `CH-2` | `input_select.kvm_channel` | `Channel 2` |
| `CH3`, `CH-3` | `input_select.kvm_channel` | `Channel 3` |
| `CH4`, `CH-4` | `input_select.kvm_channel` | `Channel 4` |

### Buzzer state

| Accepted sensor states | Helper | Action |
| --- | --- | --- |
| `BZON`, `Buzzer : ON` | `input_boolean.kvm_buzzer` | Turn on |
| `BZOFF`, `Buzzer : OFF` | `input_boolean.kvm_buzzer` | Turn off |

### Mouse channel switching

| Accepted sensor state | Helper | Action |
| --- | --- | --- |
| `Mouse change channel : ON` | `input_boolean.kvm_mouse_change_channel` | Turn on |
| `Mouse change channel : OFF` | `input_boolean.kvm_mouse_change_channel` | Turn off |

### Audio/HUB mode

| Accepted sensor state | Helper | Option |
| --- | --- | --- |
| `AUDIO : Sync` | `input_select.kvm_audio` | `Sync` |
| `HUB1 : Sync` | `input_select.kvm_hub1` | `Sync` |
| `HUB2 : Sync` | `input_select.kvm_hub2` | `Sync` |

Only `Sync` responses are handled by this automation. Responses and helper
options for any independent audio or hub channel selection are not shown.

### Hotkey mode

| Accepted sensor states | Helper | Option |
| --- | --- | --- |
| `Hot KEY : CTRL`, `CTRL` | `input_select.kvm_hotkey` | `Ctrl` |
| `Hot KEY : SHIFT`, `SHIFT` | `input_select.kvm_hotkey` | `Shift` |
| `Hot KEY : SCROLL`, `SCROLL` | `input_select.kvm_hotkey` | `Scroll Lock` |
| `Hot KEY : CAPS`, `CAPS` | `input_select.kvm_hotkey` | `Caps Lock` |

### Firmware strings (ignored today)

- `K50_0 FW Ver B1.42`
- `K50_1 FW Ver B1.42`
- `K50_2 FW Ver B1.42`
- `K50_3 FW Ver B1.42`
- `K50_4 FW Ver B1.42`
- `K50_5 FW Ver B1.42`
- `K50_6 FW Ver B1.42`
- `K50_7 FW Ver B1.42`

These eight exact strings select an empty sequence: no helper is changed
and no error is raised. This is not a general firmware-message pattern;
other firmware versions or identifiers fall through to the default branch.

### Unhandled values

Every other value reaches a `stop` action with the reason
`Unhandled state value` and `error: true`. This includes unexpected
capitalization or spacing, unlisted firmware messages, and values such as
`unknown` or `unavailable` if passed through this state trigger. The
automation does not contain a fallback parser or recovery action.

## Example exchanges

The supplied automations show sensor-to-helper updates, for example:

- Sensor state `CH-2` selects `Channel 2` on `input_select.kvm_channel`.
- Sensor state `Buzzer : OFF` turns off `input_boolean.kvm_buzzer`.
- Sensor state `SCROLL` selects `Scroll Lock` on `input_select.kvm_hotkey`.

Command/response exchanges remain undocumented. Neither supplied
automation shows a transmitted KVM command or establishes whether
responses are acknowledgments, unsolicited updates, or replies to a
status query. Response timing, ordering, and startup state discovery are
also unknown.

## Details needed from the existing setup

To complete the reference, collect:

- The definition of `shell_command.configure_serial`, including the serial
  device path and all port configuration arguments.
- The configuration that creates `sensor.serial_sensor`, including any
  decoding, line splitting, or whitespace handling.
- Shell commands, scripts, and automations that send commands or react to
  changes in the seven helpers listed above. These can establish command
  meanings, write formatting, status queries, and any feedback-loop guards.
- The helper definitions, especially the complete option lists for
  `input_select.kvm_audio`, `input_select.kvm_hub1`, and
  `input_select.kvm_hub2`.
- Representative command/response captures, including startup or status
  queries and any audio/hub modes beyond `Sync`, plus the KVM model and
  firmware version to identify the scope of the observed behavior.
