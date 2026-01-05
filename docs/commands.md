# ConnectPro KVM command reference

This file documents the serial protocol used by ConnectPro KVM devices.
Fill this in with the command formats, responses, and examples from your
existing automations.

## Serial settings

These match the current `stty` configuration used outside the
integration.

- Baudrate: 115200
- Data bits: 8
- Parity: none
- Stop bits: 1

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

Observed responses from the serial sensor include the values below. These
are treated as state updates and can be mapped to entities in the
integration.

### Channel updates

- CH1
- CH-1
- CH2
- CH-2
- CH3
- CH-3
- CH4
- CH-4

### Buzzer state

- BZON
- Buzzer : ON
- BZOFF
- Buzzer : OFF

### Mouse channel switching

- Mouse change channel : ON
- Mouse change channel : OFF

### Audio/HUB mode

- AUDIO : Sync
- HUB1 : Sync
- HUB2 : Sync

### Hotkey mode

- Hot KEY : CTRL
- CTRL
- Hot KEY : SHIFT
- SHIFT
- Hot KEY : SCROLL
- SCROLL
- Hot KEY : CAPS
- CAPS

### Firmware strings (ignored today)

- K50_0 FW Ver B1.42
- K50_1 FW Ver B1.42
- K50_2 FW Ver B1.42
- K50_3 FW Ver B1.42
- K50_4 FW Ver B1.42
- K50_5 FW Ver B1.42
- K50_6 FW Ver B1.42
- K50_7 FW Ver B1.42

## Example exchanges

TBD

## Home Assistant mapping notes

TBD
