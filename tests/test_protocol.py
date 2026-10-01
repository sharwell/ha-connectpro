"""Tests of observed messages and serial framing without Home Assistant."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_SOURCE = (
    Path(__file__).resolve().parents[1] / "custom_components/connectpro/protocol.py"
)
_SPEC = importlib.util.spec_from_file_location("connectpro_protocol_test", _SOURCE)
assert _SPEC is not None and _SPEC.loader is not None
protocol = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(protocol)


class ProtocolTests(unittest.TestCase):
    """Exercise the existing automation's supported responses."""

    def test_known_response_mappings(self) -> None:
        responses = {
            "BZON": {"buzzer": True},
            "Buzzer : ON": {"buzzer": True},
            "BZOFF": {"buzzer": False},
            "Buzzer : OFF": {"buzzer": False},
            "Mouse change channel : ON": {"mouse_change_channel": True},
            "Mouse change channel : OFF": {"mouse_change_channel": False},
            "AUDIO : Sync": {"audio": "Sync"},
            "HUB1 : Sync": {"hub1": "Sync"},
            "HUB2 : Sync": {"hub2": "Sync"},
        }
        for index in range(1, 5):
            responses[f"CH{index}"] = {"channel": f"Channel {index}"}
            responses[f"CH-{index}"] = {"channel": f"Channel {index}"}
        for key, option in (
            ("CTRL", "Ctrl"),
            ("SHIFT", "Shift"),
            ("SCROLL", "Scroll Lock"),
            ("CAPS", "Caps Lock"),
        ):
            responses[key] = {"hotkey": option}
            responses[f"Hot KEY : {key}"] = {"hotkey": option}
        for response, expected in responses.items():
            with self.subTest(response=response):
                self.assertEqual(protocol.parse_response(response), expected)

    def test_unknown_and_firmware_do_not_set_state(self) -> None:
        for line in ("ch1", " CH1", "CH1 ", "CH5", "AUDIO : 2", "\ufffd", ""):
            with self.subTest(line=line):
                self.assertEqual(protocol.parse_response(line), {})
        for index in range(8):
            line = f"K50_{index} FW Ver B1.42"
            self.assertIn(line, protocol.IGNORED_RESPONSES)
            self.assertEqual(protocol.parse_response(line), {})
        self.assertNotIn("K50_0 FW Ver B1.43", protocol.IGNORED_RESPONSES)

    def test_commands_have_one_crlf_and_reject_control_characters(self) -> None:
        self.assertEqual(protocol.encode_command("Ch2"), b"Ch2\r\n")
        self.assertEqual(protocol.encode_command("V1P0"), b"V1P0\r\n")
        for command in (
            "",
            " ",
            "Ch2\r\n",
            "Ch1\nW0",
            "Ch1\r",
            "\x00",
            "\t",
            "\x7f",
            "caf\u00e9",
            None,
        ):
            with self.subTest(command=command), self.assertRaises(ValueError):
                protocol.encode_command(command)

    def test_fragmented_and_multiple_lines(self) -> None:
        buffer = protocol.LineBuffer()
        self.assertEqual(buffer.feed(b"CH"), [])
        self.assertEqual(buffer.feed(b"-2\r"), [b"CH-2"])
        self.assertEqual(buffer.feed(b"\nBZON\n\r\nCTRL\rHUB"), [b"BZON", b"CTRL"])
        self.assertEqual(buffer.feed(b"1 : Sync\n"), [b"HUB1 : Sync"])
        self.assertEqual(buffer.feed(b"\xff\n"), [b"\xff"])

    def test_overlong_line_is_discarded_through_terminator(self) -> None:
        buffer = protocol.LineBuffer(max_length=4)
        self.assertEqual(buffer.feed(b"1234"), [])
        self.assertEqual(buffer.feed(b"5CH1" * 1000), [])
        self.assertEqual(buffer.discarded_lines, 1)
        self.assertEqual(buffer.feed(b"CH1\nCH2\r\n"), [b"CH2"])
        self.assertEqual(buffer.feed(b"BZON\n"), [b"BZON"])


if __name__ == "__main__":
    unittest.main()
