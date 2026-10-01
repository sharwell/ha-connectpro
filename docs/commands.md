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
- A later debug log and physical observations of `K1P1`, `K2P1`, and
  channel-2 button presses in a two-KVM chain on 2026-10-01
- A subsequent capture of `K1P1`, `K1P0`, and a physical channel-2 button
  press on 2026-10-01, plus a separate captured `K2P0` / `ERROR` exchange
- A captured `W0` exchange on 2026-10-01 and the user's observation that
  all displays cycled off and on; later channel feedback was unrelated
- A captured `bzon`, `BZON`, and `BZOFF` sequence on 2026-10-01, with
  matching `BZON` / `BZOFF` feedback, audible buzzer confirmation, and
  the user's qualified report that the commands appear to affect both KVMs
- A captured sequence of lowercase hotkey commands and lowercase/uppercase
  mouse channel-switching commands on 2026-10-01, with physical verification
  of both features and their effect on both linked KVMs
- The user's confirmation on 2026-10-01 that lowercase `k1p0` can obtain
  current entity state after loading, configuring, and initializing the
  integration
- A captured sequence of lowercase USB hub and video routing commands on
  2026-10-01, including a rejected `h1p0`, a two-hub Sync reset, and both
  global and individual video Sync replies; the user observed Hub 1 being
  assigned to machine 2 on both linked KVMs independently of the channel,
  followed by physical confirmation of Video 1's fixed routing across both
  units and its independent return to Sync
- Captured lowercase UART board-selection commands and a rejected `v3p0`
  on 2026-10-01, including component version and `Ready-0` diagnostics
- Captured lowercase audio and auto-scan commands on 2026-10-01, with all
  five scan interval replies and 5-second channel cycling; the user
  subsequently verified audio fixed/following behavior and the effect of
  both audio routing and auto-scan on both linked KVMs
- The user's confirmation that the `UDP2_14AP_U3` identifier in a `k1p0`
  report identifies the retail model `UDP2-14AP`; response indicators for
  other models have not been supplied
- The 2013 StarTech SV231DVIUDDM manual's serial command table, used as
  comparison evidence rather than a ConnectPro protocol specification

These sources establish port configuration, outgoing command payloads,
dashboard actions, and response-to-helper mappings. The email transcript
associates one response report with `K1P0` without preserving raw bytes or
timing. The subsequent debug logs preserve sent and received bytes, read
boundaries, and host log timestamps. The targeted channel test also records
which physical KVM changed channel. The meanings of every command are not
yet established.

The tables below preserve the original YAML setup as protocol evidence.
The integration now implements channel and hotkey selection, buzzer and
mouse channel-switching controls, auto-scan selection, the `W0` display
action, and USB/video/audio Sync actions. It receives the listed state
feedback into native entities and offers a generic command action. See
the [README](../README.md) for installation, migration, and logging
instructions. The old helpers and shell actions are not required by the
integration.

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
selection commands. The dashboard labels `W0` as `Reset`; a later capture
and physical observation below associate it with displays cycling off
and on and the reply `Wake-Up : DP-ALL`. The targeted channel test below
establishes effects for uppercase `K1P1` and `K2P1` in one two-KVM chain;
it does not verify every lowercase sender above. A subsequent buzzer
capture confirms `bzon` and `BZON` receiving `BZON`, and `BZOFF`
receiving `BZOFF`. The lowercase `bzoff` sender remains untested in these
captures. The hotkey and mouse capture below establishes command-associated
feedback for `ctrl`, `shift`, `scroll`, `caps`, and both cases of `M0` /
`M1`. The routing capture below establishes replies for lowercase `h1p2`,
`h0p0`, `v1p2`, `v0p0`, and `v1p0`, and rejection of `h1p0`. Subsequent
captures below establish lowercase `o1` / `o0` audio routing replies,
`s0` through `s5` auto-scan settings, and `u0` / `u1` / `u2` UART
board-selection replies. Uppercase `O`, `S`, and `U` payloads in the
original inventory are not separately verified by these lowercase tests.
Other command meanings remain unconfirmed on this hardware.

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

This report includes feedback for the seven original entity-state
categories handled by the integration:

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
strings. The user subsequently confirmed that `UDP2_14AP_U3` identifies
retail model `UDP2-14AP`; the integration now uses that specific mapping
for device metadata, as detailed below. The standalone `V1P0`
and `V1P1` lines match tokens in the outgoing command catalog, but their
meaning in this report is unknown; they are not established as echoes or
routing-state updates. The eight `K50_*` lines match firmware messages
already accepted by the original automation without a helper update.

The integration parses the seven entity-state lines and the confirmed
model identifier, and logs every raw received byte at debug level. The DP
component version line and `V1P0` / `V1P1` remain unrecognized; they do not interrupt the
reader or clear previously observed state. The email text is also stored
in [the regression fixture](../tests/fixtures/k1p0_report.txt).

In the original sensor automation, the two component version lines and
`V1P0` / `V1P1` would reach the `Unhandled state value` error branch. The
new integration keeps receiving subsequent lines after logging them.

