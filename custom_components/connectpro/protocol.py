"""Known ConnectPro messages and bounded serial line framing."""

from __future__ import annotations

MAX_LINE_LENGTH = 4096

_RESPONSES: dict[str, tuple[str, str | bool]] = {
    "BZON": ("buzzer", True),
    "Buzzer : ON": ("buzzer", True),
    "BZOFF": ("buzzer", False),
    "Buzzer : OFF": ("buzzer", False),
    "Mouse change channel : ON": ("mouse_change_channel", True),
    "Mouse change channel : OFF": ("mouse_change_channel", False),
    "AUDIO : Sync": ("audio", "Sync"),
    "AUDIO : CHANNEL1": ("audio", "Channel 1"),
    "Auto Scan : ON": ("auto_scan", True),
    "Auto Scan : OFF": ("auto_scan", False),
    "Auto Scan : 1(5sec)": ("auto_scan_interval", "5 seconds"),
    "Auto Scan : 2(8Sec)": ("auto_scan_interval", "8 seconds"),
    "Auto Scan : 3(15Sec)": ("auto_scan_interval", "15 seconds"),
    "Auto Scan : 4(20Sec)": ("auto_scan_interval", "20 seconds"),
    "Auto Scan : 5(30Sec)": ("auto_scan_interval", "30 seconds"),
    "HUB1 : Sync": ("hub1", "Sync"),
    "HUB1 : Async-> Channel 2": ("hub1", "Channel 2"),
    "HUB2 : Sync": ("hub2", "Sync"),
    "Video1 : ASYNC-mode-Port2": ("video1", "Channel 2"),
    "Video1 : SYNC-mode": ("video1", "Sync"),
    "Video-ALL : SYNC-mode": ("video1", "Sync"),
}
for _channel in range(1, 5):
    for _message in (f"CH{_channel}", f"CH-{_channel}"):
        _RESPONSES[_message] = ("channel", f"Channel {_channel}")
for _key, _option in (
    ("CTRL", "Ctrl"),
    ("SHIFT", "Shift"),
    ("SCROLL", "Scroll Lock"),
    ("CAPS", "Caps Lock"),
):
    for _message in (_key, f"Hot KEY : {_key}"):
        _RESPONSES[_message] = ("hotkey", _option)

IGNORED_RESPONSES = frozenset(f"K50_{index} FW Ver B1.42" for index in range(8))


def parse_response(line: str) -> dict[str, str | bool]:
    """Return a confirmed state change for an exact known response."""
    if (response := _RESPONSES.get(line)) is None:
        return {}
    key, value = response
    return {key: value}


def encode_command(command: str) -> bytes:
    """Encode one printable ASCII command with exactly one CRLF terminator."""
    if (
        not isinstance(command, str)
        or not command.strip()
        or any(not 0x20 <= ord(character) <= 0x7E for character in command)
    ):
        raise ValueError("Command must contain printable ASCII without line breaks")
    return command.encode("ascii") + b"\r\n"


class LineBuffer:
    """Frame CRLF, LF, or CR lines without retaining unbounded input.

    Overlong lines are discarded through their next terminator, so their
    tail cannot be mistaken for a valid state response.
    """

    def __init__(self, max_length: int = MAX_LINE_LENGTH) -> None:
        """Initialize an empty buffer."""
        if max_length < 1:
            raise ValueError("Line length must be positive")
        self._max_length = max_length
        self._buffer = bytearray()
        self._discarding = False
        self.discarded_lines = 0

    def feed(self, chunk: bytes) -> list[bytes]:
        """Consume bytes and return complete nonempty lines."""
        lines: list[bytes] = []
        for byte in chunk:
            if byte in (10, 13):
                if self._buffer and not self._discarding:
                    lines.append(bytes(self._buffer))
                self._buffer.clear()
                self._discarding = False
            elif not self._discarding:
                if len(self._buffer) == self._max_length:
                    self._buffer.clear()
                    self._discarding = True
                    self.discarded_lines += 1
                else:
                    self._buffer.append(byte)
        return lines
