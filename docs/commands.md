# ConnectPro KVM command reference

This file records the ConnectPro KVM serial protocol details collected so
far from the current Home Assistant setup:

- `Configure serial port when Home Assistant starts`
- `Process serial sensor inputs`
- The YAML definition of the stock serial sensor
- `shell_command.yaml`
- The script with alias `KVM - request channel`
- Dashboard channel buttons and the button labeled `Reset`
- An email transcript of the output reported after sending `K1P0`
- A debug log from manually sending `K1P0` through this integration on
  2026-10-01, with the user's daisy-chain context

These sources establish port configuration, outgoing command payloads,
dashboard actions, and response-to-helper mappings. The email transcript
associates one response report with `K1P0` without preserving raw bytes or
timing. The subsequent debug log preserves sent and received bytes, read
boundaries, and host log timestamps for another report. The meanings of
every command are not yet established.

The tables below preserve the original YAML setup as protocol evidence.
The integration now implements the confirmed channel and Reset actions,
receives the listed state feedback into native entities, and offers a
generic command action. See the [README](../README.md) for installation,
migration, and logging instructions. The old helpers and shell actions are
not required by the integration.

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
settings cannot be determined from this command alone; the serial sensor
also opens and configures the port.

### Supplied serial sensor configuration

The existing setup uses the stock serial sensor with this configuration:

```yaml
- platform: serial
  serial_port: /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AB0KK0CL-if00-port0
  baudrate: 115200
  bytesize: 8
  parity: N
  stopbits: 1
```

