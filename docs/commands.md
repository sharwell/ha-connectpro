# ConnectPro KVM command reference

This file records the ConnectPro KVM serial protocol details collected so
far from the current Home Assistant setup:

- `Configure serial port when Home Assistant starts`
- `Process serial sensor inputs`
- `shell_command.yaml`
- The script with alias `KVM - request channel`
- Dashboard channel buttons and the button labeled `Reset`

These sources establish port configuration, outgoing command payloads,
dashboard actions, and response-to-helper mappings. They do not include
raw command/response captures or establish the meanings of every command.

## Serial settings

`shell_command.configure_serial` runs this command:

```sh
stty -F /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AB0KK0CL-if00-port0 115200 cs8 -cstopb -parenb
```

The configured settings are:

- Baudrate: 115200 (`115200`)
- Data bits: 8 (`cs8`)
- Parity: none (`-parenb`)
- Stop bits: 1 (`-cstopb`)

Every supplied sender writes to that same device path. It identifies the
FTDI USB serial adapter in this installation; it is not a universal KVM
device path or a default to hard-code into the integration.

The command does not explicitly set hardware/software flow control,
raw/canonical mode, echo, or newline translation. Those effective terminal
settings cannot be determined from this command alone.

### Home Assistant startup

`Configure serial port when Home Assistant starts` runs on the
`homeassistant` start event, has no conditions, and calls
`shell_command.configure_serial` with no parameters. Its mode is `single`.

The supplied startup automation and shell command show no explicit retry
or recovery logic. They do not establish how configuration is ordered
relative to the serial sensor opening the port, or what happens after a
USB disconnect/reconnect.

## Command format

The supplied senders use `echo -e -n` and redirect output to the serial
device. They request an ASCII command followed by `\r\n` (CRLF), without
an additional newline from `echo`. Preserve payload case exactly: for
example, the action ending in `_ch1` writes `Ch1`, while `_v1p0` writes
`V1P0`. The command definitions do not establish whether the device accepts
other capitalization.

These are the intended write payloads. Raw captures would still be needed
to verify bytes on the wire, including any terminal output processing.

## Command catalog

All commands below append `\r\n` and target the device path above.

### Generic command

`shell_command.serial_command` accepts `command_text`. Its Jinja template
formats each character's ordinal as an uppercase hexadecimal escape with
at least two digits, then appends the CRLF escapes:

```jinja
{% for char in command_text %}\x{{ '%02X' % (char | ord) }}{% endfor %}\r\n
```

For example, `command_text: Ch2` renders `\x43\x68\x32\r\n`, requesting
bytes `43 68 32 0D 0A`. The sender writes the command text as bytes, not as
literal hexadecimal digits. The known command catalog is ASCII; this
example is derived from the template, not a captured device exchange.

### Fixed command actions

The file defines 55 fixed senders, in addition to the generic sender and
port configuration action. Each action below is in the `shell_command`
domain; for example, call `shell_command.serial_command_ch1` to write
`Ch1\r\n`.

| Action name (after `shell_command.`) | Command before CRLF |
| --- | --- |
| `serial_command_k1p0` | `k1p0` |
| `serial_command_k1p1` | `k1p1` |
| `serial_command_k1p2` | `k1p2` |
| `serial_command_k1p3` | `k1p3` |
| `serial_command_k1p4` | `k1p4` |
| `serial_command_ch1` | `Ch1` |
| `serial_command_ch2` | `Ch2` |
| `serial_command_ch3` | `Ch3` |
| `serial_command_ch4` | `Ch4` |
| `serial_command_bzon` | `bzon` |
| `serial_command_bzoff` | `bzoff` |
| `serial_command_ctrl` | `ctrl` |
| `serial_command_shift` | `shift` |
| `serial_command_scroll` | `scroll` |
| `serial_command_caps` | `caps` |
| `serial_command_h0p0` | `h0p0` |
| `serial_command_h1p1` | `h1p1` |
| `serial_command_h1p2` | `h1p2` |
| `serial_command_h1p3` | `h1p3` |
| `serial_command_h1p4` | `h1p4` |
| `serial_command_h2p1` | `h2p1` |
| `serial_command_h2p2` | `h2p2` |
| `serial_command_h2p3` | `h2p3` |
| `serial_command_h2p4` | `h2p4` |
| `serial_command_r0` | `R0` |
| `serial_command_o0` | `O0` |
| `serial_command_o1` | `O1` |
| `serial_command_o2` | `O2` |
| `serial_command_o3` | `O3` |
| `serial_command_o4` | `O4` |
| `serial_command_m1` | `M1` |
| `serial_command_m0` | `M0` |
| `serial_command_s0` | `S0` |
| `serial_command_s1` | `S1` |
| `serial_command_s2` | `S2` |
| `serial_command_s3` | `S3` |
| `serial_command_s4` | `S4` |
| `serial_command_s5` | `S5` |
| `serial_command_v0p0` | `V0P0` |
| `serial_command_v1p0` | `V1P0` |
| `serial_command_v1p1` | `V1P1` |
| `serial_command_v1p2` | `V1P2` |
| `serial_command_v1p3` | `V1P3` |
| `serial_command_v1p4` | `V1P4` |
| `serial_command_v2p0` | `V2P0` |
| `serial_command_v2p1` | `V2P1` |
| `serial_command_v2p2` | `V2P2` |
| `serial_command_v2p3` | `V2P3` |
| `serial_command_v2p4` | `V2P4` |
| `serial_command_w0` | `W0` |
| `serial_command_w1` | `W1` |
| `serial_command_w2` | `W2` |
| `serial_command_u0` | `U0` |
| `serial_command_u1` | `U1` |
| `serial_command_u2` | `U2` |

