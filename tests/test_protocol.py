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
    """Exercise confirmed responses from the automation and device captures."""

    def test_known_response_mappings(self) -> None:
        responses = {
            "BZON": {"buzzer": True},
            "Buzzer : ON": {"buzzer": True},
            "BZOFF": {"buzzer": False},
            "Buzzer : OFF": {"buzzer": False},
            "Mouse change channel : ON": {"mouse_change_channel": True},
            "Mouse change channel : OFF": {"mouse_change_channel": False},
            "AUDIO : Sync": {"audio": "Sync"},
            "AUDIO : CHANNEL1": {"audio": "Channel 1"},
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

    def test_confirmed_usb_board_identifier_sets_model_independent_of_version(
        self,
    ) -> None:
        """The identifier names the retail model, without exposing firmware state."""
        for suffix in ("0009 - D1223", "0010 - D0101", "2.0"):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    protocol.parse_response(
                        f"UDP2_14AP_U3 : Version_Number - {suffix}"
                    ),
                    {"model": "UDP2-14AP"},
                )

    def test_incomplete_and_other_model_identifiers_remain_unknown(self) -> None:
        """Do not infer model from DP boards, substrings, or malformed reports."""
        for line in (
            "UDP2_14AP_DP : Version_Number - 0009 - D1223",
            "UDP2_12AP_U3 : Version_Number - 0009 - D1223",
            "UDP2_14AP_U30 : Version_Number - 0009 - D1223",
            "UDP2_14AP_U3_extra : Version_Number - 0009 - D1223",
            "OTHER_UDP2_14AP_U3 : Version_Number - 0009 - D1223",
            "udp2_14ap_u3 : Version_Number - 0009 - D1223",
            "UDP2_14AP_U3 : version_number - 0009 - D1223",
            "UDP2_14AP_U3: Version_Number - 0009 - D1223",
            "UDP2_14AP_U3 : Version_Number -0009 - D1223",
            "UDP2_14AP_U3",
            "UDP2_14AP_U3 : Version_Number",
            "UDP2_14AP_U3 : Version_Number -",
            "UDP2_14AP_U3 : Version_Number - ",
            "UDP2_14AP_U3 : Version_Number -   ",
            "",
        ):
            with self.subTest(line=line):
                self.assertEqual(protocol.parse_response(line), {})

    def test_scan_feedback_keeps_enabled_and_interval_fields_separate(self) -> None:
        """Timing feedback does not enable scanning or alter the selected channel."""
        responses = {
            "Auto Scan : ON": {"auto_scan": True},
            "Auto Scan : OFF": {"auto_scan": False},
            "Auto Scan : 1(5sec)": {"auto_scan_interval": "5 seconds"},
            "Auto Scan : 2(8Sec)": {"auto_scan_interval": "8 seconds"},
            "Auto Scan : 3(15Sec)": {"auto_scan_interval": "15 seconds"},
            "Auto Scan : 4(20Sec)": {"auto_scan_interval": "20 seconds"},
            "Auto Scan : 5(30Sec)": {"auto_scan_interval": "30 seconds"},
        }
        for response, expected in responses.items():
            with self.subTest(response=response):
                self.assertEqual(protocol.parse_response(response), expected)

    def test_unknown_scan_variants_and_uart_messages_do_not_set_state(self) -> None:
        """Unobserved timing forms and UART diagnostics remain unrecognized."""
        responses = (
            "AUDIO : Channel1",
            "Auto Scan : On",
            "Auto Scan : Off",
            "Auto Scan : 1(5Sec)",
            "Auto Scan : 2(8sec)",
            "Auto Scan : 1(8Sec)",
            "Auto Scan : 6(60Sec)",
            "UART to DP1-Board",
            "UART to DP2-Board",
            "UART connect to USB-Board",
            "Ready-0",
            "ERROR",
        )
        for response in responses:
            with self.subTest(response=response):
                self.assertEqual(protocol.parse_response(response), {})
                self.assertNotIn(response, protocol.IGNORED_RESPONSES)

    def test_routing_patterns_cover_each_requested_endpoint_and_channel(self) -> None:
        """Expand confirmed forms to the user-requested sibling ports and channels."""
        responses = {"AUDIO : Sync": {"audio": "Sync"}}
        for channel in range(1, 5):
            responses[f"AUDIO : CHANNEL{channel}"] = {"audio": f"Channel {channel}"}
            for endpoint in (1, 2):
                responses[f"HUB{endpoint} : Async-> Channel {channel}"] = {
                    f"hub{endpoint}": f"Channel {channel}"
                }
                responses[f"Video{endpoint} : ASYNC-mode-Port{channel}"] = {
                    f"video{endpoint}": f"Channel {channel}"
                }
        for endpoint in (1, 2):
            responses[f"HUB{endpoint} : Sync"] = {f"hub{endpoint}": "Sync"}
            responses[f"Video{endpoint} : SYNC-mode"] = {f"video{endpoint}": "Sync"}
        for response, expected in responses.items():
            with self.subTest(response=response):
                self.assertEqual(protocol.parse_response(response), expected)

    def test_video_all_sync_returns_both_outputs_in_one_update(self) -> None:
        self.assertEqual(
            protocol.parse_response("Video-ALL : SYNC-mode"),
            {"video1": "Sync", "video2": "Sync"},
        )

    def test_invalid_routing_variants_do_not_set_state(self) -> None:
        """Keep the sanctioned forms bounded and case/spacing sensitive."""
        responses = [
            "HUB1 : ASYNC-> Channel 2",
            "HUB1 : Async-> Channel2",
            "HUB1 : Async -> Channel 2",
            "HUB1 : Async->  Channel 2",
            "HUB2 : SYNC",
            "AUDIO : CHANNEL 2",
            "AUDIO : Channel2",
            "AUDIO : SYNC",
            "VIDEO1 : SYNC-mode",
            "Video1 : ASYNC-mode-Port 2",
            "Video2 : Async-mode-Port2",
            "Video-ALL : ASYNC-mode-Port2",
            "Video-ALL : Sync-mode",
            "Video-ALL : SYNC-mode ",
            " Video-ALL : SYNC-mode",
            "ERROR",
            "V1P0",
            "V1P1",
        ]
        for channel in ("0", "5", "-1", "01", "1.0"):
            responses.append(f"AUDIO : CHANNEL{channel}")
            for endpoint in (1, 2):
                responses.extend(
                    (
                        f"HUB{endpoint} : Async-> Channel {channel}",
                        f"Video{endpoint} : ASYNC-mode-Port{channel}",
                    )
                )
        for endpoint in ("0", "3", "-1", "01"):
            responses.extend(
                (
                    f"HUB{endpoint} : Sync",
                    f"HUB{endpoint} : Async-> Channel 2",
                    f"Video{endpoint} : SYNC-mode",
                    f"Video{endpoint} : ASYNC-mode-Port2",
                )
            )
        for response in responses:
            with self.subTest(response=response):
                self.assertEqual(protocol.parse_response(response), {})

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