There is no `value_template` and no explicit `xonxoff`, `rtscts`, or
`dsrdtr` override. The current
[Home Assistant serial sensor implementation](https://github.com/home-assistant/core/blob/dev/homeassistant/components/serial/sensor.py)
defaults all three flow-control flags to false. It reads newline-delimited
bytes, decodes them as UTF-8, and strips leading and trailing whitespace
before exposing a sensor state. Thus the automation sees processed lines,
not raw bytes or terminators. The installed Home Assistant version and
raw captures would establish the exact historical behavior.

The ConnectPro integration configures the same 115200/8N1 settings and
disabled flow control when it opens the port; no separate serial sensor or
startup configuration command is needed. Existing entries with explicit
serial settings keep those values.

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
to verify the historical shell senders' bytes on the wire, including any
terminal output processing. The later integration debug capture records
the actual write passed to its serial transport as `b'K1P0\r\n'`.

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

### Report observed after `K1P0`

An old email records that the user ran uppercase `K1P0` and received the
following output, in this order:

```text
UDP2_14AP_U3 : Version_Number - 0009 - D1223
UDP2_14AP_DP : Version_Number - 0009 - D1223
CH-1
Hot KEY : CTRL
Buzzer : ON
HUB1 : Sync
HUB2 : Sync
AUDIO : Sync
Mouse change channel : OFF
V1P0
V1P1
K50_0 FW Ver B1.42
K50_1 FW Ver B1.42
K50_2 FW Ver B1.42
K50_3 FW Ver B1.42
K50_4 FW Ver B1.42
K50_5 FW Ver B1.42
K50_6 FW Ver B1.42
K50_7 FW Ver B1.42
```

This report includes feedback for all seven state categories handled by
the integration:

| Reported state | Value exposed by the integration |
| --- | --- |
| `CH-1` | Channel: `Channel 1` |
| `Hot KEY : CTRL` | Hotkey: `Ctrl` |
| `Buzzer : ON` | Buzzer: on |
| `HUB1 : Sync` | Hub 1 routing: `Sync` |
| `HUB2 : Sync` | Hub 2 routing: `Sync` |
| `AUDIO : Sync` | Audio routing: `Sync` |
| `Mouse change channel : OFF` | Mouse channel switching: off |

The two `UDP2_14AP_*` lines contain component identifiers and version
strings. They are preserved as evidence without assuming that either
identifier is the product's retail model number. The standalone `V1P0`
and `V1P1` lines match tokens in the outgoing command catalog, but their
meaning in this report is unknown; they are not established as echoes or
routing-state updates. The eight `K50_*` lines match firmware messages
already accepted by the original automation without a helper update.

The integration parses the seven known state lines and logs every raw
received byte at debug level. The component version lines and `V1P0` /
`V1P1` are currently logged as unrecognized; they do not interrupt the
reader or clear previously observed state. The email text is also stored
in [the regression fixture](../tests/fixtures/k1p0_report.txt).

In the original sensor automation, the two component version lines and
`V1P0` / `V1P1` would reach the `Unhandled state value` error branch. The
new integration keeps receiving subsequent lines after logging them.

The report suggests that `K1P0` could help obtain a status snapshot. It
does not establish that the command is a read-only query, whether it also
changes a setting, or how it differs from `K1P1` through `K1P4`. The state
before the command and any changes caused by it were not recorded. A
status report could accompany a command that changes configuration.

Preserve the distinction between uppercase `K1P0` in this observation and
lowercase `k1p0` in the existing shell command definition. Case equivalence
has not been demonstrated. The integration therefore does not send either
variant automatically on setup or reconnection. A manual or supervised
before/after observations are needed to establish the command's effect
before using it for automatic state discovery.

### Debug capture after `K1P0`

On 2026-10-01 the user manually sent `K1P0` through the integration's
command action. The debug log records this write at `10:33:20.713`:

```text
TX: b'K1P0\r\n'
```

The response arrived in eight reads containing 19 CRLF-terminated lines.
The [capture fixture](../tests/fixtures/k1p0_debug_capture.json) preserves
each read's exact bytes and timestamp separately from the earlier email.
The regression test replays these boundaries through the serial reader,
including lines split across reads and multiple lines within one read.

| RX timestamp | Elapsed from TX log timestamp |
| --- | --- |
| `10:33:20.721` | 8 ms |
| `10:33:20.723` | 10 ms |
| `10:33:20.726` | 13 ms |
| `10:33:20.729` | 16 ms |
| `10:33:20.735` | 22 ms |
| `10:33:20.746` | 33 ms |
| `10:33:20.752` | 39 ms |
| `10:33:20.766` | 53 ms |

These are host logging times for one exchange, without a timezone in the
supplied log. They do not establish wire timing, a response timeout, or a
marker for the end of a complete report. Read boundaries are transport
chunks, not protocol message boundaries.

After trimming outer whitespace, the lines have the same order and content
as the email report except for these two state values:

| State | Email report | Debug capture |
| --- | --- | --- |
| Channel | `CH-1` | `CH-2` |
| Buzzer | `Buzzer : ON` | `Buzzer : OFF` |

Both component version lines and all eight `K50_*` firmware lines contain
one trailing space before CRLF in the debug capture. The integration keeps
these bytes in its raw RX logs and strips outer whitespace for parsing.
The seven observed state values are therefore `Channel 2`, `Ctrl`, buzzer
off, mouse channel switching off, and `Sync` for both hubs and audio.

The debug log labels the two component version lines and `V1P0` / `V1P1`
as unrecognized, and all eight known firmware lines as ignored. These are
expected classifications, not reader errors; subsequent feedback remains
processable. The replay test verifies the seven state values, exact TX/RX
bytes, normalized lines, and these log classifications.

The user noted that daisy-chain linked devices, rather than one isolated
device, might explain differences. The changed channel and buzzer values
alone do not establish a daisy-chain effect. This capture does not identify
which linked device emitted each line, how many devices responded, or how
`K1P0` and `K1P1` through `K1P4` address or affect linked devices. Component
identifiers and the eight firmware lines do not prove a device count.
The integration currently exposes one device per serial connection; a
chain-aware entity model requires evidence of routing and addressing.

This capture confirms another report following uppercase `K1P0`, but does
not record state before the command or establish that it is read-only.
Lowercase equivalence and automatic state discovery remain unconfirmed.

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

The comparisons are exact, including case, internal spaces, and
punctuation. The automation itself does not trim whitespace or normalize
case. The stock serial sensor strips leading and trailing whitespace
before publishing its state, as described above. The configured sensor
has no additional value template. These are processed sensor state
strings. The later `K1P0` debug capture establishes CRLF response
terminators for that exchange; framing for other commands and hardware
configurations remains unverified.

For select helpers, the automation calls `input_select.select_option` with
the exact option shown below. For boolean helpers, it calls
`input_boolean.turn_on` or `input_boolean.turn_off` as indicated. These
helpers belong to the original hand-rolled setup. The integration exposes
a native channel select, sensors for hotkey/audio/hub modes, and binary
sensors for the two on/off states instead of writing these helpers.

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

### Firmware strings (ignored by the original automation)

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

These examples describe the supplied automation and script logic. The
`K1P0` email report above provides one command-associated response
sequence. The subsequent debug capture adds raw byte framing, read
boundaries, and host log timing for another such report. Neither records
before/after device state. The meaning of `K1P0`, acknowledgment rules,
and response origins within a daisy chain remain unknown.

## Current integration behavior

The integration owns the port for both reading and writing. It applies the
serial settings on connection, reconnects after connection failures, and
parses the confirmed feedback into native entities. It does not assume
that a successful write means the requested state has taken effect.
Values remain unknown until feedback arrives after connection. The
`K1P0` report is a candidate for future state discovery, but its effect
has not been confirmed, so no automatic startup or status command is sent.

The channel select sends `Ch1` through `Ch4`, and the Reset button sends
`W0`. Every valid channel selection sends a command, including a selection
that matches the last observed channel. Unlike the old script's guard,
this allows a quick change and change back before the first response
arrives. Other command meanings remain unconfirmed, so those features are
observed through sensors rather than exposed as controls. The
`connectpro.send_command` action accepts a ConnectPro `device_id` and a
single printable ASCII command line under `data`, and appends CRLF. This
provides a way to use known commands while collecting evidence for
additional features.

Debug logging records the device path, `TX`/`RX` direction, and escaped
bytes, including line endings. Unrecognized incoming messages are logged
without changing known state. These logs can correlate a sent command
with subsequent feedback, including messages that the original automation
did not recognize. See the
[debugging instructions](../README.md#debugging-serial-communication).

## Details needed from the existing setup

To complete the reference, collect:

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
- The documented purpose of `K1P0`, how `K1P1` through `K1P4` differ, and
  whether uppercase and lowercase variants behave identically. A manual
  or before/after state observations should establish whether these
  commands change any configuration.
- Before/after state observations and repeated captures with the chain
  topology identified, or a comparison with an isolated device, to establish
  command effects and the origin of responses. The existing `K1P0` debug
  capture already preserves bytes, timing, and read boundaries for one
  exchange.
- Startup/status behavior and any audio/hub modes beyond `Sync`, plus the
  retail KVM models and firmware versions to identify the scope of the
  observed behavior.