The request-channel script establishes `Ch1` through `Ch4` as channel
selection commands. The dashboard labels `W0` as `Reset`, but the scope of
that reset is not established. The remaining command meanings are still
unconfirmed; names alone do not prove a mapping to buzzer, hotkey, mouse,
audio, hub, or other features.

## Dashboard and channel request behavior

### Channel buttons

All four supplied channel buttons call `script.kvm_request_channel` with
the `channel` value below. The script with alias `KVM - request channel`
has the matching role, but its exported YAML omits its entity ID. Confirm
that ID to establish that it is the script referenced by the dashboard.

| Dashboard label | Requested helper option | Action in the supplied script | Command |
| --- | --- | --- | --- |
| Alpha | `Channel 1` | `shell_command.serial_command_ch1` | `Ch1` |
| Beta | `Channel 2` | `shell_command.serial_command_ch2` | `Ch2` |
| Gamma | `Channel 3` | `shell_command.serial_command_ch3` | `Ch3` |
| Delta | `Channel 4` | `shell_command.serial_command_ch4` | `Ch4` |

These labels are installation-specific names. Each button reads
`input_select.kvm_channel` and highlights its matching option with a
different icon and color. The cards hide the state text.

The supplied script uses `mode: single` and implements this sequence:

1. Read `input_select.kvm_channel` into `current`.
2. If `current` equals the requested `channel`, do nothing.
3. Otherwise, send the corresponding `Ch1`, `Ch2`, `Ch3`, or `Ch4` command
   for an exact `Channel 1` through `Channel 4` match. An unsupported value
   matches no branch and causes no command to be sent.

The script does not update the helper optimistically or wait for a
response. The serial sensor automation separately updates the helper from
`CH1`/`CH-1` through `CH4`/`CH-4`, which then drives button highlighting.
This provides a same-selection guard based on the helper's stored state;
it does not query the device to check that the helper is current. No retry
or response timeout is shown in the script.

### Reset button

The button labeled `Reset` directly calls
`shell_command.serial_command_w0`, which writes `W0\r\n`. It bypasses the
channel request script and has no channel-state guard. The snippet does
not show an expected response. The effect and scope of this reset remain
unknown; the label does not establish a factory reset.

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

## Examples and response correlation

The supplied configuration establishes these individual behaviors:

- A script request for `Channel 2`, when the helper has a different value,
  invokes `shell_command.serial_command_ch2` to write `Ch2\r\n`.
- Sensor state `CH-2` selects `Channel 2` on `input_select.kvm_channel`.
- Sensor state `Buzzer : OFF` turns off `input_boolean.kvm_buzzer`.
- Sensor state `SCROLL` selects `Scroll Lock` on `input_select.kvm_hotkey`.

These examples are not a captured exchange: the sources do not establish
which responses follow a particular command, or whether messages are
acknowledgments, unsolicited updates, or replies to a status query.
Response timing, ordering, and startup state discovery are also unknown.

## Details needed from the existing setup

To complete the reference, collect:

- The configuration that creates `sensor.serial_sensor`, including any
  decoding, line splitting, whitespace handling, and port settings applied
  by the sensor itself.
- Confirmation that the supplied request-channel script has entity ID
  `script.kvm_request_channel`.
- Other scripts, automations, or dashboard controls that call the listed
  senders or react to changes in the seven helpers above. These can
  establish the remaining command meanings, status queries, and any
  additional feedback-loop guards. The shell command definitions and
  channel/Reset dashboard actions are already recorded here.
- The helper definitions, especially the complete option lists for
  `input_select.kvm_audio`, `input_select.kvm_hub1`, and
  `input_select.kvm_hub2`.
- The actual effect of the `Reset` button (`W0`), including which state or
  settings it changes.
- Representative command/response captures, including startup or status
  queries and any audio/hub modes beyond `Sync`, plus the KVM model and
  firmware version to identify the scope of the observed behavior.