The email associates `K1P0` with the seven recognized state categories,
but does not record raw bytes or before/after observations. Later captures
preserve its status output, and the user subsequently confirmed lowercase
`k1p0` can obtain current entity state after initialization. The targeted
channel test below separately establishes `K1P1` channel-selection behavior.

Preserve uppercase `K1P0` in this historical observation and lowercase
`k1p0` in the existing shell command definition. The later user confirmation
supports using the lowercase command for
[automatic state initialization](#automatic-state-initialization); no new
raw lowercase status exchange was supplied with that confirmation.

### Model identification

The user confirmed that `UDP2_14AP_U3` in a `k1p0` report identifies this
device's retail model as `UDP2-14AP`. This confirmation adds meaning to
the previously captured bytes; no new hardware exchange was supplied.
The only known model mapping is:

| Report identifier | Home Assistant device model |
| --- | --- |
| `UDP2_14AP_U3` | `UDP2-14AP` |

The parser recognizes a complete line beginning exactly
`UDP2_14AP_U3 : Version_Number - ` with a nonempty version suffix. Model
identification is tied to the exact component identifier rather than the
captured `0009 - D1223` version, so a different version suffix can still
identify the same model. Partial lines, empty suffixes, other identifiers,
lookalike prefixes, and case variants do not identify a device. There is
no general underscore-to-hyphen transformation, and the DP-only identifier
does not establish a model.

Home Assistant exposes model information on the integration's device
page. Once the response arrives, the integration updates the existing
device registry record using its current identifier. The entity/device
names and unique IDs remain unchanged, and no extra metadata sensor is
created. Registry updates run from the shared connection's subscription,
so model identification does not depend on an individual entity being
enabled. Duplicate reports do not rewrite an unchanged model. The
subscription is removed when the integration unloads.

The model is descriptive metadata: the device registry retains its last
identified model while a disconnected client clears live state and retries.
A device with no recognized model has no model supplied by this mapping.
The firmware suffix and the separate DP/`K50_*` version lines are not
mapped to a device firmware version. This report describes one serial
connection; it does not identify the models of linked KVMs separately.

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

The original debug log labels the two component version lines and `V1P0`
/ `V1P1` as unrecognized, and all eight known firmware lines as ignored.
Following the user's model confirmation, the current parser recognizes
the U3 line as model metadata; the DP line and the two video tokens remain
unrecognized. These diagnostics do not prevent later state processing.
The replay test verifies the seven entity-state values, the model, exact
TX/RX bytes, normalized lines, and the current log classifications. The
raw capture retains the original historical diagnostics.

The user noted that daisy-chain linked devices, rather than one isolated
device, might explain differences. The changed channel and buzzer values
alone do not establish a daisy-chain effect. This capture does not identify
which linked device emitted each line, how many devices responded, or how
`K1P0` and `K1P1` through `K1P4` address or affect linked devices. Component
identifiers and the eight firmware lines do not prove a device count.
The later targeted channel test below supplies additional addressing
evidence. The integration still exposes one device per serial connection;
separate entities for linked units require feedback that can identify
each unit's state.

This capture confirms another report following uppercase `K1P0`, but does
not record state before the command or establish that it is read-only.
The later user confirmation establishes lowercase `k1p0` as a way to
obtain current entity state; this earlier capture itself tests uppercase.

### Targeted channel switching in a two-KVM chain

On 2026-10-01 the user tested uppercase `K1P1` and `K2P1` through the
integration's manual command action, with physical channel-2 button
presses between and after them. The user observed these results separately
from the serial log:

| Step | Action | First KVM afterward | Second KVM afterward |
| --- | --- | --- | --- |
| 1 | Send `K1P1` | Channel 1 | Channel 2 |
| 2 | Press physical channel-2 button | Channel 2 | Channel 2 |
| 3 | Send `K2P1` | Channel 2 | Channel 1 |
| 4 | Press physical channel-2 button | Channel 2 | Channel 2 |

The [capture fixture](../tests/fixtures/targeted_channel_debug_capture.json)
preserves the seven ordered TX/RX events, exact bytes, host log timestamps,
and separate physical observations. The serial sequence was:

| Host log timestamp | Direction | Bytes |
| --- | --- | --- |
| `10:58:57.573` | TX | `b'K1P1\r\n'` |
| `10:58:57.596` | RX | `b'OK\r\n'` |
| `10:59:36.800` | RX | `b'CH2\r\n'` |
| `11:00:00.161` | TX | `b'K2P1\r\n'` |
| `11:00:00.169` | RX | `b'K1P1\r\n'` |
| `11:00:07.098` | RX | `b'CH2'` |
| `11:00:07.102` | RX | `b'\r\n'` |

This confirms selective switching for the two commands and two units
tested: `K1P1` changes the first KVM to channel 1 without changing the
second, and `K2P1` changes the second without changing the first. The
physical channel-2 action changes both units to channel 2. That physical
action supplies no integration TX event. The log does not identify which
unit emitted each reply.

The [2013 StarTech SV231DVIUDDM manual](https://images10.newegg.com/UploadFilesForNewegg/itemintelligence/STARTECH/SV231DVIUDDM_Manual1401397479455.pdf#page=7),
printed page 4 / PDF page 7, describes `k1pY` as console channel selection
and `kXpY` for levels above 1 with a reported token whose level is reduced
by one. The observed `K2P1` to `K1P1` response matches that pattern. It is
consistent with addressing or forwarding to the next KVM, but the host
capture does not show traffic on the link between units and does not prove
the forwarding mechanism. The response is not an exact echo of the sent
command. The manual belongs to a different vendor and model.

The same table labels `chX` as synchronized channel selection. This test
does not send `Ch1`, so it does not confirm that serial `Ch1` switches both
linked units or establish what synchronized switching includes. Additional
ports, levels, chain lengths, and lowercase equivalence remain untested.
`K1P0` status-report behavior should not be generalized to `K2P0`; the
additional capture below shows `K2P0` receiving `ERROR`.

The integration currently logs `OK` and received `K1P1` as unrecognized
lines without changing state. Neither is an addressed channel-state
report: `OK` contains no channel or unit, and received `K1P1` is not
established as state feedback. The Channel entity retains the last
recognized unaddressed `CHn` / `CH-n` value on the serial connection. It
can therefore retain `Channel 2` while the physical units differ after a
targeted manual command. It does not report the state of each linked unit
or establish that the chain is synchronized.

The replay regression verifies both manual writes, raw RX logging, and
that these two non-state replies do not fabricate a channel update. The
final split `CH2` produces one state report only when the terminator
arrives, and the reader stays connected without sending extra commands.

### Local status after targeted channel selection

The next supplied debug log records `K1P1`, then `K1P0`, followed by a
physical channel-2 button press on 2026-10-01. The
[capture fixture](../tests/fixtures/local_status_after_targeted_switch.json)
preserves all 21 ordered raw TX/RX events, timestamps, and read boundaries.
The sequence is:

| Action | TX timestamp | Received output |
| --- | --- | --- |
| Send `K1P1` | `11:10:25.613` | `OK\r\n` at `11:10:25.635` |
| Send `K1P0` | `11:10:33.025` | 19-line report in 17 reads from `11:10:33.030` to `11:10:33.077` |
| Press physical channel-2 button | No integration TX | `CH2\r\n` at `11:10:41.945` |

The `K1P0` report contains `CH-1`. Reassembling its 378 bytes yields
exactly the earlier debug report with `CH-2` changed to `CH-1`; all other
bytes, including trailing spaces and CRLF terminators, match. Buzzer
remains `OFF`, hotkey `CTRL`, mouse channel switching `OFF`, and both
hubs and audio `Sync`. Component versions remain `0009 - D1223`, and
the eight firmware messages remain `B1.42`. `V1P0` and `V1P1` are unchanged.

Together with the prior physical observation that `K1P1` switches the
first KVM, the matching `CH-1` supports interpreting `K1P0` as a status
request for the first/local unit. It is not evidence of a synchronized
whole-chain channel state or an addressed report for each linked unit.
The host capture alone does not identify the source of every version or
state line. The user did not supply an additional physical before/after
comparison of other settings for this sequence, so it does not establish
that `K1P0` is read-only in every respect.

The reader leaves state unchanged after `OK`, identifies the model from
the complete U3 line, updates channel to `Channel 1` from `CH-1`, fills
the other six original entity-state categories,
then updates only channel to `Channel 2` after the physical-button `CH2`.
The replay regression verifies these transitions, the exact command writes
and raw reads, existing unknown/ignored diagnostics, continued connection,
and the absence of unsolicited commands. The captured timestamps are host
log times, not protocol response deadlines.

The user separately supplied the earlier unsuccessful `K2P0` attempt,
preserved in its own
[capture fixture](../tests/fixtures/k2p0_error_debug_capture.json):

| Direction | Timestamp | Raw bytes |
| --- | --- | --- |
| TX | `11:07:43.429` | `b'K2P0\r\n'` |
| RX | `11:07:43.437` | `b'ERROR\r\n'` |

This is an explicit error reply, not a missing response. It rejects this
attempt to retrieve the second KVM's status, despite `K2P1` successfully
selecting that unit's channel. This supports treating `K1P0` as a special
local status request rather than assuming `KxP0` works for every chain
level. It does not establish whether the error came from the first KVM or
a downstream unit, or whether another command can retrieve downstream
status. The reader logs `ERROR` as an unrecognized line without changing
observed state, disconnecting, or retrying the command.

### Debug capture after `W0`

On 2026-10-01 the user manually sent `W0` through the integration. The
[capture fixture](../tests/fixtures/w0_debug_capture.json) preserves all
six ordered raw TX/RX events and the unrecognized-line diagnostic:

| Direction | Timestamp | Raw bytes |
| --- | --- | --- |
| TX | `11:18:27.291` | `b'W0\r\n'` |
| RX | `11:18:27.392` | `b'W'` |
| RX | `11:18:27.394` | `b'ake-Up : DP-'` |
| RX | `11:18:27.399` | `b'ALL\r\n'` |
| RX | `11:22:48.045` | `b'CH1\r\n'` |
| RX | `11:22:50.724` | `b'CH2\r\n'` |

The first three reads form one line, `Wake-Up : DP-ALL`, logged as
unrecognized at `11:18:27.400`. The user observed all displays resetting
off and on. They suggested this might cause connected computers to
redetect the displays; that computer-side effect is a hypothesis, not a
confirmed observation. The response text suggests a DisplayPort wake-up
operation, while the observed off/on cycle establishes the display effect
in this installation. The capture does not establish a factory reset,
KVM reboot, settings reset, or the scope of `DP-ALL` in other topologies.

The user explicitly confirmed that the later `CH1` and `CH2` reports were
unrelated to `W0`. They are ordinary channel feedback, not evidence that
the display operation switches channels. The response timestamps are host
log times; the three wake-up reads arrived 101, 103, and 108 ms after TX,
without establishing a guaranteed response deadline.

The reader does not change observed state for `W0` or `Wake-Up : DP-ALL`.
The replay regression verifies the exact write and raw reads, one
unrecognized-line diagnostic after the full line arrives, later channel
updates to `Channel 1` and `Channel 2`, continued connection, and no extra
commands. The response is not treated as a persistent display-power state.

### Debug capture after buzzer commands

On 2026-10-01 the user sent lowercase `bzon`, uppercase `BZON`, then
uppercase `BZOFF` through the integration. They heard the buzzer and
reported that the commands appear to affect both linked KVMs. The
[capture fixture](../tests/fixtures/buzzer_debug_capture.json) preserves
all seven ordered raw TX/RX events and their read boundaries:

| Command | TX timestamp | Received output |
| --- | --- | --- |
| `bzon` | `11:43:56.563` | `BZON\r\n` at `11:43:56.583` |
| `BZON` | `11:44:03.932` | `B` at `11:44:03.966`, then `ZON\r\n` at `11:44:03.968` |
| `BZOFF` | `11:44:24.229` | `BZOFF\r\n` at `11:44:24.251` |

These replies use the buzzer state strings already handled by the
original automation and integration. They report on, on again, then off.
The native Buzzer switch uses uppercase `BZON` and `BZOFF`, since both
were tested. The on-command variants produced identical normalized
feedback, but this does not establish general case insensitivity,
lowercase `bzoff` equivalence, or command behavior on other firmware.
The host log does not identify which unit emitted the replies. The user's
observation suggests a chain-wide effect in this installation, but does
not supply isolated per-unit verification or establish the scope in
other chain topologies.

The reader waits for the complete split `BZON` line before processing it.
Neither an outgoing command nor the partial `B` changes observed state.
Repeated complete `BZON` feedback retains on without creating a second
state-change notification; `BZOFF` changes the observed state to off.
The replay regression verifies the three exact writes, four raw reads,
complete-line parsing, state changes, continued connection, and no extra
commands. Captured host timestamps do not establish response deadlines.

### Debug capture after hotkey and mouse commands

On 2026-10-01 the user tested the hotkey settings and mouse channel
switching through the integration's manual command action. The
[capture fixture](../tests/fixtures/hotkey_mouse_debug_capture.json)
preserves all 33 ordered events: ten command writes and 23 raw reads.
The user also verified the selected hotkeys and mouse channel switching
in use and confirmed that the changes affect both linked KVMs.

| Command | TX timestamp | Complete reply | RX read count |
| --- | --- | --- | --- |
| `shift` | `11:47:29.032` | `SHIFT\r\n` | 2 |
| `ctrl` | `11:47:34.035` | `CTRL\r\n` | 2 |
| `scroll` | `11:47:41.567` | `SCROLL\r\n` | 2 |
| `ctrl` | `11:47:45.485` | `CTRL\r\n` | 2 |
| `caps` | `11:49:13.568` | `CAPS\r\n` | 1 |
| `ctrl` | `11:49:17.377` | `CTRL\r\n` | 2 |
| `m0` | `11:49:24.336` | `Mouse change channel : OFF\r\n` | 4 |
| `M0` | `11:49:35.329` | `Mouse change channel : OFF\r\n` | 3 |
| `M1` | `11:49:40.604` | `Mouse change channel : ON\r\n` | 3 |
| `m1` | `11:49:46.359` | `Mouse change channel : ON\r\n` | 2 |

All ten complete replies match the existing parser and original automation.
The hotkey state progresses through `Shift`, `Ctrl`, `Scroll Lock`, `Ctrl`,
`Caps Lock`, and `Ctrl`. Mouse channel switching then reports off twice,
followed by on twice. The Hotkey selector maps these four options to the
tested lowercase commands. The Mouse channel switching switch uses tested
uppercase `M1` for on and `M0` for off.

Both cases of the two mouse commands produced identical normalized
feedback. Uppercase hotkey commands were not tested, and this capture
does not establish general case insensitivity for other commands or
firmware. The host log does not identify which KVM produced each reply.
The physical observation establishes effects on both units in this
installation, without establishing behavior in other chain topologies.
The mouse gesture used was not specified.

The reader waits for each complete line; fragments such as `SHIF` or
`Mouse cha` are not state reports. Outgoing commands do not update state.
The replay regression verifies all ten writes, 23 reads, and ten parsed
lines. There are eight state-change notifications: six hotkey changes and
two mouse changes. The repeated off/on mouse replies are parsed without
duplicate notifications. The connection remains open and no extra commands
are sent. Timestamps describe the host log, not response deadlines.

### Debug capture after USB hub and video routing commands

On 2026-10-01 the user sent six lowercase commands through the integration.
The [capture fixture](../tests/fixtures/routing_debug_capture.json)
preserves all 20 ordered events: six writes and 14 raw reads, with their
original case, read boundaries, and host timestamps.

| Command | TX timestamp | Complete reply | RX read count |
| --- | --- | --- | --- |
| `h1p2` | `12:14:27.260` | `HUB1 : Async-> Channel 2\r\n` | 3 |
| `h1p0` | `12:15:37.241` | `ERROR\r\n` | 1 |
| `h0p0` | `12:15:43.736` | `HUB1 : Sync\r\nHUB2 : Sync\r\n` | 1 |
| `v1p2` | `12:18:14.604` | `Video1 : ASYNC-mode-Port2\r\n` | 3 |
| `v0p0` | `12:19:00.481` | `Video-ALL : SYNC-mode\r\n` | 3 |
| `v1p0` | `12:20:12.449` | `Video1 : SYNC-mode\r\n` | 3 |

The user observed `h1p2` assigning USB Hub 1 on both linked KVMs to
machine 2 even when the current channel was different. Its reply updates
Hub 1 routing to `Channel 2`. In this context, Async describes a fixed
assignment independent of the selected KVM channel. The user described
`h0p0` as restoring both hubs to Sync, and its two replies report that
state individually. Sync denotes routing that follows the selected
channel, according to the user's description of the mapping behavior.

`h1p0` returned `ERROR`. It must not be used as an individual Hub 1 Sync
command. The user has not found a way to restore one hub without also
restoring the other; this establishes the tested command's limitation,
not that every firmware necessarily lacks such a command. The capture
does not establish asynchronous routing commands for Hub 2 or other
destination channels.

The user described video routing as appearing to work similarly. `v1p2`
reports Video 1 assigned to port 2, `v0p0` reports all video in Sync, and
`v1p0` reports Video 1 in Sync. Unlike `h1p0`, `v1p0` produced recognized
Sync feedback. Video commands therefore have a confirmed individual
Sync form for Video 1 as well as a global Sync form. In a subsequent
confirmation, the user verified `v1p2` physically pinning Video 1 to
machine 2 on both linked KVMs, and `v1p0` restoring only Video 1 while
leaving another pinned video output unchanged. This confirms the
individual output's physical effect and scope in this installation.
Other output/port combinations and uppercase equivalents remain untested
in these captures, even where the earlier shell command inventory lists
similar spellings.

The native parser recognizes the four new exact reply forms. The global
video Sync reply updates the confirmed Video 1 state; it does not create
additional video entities. The bare `V1P0` and `V1P1` tokens in the earlier
`K1P0` reports remain unrecognized: they are different from these routing
replies, and their meaning in those reports is still unknown. Those
reports therefore do not currently initialize video routing state.

The device page provides **Sync both USB hubs** (`h0p0`), **Sync video
output 1** (`v1p0`), and **Sync all video outputs** (`v0p0`) buttons.
Their names make the global versus individual scope explicit. Routing
sensors retain the observed hub settings and add Video 1 routing. They
remain necessary because these buttons request actions rather than select
and report a complete routing setting. Fixed assignments such as `h1p2`
and `v1p2` are available through the manual command action. Full routing
selectors are deferred until additional destination/output combinations
are established; no temporary Channel 2-only selectors are created.

The replay verifies all six writes, 14 reads, and seven complete reply
lines. Hub 1 progresses from `Channel 2` to `Sync`, Hub 2 reports `Sync`,
and Video 1 progresses from `Channel 2` to `Sync`. The final individual
video Sync reply repeats the state already reported by the global reply.
There are five state-change notifications; `ERROR` remains a debug
diagnostic without changing state or closing the connection. No write
alone establishes a state change, and no additional commands are sent.

### Debug capture after UART board-selection commands

The user supplied the following sequence on 2026-10-01. The
[capture fixture](../tests/fixtures/uart_debug_capture.json) preserves
all 35 ordered events (six writes and 29 reads), including leading/trailing
spaces and standalone CR/LF reads. The leading `v1p0` exchange repeats
the same timestamped exchange in the previous routing capture; it is not
evidence of a second independent test.

| Command | TX timestamp | Normalized reply lines |
| --- | --- | --- |
| `v1p0` | `12:20:12.449` | `Video1 : SYNC-mode` |
| `v3p0` | `12:21:08.137` | `ERROR` |
| `u1` | `12:27:45.495` | `UART to DP1-Board`; `UDP2_14AP_DP : Version_Number - 0009 - D1223` |
| `u0` | `12:28:06.651` | `UART connect to USB-Board`; `Ready-0` |
| `u2` | `12:29:42.197` | `UART to DP2-Board`; `UDP2_14AP_DP : Version_Number - 0009 - D1223` |
| `u0` | `12:29:46.437` | `UART connect to USB-Board`; `UDP2_14AP_DP : Version_Number - 0009 - D1223`; `Ready-0` |

The wording suggests selecting an internal board's UART command path:
`u1` reports DP1, `u2` reports DP2, and `u0` reports USB. This is an
inference from the replies; the capture does not establish what later
commands do on each path. DP1/DP2 board labels must not be equated with
the first/second daisy-chained KVM without additional evidence. These
commands are also distinct from the USB hub's computer routing commands.

Both DP selections return the same component-version text. That text
also appears after the second USB return, so timing alone does not
establish which board originated a version line or whether it describes
the newly selected board. `Ready-0` follows both returns, but its exact
meaning is unknown. Neither diagnostic is treated as a required startup
handshake, a confirmation of channel state, or a trigger for reconnection.
The integration does not send `u0` automatically.

The eleven normalized lines include one recognized Video 1 Sync reply
and ten diagnostics. The normalized UART, version, `Ready-0`, and `ERROR`
lines remain debug diagnostics without entity updates. The initial `Video1 : SYNC-mode`
updates Video 1 through the existing parser. `v3p0` returned `ERROR`;
this rejects that exact lowercase command in the tested setup, without
establishing a general maximum output count or proving that all related
commands are invalid.

For `u1`, the version line ends with CR in the read at `12:27:45.626`,
and LF arrives separately at `12:27:45.628`. Other reads contain CRLF
followed by an extra CR. Existing line framing and outer-whitespace
trimming handle these forms without treating fragments or blank lines as
state. Replay coverage preserves those boundaries, checks raw logging,
and verifies that diagnostic replies do not close the serial connection
or cause additional writes.

### Debug capture after audio and auto-scan commands

On 2026-10-01 the user tested audio routing and all five scan settings.
The [capture fixture](../tests/fixtures/audio_scan_debug_capture.json)
preserves all 58 ordered events (eleven writes and 47 reads), with the
exact lowercase writes, fragmented reads, and host times.

| Command | TX timestamp | Complete reply lines |
| --- | --- | --- |
| `o1` | `12:30:25.726` | `AUDIO : CHANNEL1` |
| `o0` | `12:30:35.452` | `AUDIO : Sync` |
| `s1` | `12:30:57.101` | `Auto Scan : ON`; `Auto Scan : 1(5sec)` |
| `s0` | `12:32:31.166` | `Auto Scan : OFF` |
| `s2` | `12:33:02.374` | `Auto Scan : ON`; `Auto Scan : 2(8Sec)` |
| `s0` | `12:33:06.892` | `Auto Scan : OFF` |
| `s3` | `12:33:12.621` | `Auto Scan : ON`; `Auto Scan : 3(15Sec)` |
| `s0` | `12:33:16.075` | `Auto Scan : OFF` |
| `s4` | `12:33:20.458` | `Auto Scan : ON`; `Auto Scan : 4(20Sec)` |
| `s5` | `12:33:23.871` | `Auto Scan : ON`; `Auto Scan : 5(30Sec)` |
| `s0` | `12:33:27.293` | `Auto Scan : OFF` |

The user subsequently verified `o1` routing audio from machine 1 and
`o0` restoring audio following the selected channel. Audio routing and
auto-scan affect both linked KVMs in this installation. The log does not
identify which unit originated each serial reply. The Audio routing
sensor now maps `AUDIO : CHANNEL1` to `Channel 1`, alongside the existing
`Sync` mapping. **Sync audio** sends the tested lowercase `o0`; the manual
command action can send `o1`. Other fixed audio destinations still need
captured replies before a complete audio selector is introduced.

Every nonzero scan command reports ON followed by its interval; it starts
scanning rather than merely storing a duration. The native **Auto scan**
selector exposes `Off` (`s0`), `5 seconds` (`s1`), `8 seconds` (`s2`),
`15 seconds` (`s3`), `20 seconds` (`s4`), and `30 seconds` (`s5`). These
labels come from the exact reported intervals, including the different
`sec` / `Sec` spellings. Other spellings or interval combinations are not
accepted as state without further evidence.

After `s1`, channel feedback runs through `CH3`, `CH4`, `CH1`, `CH2`
twice from `12:31:02.107` through `12:31:37.171`, about five seconds
apart. The user reported scanning disrupting inputs faster than the
monitors could adjust and manually pressed a button to return to channel
2. The extra `CH2` at `12:31:40.654` does not include `Auto Scan : OFF`.
The integration therefore preserves the last explicitly reported scan
setting until `s0` produces OFF at `12:32:31.190`. The capture does not
measure channel dwell times for the other four intervals; those durations
are established by their interval replies.

Scan enabled state and the last reported interval are stored separately.
OFF makes the selector show `Off` regardless of an earlier interval.
ON with no recognized interval, or an interval with no enabled-state
report, leaves it unknown. While ON, it displays the last reported
interval until a newer interval arrives. This includes the direct
`s4` to `s5` change, whose repeated ON reply does not itself establish
the new duration. Selecting any valid option always sends its command;
the selection does not optimistically change state or suppress a request
that matches stale feedback. Channel reports only update channel state.

The captured `k1p0` reports do not include scan enabled state or interval,
so those values remain unknown after initialization until explicit scan
feedback arrives. No scan command is sent automatically, and no separate
scan compatibility sensor is created. The replay verifies all 25 complete
lines, framing, feedback-only state changes, duplicate suppression, and
continued connection across the entire sequence. The duplicate manual
`CH2` and the repeated ON during the direct interval change produce no
additional state notification.

### Automatic state initialization

The user confirmed that lowercase `k1p0` can obtain current state for the
entities after the integration is loaded, configured, and initialized.
This confirmation is separate from the earlier raw uppercase `K1P0`
captures; no new raw exchange accompanies it.

The integration opens and configures the serial port, initializes the
entity platforms, then starts its reader and sends `b'k1p0\r\n'` once on
that connection. It sends the same request once after each successful
reconnect, since disconnecting clears previously observed state. Temporary
serial-port checks in the configuration flow only open and close the port;
they do not send a status request or other KVM commands.

The request uses the normal serialized command path and TX logging. The
reply uses normal RX logging, line framing, and parsing. Each recognized
line supplies its observed state; a write alone does not populate entities.
Initialization does not wait for a complete status handshake or poll
periodically. If the write fails, the reader uses the existing bounded
reconnect backoff and requests state on the replacement connection.

The status response is consistent with the first/local KVM and does not
create per-unit state for a chain. `K2P0` returned `ERROR` in the supplied
capture and is not sent automatically. The confirmed U3 identifier
supplies device model metadata; other component versions, video tokens,
and firmware diagnostics continue through the normal logging behavior.

Lifecycle tests verify the initial request, received state, reconnect
refresh, write-failure recovery, and shutdown. They reuse existing captured
status bytes as a simulated initialization response, without claiming a
new hardware capture of lowercase `k1p0`.

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
not show an expected response. The later `W0` capture above supplies
`Wake-Up : DP-ALL`, with all displays observed cycling off and on. The
integration calls this control **Reset displays**; the original dashboard
label is not evidence of a factory reset or a KVM settings reset.

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
strings. The later debug captures establish CRLF response terminators for
the supplied status, targeted-channel, display, buzzer, hotkey, mouse,
routing, and scan exchanges. The UART capture also includes split CR/LF
terminators and extra CRs; framing for other commands and hardware
configurations remains unverified.

For select helpers, the automation calls `input_select.select_option` with
the exact option shown below. For boolean helpers, it calls
`input_boolean.turn_on` or `input_boolean.turn_off` as indicated. These
helpers belong to the original hand-rolled setup. The integration exposes
native channel, hotkey, and auto-scan selectors, buzzer and mouse
channel-switching switches, and sensors for audio/hub/video routing instead
of writing these helpers. Additional buttons request the tested Sync actions.
The earlier read-only hotkey, buzzer, and mouse entities are removed during
prerelease development; each control also reports its observed state.

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
before/after device state. The targeted channel capture separately adds
physical before/after observations for `K1P1` and `K2P1`. The next
`K1P1` / `K1P0` capture adds a report whose channel matches the first
KVM's selected channel, followed by physical-button feedback. The possible
side effects of `K1P0`, general acknowledgment rules, and the origin of
each reply within a daisy chain remain unknown.

## Current integration behavior

The integration owns the port for both reading and writing. It applies the
serial settings on connection, reconnects after connection failures, and
parses the confirmed feedback into native entities. It does not assume
that a successful write means the requested state has taken effect.
Values remain unknown until feedback arrives after connection. The
manual `K1P0` reports update the recognized state categories; the tested
channel value is consistent with the first/local KVM. The integration now
sends lowercase `k1p0` once after initialization on each runtime connection,
including reconnects, using the user's confirmation above. Status lines
populate entities through the same parser as unsolicited feedback.
Downstream status retrieval remains unconfirmed, and there is no periodic
status polling.

The channel select sends `Ch1` through `Ch4`, and the Reset displays button
sends `W0`. The button retains its existing `reset` entity key and unique
ID; changing its display name does not create a replacement entity. Its
`Wake-Up : DP-ALL` reply is debug logged without fabricating state.

The Buzzer switch sends `BZON` or `BZOFF`; the Mouse channel switching
switch sends `M1` or `M0`. The Hotkey selector sends `ctrl`, `shift`,
`scroll`, or `caps` for `Ctrl`, `Shift`, `Scroll Lock`, or `Caps Lock`.
Each control sends every valid request, including requests matching the
last observed state. Their states remain unknown until feedback arrives
and change only from recognized feedback. They do not track separate
state for linked KVMs. Converted settings have no compatibility sensors;
the binary sensor platform and the earlier hotkey sensor are removed.

Routing feedback now recognizes Hub 1 fixed to `Channel 2`, Video 1 fixed
to `Channel 2`, and individual/global video Sync. Audio and hub routing
sensors remain, and a Video 1 routing sensor is added. The three routing
buttons send exact tested lowercase commands: `h0p0` restores both USB
hubs to Sync, `v1p0` restores Video 1, and `v0p0` restores all video
outputs. Only recognized replies update routing state. No button sends
the rejected `h1p0`, and the global video Sync reply updates only the
confirmed Video 1 state rather than creating untested video entities.

Audio also recognizes the tested `Channel 1` reply. **Sync audio** sends
`o0`, alongside the audio routing sensor; fixed `o1` routing remains
available through the manual command action. This stateless button does
not replace a stateful setting, so the sensor remains the current-state
entity rather than a compatibility copy.

The Auto scan selector sends `s0` through `s5` for Off or one of the five
reported durations. Every duration selection starts scanning. Only
explicit scan and interval replies establish its state; channel changes
do not establish that scanning stopped. UART board-selection replies,
version text, `Ready-0`, and command errors remain diagnostics through
normal debug logging. The integration does not create UART controls or
automatically select a board.

Every valid channel selection sends a command, including a selection
that matches the last observed channel. Unlike the old script's guard,
this allows a quick change and change back before the first response
arrives. Additional audio destinations and hub/video combinations remain
unconfirmed. Their payloads stay in the command catalog for further
verification. The `connectpro.send_command` action accepts a ConnectPro
`device_id` and a single printable ASCII command line under `data`, and
appends CRLF. This
provides a way to use known commands while collecting evidence for
additional features.

The targeted channel commands can selectively switch linked units through
the manual action, but their observed replies do not update the Channel
entity. A subsequent manual `K1P0` can supply recognized channel feedback,
as the later capture demonstrates. The current entities describe feedback
on one serial connection; they do not track each unit in a chain separately.

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
- The scope of `W0` across displays and linked KVMs in other topologies,
  and whether computers actually redetect displays after the observed
  off/on cycle. Its `Wake-Up : DP-ALL` reply and the display cycle in this
  installation are now recorded; KVM settings changes are not established.
- Any side effects of `K1P0` beyond returning the observed status report.
  The `K1P1` and `K2P1` channel-selection effects are observed in this
  installation, but other ports/levels and lowercase equivalence of those
  selection commands still need confirmation. The user has confirmed
  lowercase `k1p0` for current-state initialization.
- Whether another command can retrieve downstream status, how those
  responses return to the host, and which unit produced the `K2P0` error.
- Isolated before/after verification of buzzer control on each linked KVM
  and other chain topologies. The user heard the buzzer and reported that
  commands appear to affect both units; the reply origin and general
  chain scope remain unconfirmed. Lowercase `bzoff` is untested.
- The mouse gesture used for channel switching and behavior in other
  chain topologies. The user has verified hotkey and mouse settings in
  use on both linked KVMs; the source of each serial reply remains unknown.
- A serial `Ch1` comparison with linked units initially on different
  channels, to establish its synchronized-switching scope separately from
  physical button behavior. Per-unit state feedback and response origins
  are also needed before adding separate entities for linked units.
- Before/after state observations and repeated captures with the chain
  topology identified, or a comparison with an isolated device, to establish
  command effects and the origin of responses. The existing `K1P0` debug
  capture already preserves bytes, timing, and read boundaries for one
  exchange. The targeted channel capture adds physical observations for
  two commands; it does not establish the effects of every listed sender.
- Additional hub/video destination channels and Hub 2/Video 2 fixed
  routing, including their exact replies. Hub 1 and Video 1 routing to
  machine 2, both-hub Sync, and individual/global video Sync are recorded
  above. Whether an independent hub Sync command exists remains open;
  `h1p0` is rejected in this installation.
- Audio destinations beyond the tested Channel 1, video routing in status
  reports, and model indicators for other KVMs and firmware versions to
  identify the scope of the observed behavior. `UDP2_14AP_U3` now identifies
  `UDP2-14AP`. Bare `V1P0` / `V1P1` report tokens do not yet provide
  video state.
- The effect of UART board selection on later commands and its scope
  across the chain. `u0` / `u1` / `u2` replies and `Ready-0` diagnostics
  are recorded, but board labels and reply timing do not establish chain
  addresses or a required initialization/recovery sequence.
- Scan behavior after manual channel selection, actual dwell times for
  the other four intervals, and whether scan settings appear in a status
  report. The user verified scan operation on both linked KVMs; only the
  5-second channel cycle is captured here.
