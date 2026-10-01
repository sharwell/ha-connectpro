"""Serial lifecycle tests using asyncio streams, without Home Assistant."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
import unittest
from contextlib import suppress
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Load only the transport modules, without running the HA integration package.
_PACKAGE = "connectpro_transport_test"
_SOURCE = Path(__file__).resolve().parents[1] / "custom_components/connectpro"
_namespace = types.ModuleType(_PACKAGE)
_namespace.__path__ = [str(_SOURCE)]
sys.modules.setdefault(_PACKAGE, _namespace)
client_module = importlib.import_module(f"{_PACKAGE}.client")
ConnectProClient = client_module.ConnectProClient
SerialSettings = client_module.SerialSettings


def simulated_initialization_report() -> tuple[list[bytes], dict[str, str | bool]]:
    """Reuse an uppercase K1P0 capture as simulated initialization feedback.

    This does not represent a new captured lowercase k1p0 exchange.
    """
    capture = json.loads(
        (Path(__file__).parent / "fixtures" / "k1p0_debug_capture.json").read_text(
            encoding="utf-8"
        )
    )
    return [event["ascii"].encode("ascii") for event in capture["rx"]], {
        "channel": "Channel 2",
        "hotkey": "Ctrl",
        "buzzer": False,
        "hub1": "Sync",
        "hub2": "Sync",
        "audio": "Sync",
        "mouse_change_channel": False,
    }


class FakeWriter:
    """A stream writer whose drain and connection loss can be controlled."""

    def __init__(self, reader: asyncio.StreamReader) -> None:
        self.reader = reader
        self.writes: list[bytes] = []
        self.closed = False
        self.close_count = 0
        self.drain_started = asyncio.Event()
        self.drain_gate: asyncio.Event | None = None
        self.drain_error: Exception | None = None

    def write(self, data: bytes) -> None:
        if self.closed:
            raise ConnectionError("writer closed")
        self.writes.append(data)

    async def drain(self) -> None:
        self.drain_started.set()
        if self.drain_gate is not None:
            await self.drain_gate.wait()
        if self.drain_error is not None:
            raise self.drain_error

    def close(self) -> None:
        self.closed = True
        self.close_count += 1
        self.reader.feed_eof()

    async def wait_closed(self) -> None:
        return


class ClientTests(unittest.IsolatedAsyncioTestCase):
    """Test complete connect/read/write/reconnect/close behavior."""

    async def asyncSetUp(self) -> None:
        self.reader = asyncio.StreamReader()
        self.writer = FakeWriter(self.reader)
        self.client = ConnectProClient(SerialSettings("/dev/test-kvm"))
        self.opener_patch = patch.object(
            client_module, "open_serial_connection", new_callable=AsyncMock
        )
        self.opener = self.opener_patch.start()
        self.opener.return_value = self.reader, self.writer
        self.tasks: list[asyncio.Task] = []

    async def asyncTearDown(self) -> None:
        for task in self.tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await self.client.async_close()
        self.opener_patch.stop()

    def start_reader(self, *, initialize_state: bool = False) -> asyncio.Task:
        task = asyncio.create_task(
            self.client.async_run(initialize_state=initialize_state)
        )
        self.tasks.append(task)
        return task

    async def test_settings_and_temporary_connection_cleanup(self) -> None:
        changes = []
        remove = self.client.add_listener(lambda: changes.append(self.client.connected))
        await self.client.async_connect()
        await self.client.async_connect()
        self.opener.assert_awaited_once_with(
            url="/dev/test-kvm",
            baudrate=115200,
            byte_size=8,
            parity=client_module.Parity.NONE,
            stopbits=client_module.StopBits.ONE,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        self.assertTrue(self.client.connected)
        self.assertEqual(self.writer.writes, [])
        self.assertEqual(changes, [True])
        remove()
        remove()
        await self.client.async_close()
        await self.client.async_close()
        self.assertFalse(self.client.connected)
        self.assertEqual(self.writer.close_count, 1)
        self.assertEqual(self.writer.writes, [])
        self.assertEqual(changes, [True])
        with self.assertRaises(ConnectionError):
            await self.client.async_connect()

    async def test_initialization_queries_once_and_receives_all_observed_states(
        self,
    ) -> None:
        """Opting in sends one lowercase query and awaits ordinary parsed feedback."""
        chunks, expected = simulated_initialization_report()
        await self.client.async_connect()
        self.assertEqual(self.writer.writes, [])
        with self.assertLogs(client_module._LOGGER, level="DEBUG") as captured:
            task = self.start_reader(initialize_state=True)
            await asyncio.wait_for(self.writer.drain_started.wait(), 1)
            self.assertEqual(self.writer.writes, [b"k1p0\r\n"])
            self.assertEqual(self.client.state, {})
            for chunk in chunks:
                self.reader.feed_data(chunk)
                await asyncio.sleep(0)
                self.assertEqual(self.writer.writes, [b"k1p0\r\n"])

        self.assertEqual(self.client.state, expected)
        self.assertTrue(self.client.connected)
        self.assertFalse(task.done())
        self.opener.assert_awaited_once()
        messages = [record.getMessage() for record in captured.records]
        self.assertEqual(messages.count("TX /dev/test-kvm: b'k1p0\\r\\n'"), 1)
        self.assertEqual(
            [
                message
                for message in messages
                if message.startswith("RX /dev/test-kvm: ")
            ],
            [f"RX /dev/test-kvm: {chunk!r}" for chunk in chunks],
        )

    async def test_reconnect_reinitializes_once_with_fresh_observed_state(self) -> None:
        """Each replacement connection gets one query after stale state is cleared."""
        chunks, expected = simulated_initialization_report()
        await self.client.async_connect()
        next_reader = asyncio.StreamReader()
        next_writer = FakeWriter(next_reader)
        self.opener.return_value = next_reader, next_writer
        backoff_started = asyncio.Event()
        resume = asyncio.Event()
        observed = []
        self.client.add_listener(
            lambda: observed.append((self.client.connected, dict(self.client.state)))
        )

        async def wait_for_reconnect(delay: float) -> None:
            backoff_started.set()
            await resume.wait()

        with (
            patch.object(
                self.client, "_wait_to_reconnect", side_effect=wait_for_reconnect
            ) as wait,
            self.assertLogs(client_module._LOGGER, level="WARNING"),
        ):
            task = self.start_reader(initialize_state=True)
            await asyncio.wait_for(self.writer.drain_started.wait(), 1)
            for chunk in chunks:
                self.reader.feed_data(chunk)
                await asyncio.sleep(0)
            self.assertEqual(self.client.state, expected)
            self.reader.feed_eof()
            await asyncio.wait_for(backoff_started.wait(), 1)
            self.assertFalse(self.client.connected)
            self.assertEqual(self.client.state, {})
            self.assertTrue(self.writer.closed)
            self.assertEqual(next_writer.writes, [])
            resume.set()
            await asyncio.wait_for(next_writer.drain_started.wait(), 1)
            self.assertTrue(self.client.connected)
            self.assertEqual(self.client.state, {})
            self.assertEqual(next_writer.writes, [b"k1p0\r\n"])
            for chunk in chunks:
                next_reader.feed_data(chunk)
                await asyncio.sleep(0)
                self.assertEqual(next_writer.writes, [b"k1p0\r\n"])

        wait.assert_awaited_once_with(client_module.RECONNECT_DELAY)
        self.assertIn((False, {}), observed)
        self.assertIn((True, {}), observed)
        self.assertEqual(self.client.state, expected)
        self.assertEqual(self.writer.writes, [b"k1p0\r\n"])
        self.assertFalse(next_writer.closed)
        self.assertFalse(task.done())
        self.assertEqual(self.opener.await_count, 2)

    async def test_initialization_drain_failure_reconnects_and_retries_query(
        self,
    ) -> None:
        """A failed initial write closes its port before retrying on a fresh connection."""
        chunks, expected = simulated_initialization_report()
        await self.client.async_connect()
        self.writer.drain_error = client_module.SerialException("initial query failed")
        next_reader = asyncio.StreamReader()
        next_writer = FakeWriter(next_reader)
        self.opener.return_value = next_reader, next_writer
        backoff_started = asyncio.Event()
        resume = asyncio.Event()

        async def wait_for_reconnect(delay: float) -> None:
            backoff_started.set()
            await resume.wait()

        with (
            patch.object(
                self.client, "_wait_to_reconnect", side_effect=wait_for_reconnect
            ) as wait,
            self.assertLogs(client_module._LOGGER, level="WARNING"),
        ):
            task = self.start_reader(initialize_state=True)
            await asyncio.wait_for(backoff_started.wait(), 1)
            self.assertTrue(self.writer.closed)
            self.assertFalse(self.client.connected)
            self.assertEqual(self.client.state, {})
            self.assertEqual(self.writer.writes, [b"k1p0\r\n"])
            self.assertEqual(next_writer.writes, [])
            self.opener.assert_awaited_once()
            resume.set()
            await asyncio.wait_for(next_writer.drain_started.wait(), 1)
            self.assertEqual(next_writer.writes, [b"k1p0\r\n"])
            self.assertEqual(self.client.state, {})
            for chunk in chunks:
                next_reader.feed_data(chunk)
                await asyncio.sleep(0)

        wait.assert_awaited_once_with(client_module.RECONNECT_DELAY)
        self.assertEqual(self.client.state, expected)
        self.assertTrue(self.client.connected)
        self.assertFalse(next_writer.closed)
        self.assertFalse(task.done())
        self.assertEqual(next_writer.writes, [b"k1p0\r\n"])
        self.assertEqual(self.opener.await_count, 2)

    async def test_cancel_during_initialization_drain_closes_port(self) -> None:
        """Unloading during a blocked initial query cannot leak the serial port."""
        await self.client.async_connect()
        self.writer.drain_gate = asyncio.Event()
        task = self.start_reader(initialize_state=True)
        await asyncio.wait_for(self.writer.drain_started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        self.assertTrue(self.writer.closed)
        self.assertFalse(self.client.connected)
        self.assertEqual(self.client.state, {})
        self.assertEqual(self.writer.writes, [b"k1p0\r\n"])
        self.opener.assert_awaited_once()

    async def test_close_during_initialization_drain_does_not_reopen_or_query(
        self,
    ) -> None:
        """Closing a pending initial query does not send another query afterward."""
        await self.client.async_connect()
        self.writer.drain_gate = asyncio.Event()
        task = self.start_reader(initialize_state=True)
        await asyncio.wait_for(self.writer.drain_started.wait(), 1)
        await self.client.async_close()
        self.writer.drain_gate.set()
        await asyncio.wait_for(task, 1)
        self.assertTrue(self.writer.closed)
        self.assertFalse(self.client.connected)
        self.assertEqual(self.client.state, {})
        self.assertEqual(self.writer.writes, [b"k1p0\r\n"])
        self.opener.assert_awaited_once()

    async def test_fragmented_input_unknown_bytes_and_raw_logging(self) -> None:
        await self.client.async_connect()
        complete = asyncio.Event()
        self.client.add_listener(
            lambda: (
                complete.set() if self.client.state.get("hotkey") == "Ctrl" else None
            )
        )
        with self.assertLogs(client_module._LOGGER, level="DEBUG") as captured:
            self.start_reader()
            self.reader.feed_data(b"CH")
            await asyncio.sleep(0)
            self.reader.feed_data(b"-2\r\nBZOFF\n\xffunknown\nK50_0 FW Ver B1.42\n")
            self.reader.feed_data(b"AUDIO : Sync\nHot KEY : CTRL\n")
            await asyncio.wait_for(complete.wait(), 1)
        self.assertEqual(
            self.client.state,
            {
                "channel": "Channel 2",
                "buzzer": False,
                "audio": "Sync",
                "hotkey": "Ctrl",
            },
        )
        logs = "\n".join(captured.output)
        self.assertIn("RX /dev/test-kvm: b'CH'", logs)
        self.assertIn("\\r\\n", logs)
        self.assertIn("\\xffunknown", logs)
        self.assertIn("unrecognized line", logs)
        self.assertIn("ignored line", logs)

    async def test_complete_k1p0_report_preserves_state_and_unknown_lines(self) -> None:
        """A fragmented status report updates all settings without sending commands."""
        report = (
            (Path(__file__).parent / "fixtures" / "k1p0_report.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        self.assertEqual(len(report), 19)
        # This is an email transcription, not a raw serial capture. LF is
        # chosen for this test and does not establish the device's framing.
        payload = ("\n".join(report) + "\n").encode("ascii")
        await self.client.async_connect()

        with self.assertLogs(client_module._LOGGER, level="DEBUG") as captured:
            task = self.start_reader()
            for offset in range(0, len(payload), 17):
                self.reader.feed_data(payload[offset : offset + 17])
                # Let the reader process each fragment, including the final
                # firmware lines after the seven state-bearing messages.
                await asyncio.sleep(0)

        self.assertEqual(
            self.client.state,
            {
                "channel": "Channel 1",
                "hotkey": "Ctrl",
                "buzzer": True,
                "hub1": "Sync",
                "hub2": "Sync",
                "audio": "Sync",
                "mouse_change_channel": False,
            },
        )
        self.assertTrue(self.client.connected)
        self.assertFalse(task.done())
        self.assertEqual(self.writer.writes, [])
        self.opener.assert_awaited_once()

        logs = "\n".join(captured.output)
        self.assertIn(f"RX /dev/test-kvm: {payload[:17]!r}", logs)
        for line in (*report[:2], "V1P0", "V1P1"):
            self.assertIn(f"unrecognized line: {line!r}", logs)
        for index in range(8):
            self.assertIn(f"ignored line: 'K50_{index} FW Ver B1.42'", logs)

    async def test_k1p0_debug_capture_preserves_exact_read_boundaries(self) -> None:
        """Replay the captured exchange, retaining padding, CRLFs, and read chunks."""
        capture = json.loads(
            (Path(__file__).parent / "fixtures" / "k1p0_debug_capture.json").read_text(
                encoding="utf-8"
            )
        )
        tx = capture["tx"]["ascii"].encode("ascii")
        chunks = [item["ascii"].encode("ascii") for item in capture["rx"]]
        self.assertEqual(tx, b"K1P0\r\n")
        self.assertEqual(len(chunks), 8)
        self.assertEqual(b"".join(chunks).count(b"\r\n"), 19)
        expected_lines = [
            "UDP2_14AP_U3 : Version_Number - 0009 - D1223",
            "UDP2_14AP_DP : Version_Number - 0009 - D1223",
            "CH-2",
            "Hot KEY : CTRL",
            "Buzzer : OFF",
            "HUB1 : Sync",
            "HUB2 : Sync",
            "AUDIO : Sync",
            "Mouse change channel : OFF",
            "V1P0",
            "V1P1",
            *[f"K50_{index} FW Ver B1.42" for index in range(8)],
        ]
        raw_lines = b"".join(chunks).split(b"\r\n")
        self.assertEqual(raw_lines[-1], b"")
        self.assertEqual(
            [line for line in raw_lines if line.endswith(b" ")],
            [
                line.encode("ascii") + b" "
                for line in (*expected_lines[:2], *expected_lines[11:])
            ],
        )
        await self.client.async_connect()

        with (
            self.assertLogs(client_module._LOGGER, level="DEBUG") as captured,
            patch.object(
                client_module, "parse_response", wraps=client_module.parse_response
            ) as parse,
        ):
            task = self.start_reader()
            self.assertEqual(self.writer.writes, [])
            await self.client.async_send_command("K1P0")
            self.assertEqual(self.writer.writes, [tx])
            for chunk in chunks:
                self.reader.feed_data(chunk)
                # Preserve the captured boundaries rather than coalescing
                # queued data into a single StreamReader.read() result.
                await asyncio.sleep(0)

        self.assertEqual(
            [call.args[0] for call in parse.call_args_list], expected_lines
        )
        self.assertEqual(
            self.client.state,
            {
                "channel": "Channel 2",
                "hotkey": "Ctrl",
                "buzzer": False,
                "hub1": "Sync",
                "hub2": "Sync",
                "audio": "Sync",
                "mouse_change_channel": False,
            },
        )
        self.assertTrue(self.client.connected)
        self.assertFalse(task.done())
        self.assertEqual(self.writer.writes, [tx])
        self.opener.assert_awaited_once()

        messages = [record.getMessage() for record in captured.records]
        self.assertIn(f"TX /dev/test-kvm: {tx!r}", messages)
        self.assertEqual(
            [
                message
                for message in messages
                if message.startswith("RX /dev/test-kvm: ")
            ],
            [f"RX /dev/test-kvm: {chunk!r}" for chunk in chunks],
        )
        for line in (*expected_lines[:2], "V1P0", "V1P1"):
            self.assertIn(f"RX /dev/test-kvm unrecognized line: {line!r}", messages)
        for index in range(8):
            self.assertIn(
                f"RX /dev/test-kvm ignored line: 'K50_{index} FW Ver B1.42'",
                messages,
            )

    async def test_targeted_channel_capture_does_not_infer_state_from_replies(
        self,
    ) -> None:
        """Unknown replies cannot substitute for an observed CH2 state message."""
        capture = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "targeted_channel_debug_capture.json"
            ).read_text(encoding="utf-8")
        )
        events = [
            (event["direction"], event["ascii"].encode("ascii"))
            for event in capture["events"]
        ]
        self.assertEqual(
            events,
            [
                ("TX", b"K1P1\r\n"),
                ("RX", b"OK\r\n"),
                ("RX", b"CH2\r\n"),
                ("TX", b"K2P1\r\n"),
                ("RX", b"K1P1\r\n"),
                ("RX", b"CH2"),
                ("RX", b"\r\n"),
            ],
        )
        await self.client.async_connect()
        observed = []
        self.client.add_listener(lambda: observed.append(dict(self.client.state)))
        expected_parse_counts = [0, 1, 2, 2, 3, 3, 4]
        expected_writes = []

        with (
            self.assertLogs(client_module._LOGGER, level="DEBUG") as captured,
            patch.object(
                client_module, "parse_response", wraps=client_module.parse_response
            ) as parse,
        ):
            task = self.start_reader()
            for index, (direction, payload) in enumerate(events):
                if direction == "TX":
                    await self.client.async_send_command(
                        payload.removesuffix(b"\r\n").decode("ascii")
                    )
                    expected_writes.append(payload)
                else:
                    self.reader.feed_data(payload)
                # Yield to the reader without replaying elapsed wall time.
                await asyncio.sleep(0)
                self.assertEqual(self.writer.writes, expected_writes)
                self.assertEqual(parse.call_count, expected_parse_counts[index])
                self.assertEqual(
                    self.client.state, {} if index < 2 else {"channel": "Channel 2"}
                )

        self.assertEqual(
            [call.args[0] for call in parse.call_args_list],
            ["OK", "CH2", "K1P1", "CH2"],
        )
        self.assertEqual(observed, [{"channel": "Channel 2"}])
        self.assertTrue(self.client.connected)
        self.assertFalse(task.done())
        self.assertEqual(self.writer.writes, [b"K1P1\r\n", b"K2P1\r\n"])
        self.opener.assert_awaited_once()

        messages = [record.getMessage() for record in captured.records]
        self.assertEqual(
            [
                message
                for message in messages
                if message.startswith(("TX /dev/test-kvm: ", "RX /dev/test-kvm: "))
            ],
            [
                f"{direction} /dev/test-kvm: {payload!r}"
                for direction, payload in events
            ],
        )
        for line in ("OK", "K1P1"):
            self.assertIn(f"RX /dev/test-kvm unrecognized line: {line!r}", messages)

    async def test_k2p0_error_capture_preserves_observed_state(self) -> None:
        """A rejected manual query leaves known state and the connection intact."""
        capture = json.loads(
            (
                Path(__file__).parent / "fixtures" / "k2p0_error_debug_capture.json"
            ).read_text(encoding="utf-8")
        )
        events = [
            (event["direction"], event["ascii"].encode("ascii"))
            for event in capture["events"]
        ]
        self.assertEqual(events, [("TX", b"K2P0\r\n"), ("RX", b"ERROR\r\n")])
        await self.client.async_connect()
        task = self.start_reader()
        # Establish known state from supported responses before the capture.
        # These setup bytes are synthetic, not part of the user's log.
        self.reader.feed_data(b"CH-2\r\nBZOFF\r\n")
        await asyncio.sleep(0)
        baseline = {"channel": "Channel 2", "buzzer": False}
        self.assertEqual(self.client.state, baseline)
        observed = []
        self.client.add_listener(lambda: observed.append(dict(self.client.state)))

        with (
            self.assertLogs(client_module._LOGGER, level="DEBUG") as captured,
            patch.object(
                client_module, "parse_response", wraps=client_module.parse_response
            ) as parse,
        ):
            for direction, payload in events:
                if direction == "TX":
                    await self.client.async_send_command(
                        payload.removesuffix(b"\r\n").decode("ascii")
                    )
                else:
                    self.reader.feed_data(payload)
                await asyncio.sleep(0)
                self.assertEqual(self.client.state, baseline)
                self.assertTrue(self.client.connected)

        self.assertEqual([call.args[0] for call in parse.call_args_list], ["ERROR"])
        self.assertEqual(observed, [])
        self.assertFalse(task.done())
        self.assertEqual(self.writer.writes, [b"K2P0\r\n"])
        self.opener.assert_awaited_once()
        self.assertTrue(all(record.levelname == "DEBUG" for record in captured.records))
        messages = [record.getMessage() for record in captured.records]
        self.assertEqual(
            messages,
            [
                "TX /dev/test-kvm: b'K2P0\\r\\n'",
                "RX /dev/test-kvm: b'ERROR\\r\\n'",
                "RX /dev/test-kvm unrecognized line: 'ERROR'",
            ],
        )

    async def test_status_after_targeted_switch_updates_only_observed_state(
        self,
    ) -> None:
        """A status report confirms channel 1 before a physical CH2 update."""
        capture = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "local_status_after_targeted_switch.json"
            ).read_text(encoding="utf-8")
        )
        events = [
            (event["direction"], event["ascii"].encode("ascii"))
            for event in capture["events"]
        ]
        self.assertEqual(len(events), 21)
        self.assertEqual(
            [payload for direction, payload in events if direction == "TX"],
            [b"K1P1\r\n", b"K1P0\r\n"],
        )
        self.assertEqual(events[1], ("RX", b"OK\r\n"))
        self.assertEqual(events[-1], ("RX", b"CH2\r\n"))
        report_chunks = [payload for direction, payload in events[3:-1]]
        self.assertEqual(len(report_chunks), 17)
        self.assertEqual(b"".join(report_chunks).count(b"\r\n"), 19)
        report_lines = [
            "UDP2_14AP_U3 : Version_Number - 0009 - D1223",
            "UDP2_14AP_DP : Version_Number - 0009 - D1223",
            "CH-1",
            "Hot KEY : CTRL",
            "Buzzer : OFF",
            "HUB1 : Sync",
            "HUB2 : Sync",
            "AUDIO : Sync",
            "Mouse change channel : OFF",
            "V1P0",
            "V1P1",
            *[f"K50_{index} FW Ver B1.42" for index in range(8)],
        ]
        report_state = {
            "channel": "Channel 1",
            "hotkey": "Ctrl",
            "buzzer": False,
            "hub1": "Sync",
            "hub2": "Sync",
            "audio": "Sync",
            "mouse_change_channel": False,
        }
        final_state = report_state | {"channel": "Channel 2"}
        await self.client.async_connect()
        observed = []
        self.client.add_listener(lambda: observed.append(dict(self.client.state)))
        expected_writes = []

        with (
            self.assertLogs(client_module._LOGGER, level="DEBUG") as captured,
            patch.object(
                client_module, "parse_response", wraps=client_module.parse_response
            ) as parse,
        ):
            task = self.start_reader()
            for index, (direction, payload) in enumerate(events):
                if direction == "TX":
                    await self.client.async_send_command(
                        payload.removesuffix(b"\r\n").decode("ascii")
                    )
                    expected_writes.append(payload)
                else:
                    self.reader.feed_data(payload)
                # Keep the recorded read boundaries without waiting for the
                # original timestamps or inferring state from user actions.
                await asyncio.sleep(0)
                self.assertEqual(self.writer.writes, expected_writes)
                if index <= 2:
                    self.assertEqual(self.client.state, {})
                    self.assertEqual(observed, [])
                elif index == len(events) - 2:
                    self.assertEqual(self.client.state, report_state)
                elif index == len(events) - 1:
                    self.assertEqual(self.client.state, final_state)

        self.assertEqual(
            [call.args[0] for call in parse.call_args_list],
            ["OK", *report_lines, "CH2"],
        )
        self.assertEqual(len(observed), 8)
        self.assertEqual(observed[0], {"channel": "Channel 1"})
        self.assertEqual(observed[-2:], [report_state, final_state])
        self.assertTrue(self.client.connected)
        self.assertFalse(task.done())
        self.assertEqual(self.writer.writes, [b"K1P1\r\n", b"K1P0\r\n"])
        self.opener.assert_awaited_once()

        messages = [record.getMessage() for record in captured.records]
        self.assertEqual(
            [
                message
                for message in messages
                if message.startswith(("TX /dev/test-kvm: ", "RX /dev/test-kvm: "))
            ],
            [
                f"{direction} /dev/test-kvm: {payload!r}"
                for direction, payload in events
            ],
        )
        for line in ("OK", *report_lines[:2], "V1P0", "V1P1"):
            self.assertIn(f"RX /dev/test-kvm unrecognized line: {line!r}", messages)
        for index in range(8):
            self.assertIn(
                f"RX /dev/test-kvm ignored line: 'K50_{index} FW Ver B1.42'",
                messages,
            )

    async def test_w0_capture_waits_for_complete_lines_without_inventing_state(
        self,
    ) -> None:
        """The unknown W0 reply leaves state unknown until later channel feedback."""
        capture = json.loads(
            (Path(__file__).parent / "fixtures" / "w0_debug_capture.json").read_text(
                encoding="utf-8"
            )
        )
        events = [
            (event["direction"], event["ascii"].encode("ascii"))
            for event in capture["events"]
        ]
        self.assertEqual(
            events,
            [
                ("TX", b"W0\r\n"),
                ("RX", b"W"),
                ("RX", b"ake-Up : DP-"),
                ("RX", b"ALL\r\n"),
                ("RX", b"CH1\r\n"),
                ("RX", b"CH2\r\n"),
            ],
        )
        await self.client.async_connect()
        observed = []
        self.client.add_listener(lambda: observed.append(dict(self.client.state)))
        expected_parse_counts = [0, 0, 0, 1, 2, 3]
        expected_states = [
            {},
            {},
            {},
            {},
            {"channel": "Channel 1"},
            {"channel": "Channel 2"},
        ]
        unknown_message = "RX /dev/test-kvm unrecognized line: 'Wake-Up : DP-ALL'"

        with (
            self.assertLogs(client_module._LOGGER, level="DEBUG") as captured,
            patch.object(
                client_module, "parse_response", wraps=client_module.parse_response
            ) as parse,
        ):
            task = self.start_reader()
            for index, (direction, payload) in enumerate(events):
                if direction == "TX":
                    await self.client.async_send_command(
                        payload.removesuffix(b"\r\n").decode("ascii")
                    )
                else:
                    self.reader.feed_data(payload)
                # Replay read boundaries, not the minutes between timestamps.
                await asyncio.sleep(0)
                self.assertEqual(parse.call_count, expected_parse_counts[index])
                self.assertEqual(self.client.state, expected_states[index])
                self.assertEqual(self.writer.writes, [b"W0\r\n"])
                self.assertEqual(
                    sum(
                        record.getMessage() == unknown_message
                        for record in captured.records
                    ),
                    0 if index < 3 else 1,
                )

        self.assertEqual(
            [call.args[0] for call in parse.call_args_list],
            ["Wake-Up : DP-ALL", "CH1", "CH2"],
        )
        self.assertEqual(observed, [{"channel": "Channel 1"}, {"channel": "Channel 2"}])
        self.assertTrue(self.client.connected)
        self.assertFalse(task.done())
        self.opener.assert_awaited_once()
        messages = [record.getMessage() for record in captured.records]
        self.assertEqual(
            [
                message
                for message in messages
                if message.startswith(("TX /dev/test-kvm: ", "RX /dev/test-kvm: "))
            ],
            [
                f"{direction} /dev/test-kvm: {payload!r}"
                for direction, payload in events
            ],
        )
        self.assertEqual(messages.count(unknown_message), 1)

    async def test_buzzer_capture_waits_for_confirmed_state(self) -> None:
        """Buzzer commands await complete replies and duplicate replies add no update."""
        capture = json.loads(
            (
                Path(__file__).parent / "fixtures" / "buzzer_debug_capture.json"
            ).read_text(encoding="utf-8")
        )
        events = [
            (event["direction"], event["ascii"].encode("ascii"))
            for event in capture["events"]
        ]
        self.assertEqual(
            events,
            [
                ("TX", b"bzon\r\n"),
                ("RX", b"BZON\r\n"),
                ("TX", b"BZON\r\n"),
                ("RX", b"B"),
                ("RX", b"ZON\r\n"),
                ("TX", b"BZOFF\r\n"),
                ("RX", b"BZOFF\r\n"),
            ],
        )
        await self.client.async_connect()
        observed = []
        self.client.add_listener(lambda: observed.append(dict(self.client.state)))
        expected_parse_counts = [0, 1, 1, 1, 2, 2, 3]
        expected_update_counts = [0, 1, 1, 1, 1, 1, 2]
        expected_values = [None, True, True, True, True, True, False]
        expected_writes = []

        with (
            self.assertLogs(client_module._LOGGER, level="DEBUG") as captured,
            patch.object(
                client_module, "parse_response", wraps=client_module.parse_response
            ) as parse,
        ):
            task = self.start_reader()
            for index, (direction, payload) in enumerate(events):
                if direction == "TX":
                    await self.client.async_send_command(
                        payload.removesuffix(b"\r\n").decode("ascii")
                    )
                    expected_writes.append(payload)
                else:
                    self.reader.feed_data(payload)
                # Preserve read boundaries without waiting for recorded times.
                await asyncio.sleep(0)
                self.assertEqual(parse.call_count, expected_parse_counts[index])
                self.assertEqual(len(observed), expected_update_counts[index])
                self.assertEqual(
                    self.client.state,
                    {} if index == 0 else {"buzzer": expected_values[index]},
                )
                self.assertEqual(self.writer.writes, expected_writes)

        self.assertEqual(
            [call.args[0] for call in parse.call_args_list], ["BZON", "BZON", "BZOFF"]
        )
        self.assertEqual(observed, [{"buzzer": True}, {"buzzer": False}])
        self.assertTrue(self.client.connected)
        self.assertFalse(task.done())
        self.assertEqual(self.writer.writes, [b"bzon\r\n", b"BZON\r\n", b"BZOFF\r\n"])
        self.opener.assert_awaited_once()
        self.assertEqual(
            [record.getMessage() for record in captured.records],
            [
                f"{direction} /dev/test-kvm: {payload!r}"
                for direction, payload in events
            ],
        )

    async def test_hotkey_and_mouse_capture_updates_only_after_complete_feedback(
        self,
    ) -> None:
        """Commands and partial replies preserve state until complete feedback arrives."""
        capture = json.loads(
            (
                Path(__file__).parent / "fixtures" / "hotkey_mouse_debug_capture.json"
            ).read_text(encoding="utf-8")
        )
        events = [
            (event["direction"], event["ascii"].encode("ascii"))
            for event in capture["events"]
        ]
        expected_commands = [
            b"shift\r\n",
            b"ctrl\r\n",
            b"scroll\r\n",
            b"ctrl\r\n",
            b"caps\r\n",
            b"ctrl\r\n",
            b"m0\r\n",
            b"M0\r\n",
            b"M1\r\n",
            b"m1\r\n",
        ]
        self.assertEqual(len(events), 33)
        self.assertEqual(sum(direction == "RX" for direction, _ in events), 23)
        self.assertEqual(
            [payload for direction, payload in events if direction == "TX"],
            expected_commands,
        )
        expected_lines = [
            "SHIFT",
            "CTRL",
            "SCROLL",
            "CTRL",
            "CAPS",
            "CTRL",
            "Mouse change channel : OFF",
            "Mouse change channel : OFF",
            "Mouse change channel : ON",
            "Mouse change channel : ON",
        ]
        hotkey_states = [
            {"hotkey": option}
            for option in ("Shift", "Ctrl", "Scroll Lock", "Ctrl", "Caps Lock", "Ctrl")
        ]
        mouse_off = {"hotkey": "Ctrl", "mouse_change_channel": False}
        mouse_on = {"hotkey": "Ctrl", "mouse_change_channel": True}
        states_by_complete_lines = [
            {},
            *hotkey_states,
            mouse_off,
            mouse_off,
            mouse_on,
            mouse_on,
        ]
        update_counts_by_complete_lines = [0, 1, 2, 3, 4, 5, 6, 7, 7, 8, 8]
        await self.client.async_connect()
        observed = []
        self.client.add_listener(lambda: observed.append(dict(self.client.state)))
        expected_writes = []
        received = bytearray()

        with (
            self.assertLogs(client_module._LOGGER, level="DEBUG") as captured,
            patch.object(
                client_module, "parse_response", wraps=client_module.parse_response
            ) as parse,
        ):
            task = self.start_reader()
            for direction, payload in events:
                if direction == "TX":
                    await self.client.async_send_command(
                        payload.removesuffix(b"\r\n").decode("ascii")
                    )
                    expected_writes.append(payload)
                else:
                    self.reader.feed_data(payload)
                    received.extend(payload)
                # Replay each recorded read, without its original elapsed time.
                await asyncio.sleep(0)
                complete_lines = received.count(b"\r\n")
                self.assertEqual(parse.call_count, complete_lines)
                self.assertEqual(
                    [call.args[0] for call in parse.call_args_list],
                    expected_lines[:complete_lines],
                )
                self.assertEqual(
                    self.client.state, states_by_complete_lines[complete_lines]
                )
                self.assertEqual(
                    len(observed), update_counts_by_complete_lines[complete_lines]
                )
                self.assertEqual(self.writer.writes, expected_writes)

        self.assertEqual(parse.call_count, 10)
        self.assertEqual(observed, [*hotkey_states, mouse_off, mouse_on])
        self.assertTrue(self.client.connected)
        self.assertFalse(task.done())
        self.assertEqual(self.writer.writes, expected_commands)
        self.opener.assert_awaited_once()
        self.assertEqual(
            [record.getMessage() for record in captured.records],
            [
                f"{direction} /dev/test-kvm: {payload!r}"
                for direction, payload in events
            ],
        )

    async def test_overlong_input_does_not_create_false_state(self) -> None:
        await self.client.async_connect()
        complete = asyncio.Event()
        self.client.add_listener(
            lambda: complete.set() if self.client.state.get("buzzer") else None
        )
        self.start_reader()
        self.reader.feed_data(b"x" * 5000 + b"CH1\nBZON\n")
        await asyncio.wait_for(complete.wait(), 1)
        self.assertEqual(self.client.state, {"buzzer": True})

    async def test_utf8_outer_trim_preserves_internal_spacing(self) -> None:
        await self.client.async_connect()
        complete = asyncio.Event()
        self.client.add_listener(
            lambda: (
                complete.set() if self.client.state.get("hotkey") == "Ctrl" else None
            )
        )
        with self.assertLogs(client_module._LOGGER, level="DEBUG") as captured:
            self.start_reader()
            self.reader.feed_data(
                "\t CH-2 \t\r\nBuzzer  : ON\ncaf\u00e9\nHot KEY : CTRL \t\n".encode(
                    "utf-8"
                )
            )
            await asyncio.wait_for(complete.wait(), 1)
        self.assertEqual(self.client.state, {"channel": "Channel 2", "hotkey": "Ctrl"})
        logs = "\n".join(captured.output)
        self.assertIn("unrecognized line: 'Buzzer  : ON'", logs)
        self.assertIn("unrecognized line: 'caf\u00e9'", logs)
        self.assertIn("\\t CH-2 \\t\\r\\n", logs)
        self.assertIn("caf\\xc3\\xa9", logs)

    async def test_concurrent_writes_are_serialized_and_logged(self) -> None:
        await self.client.async_connect()
        self.writer.drain_gate = asyncio.Event()
        with self.assertLogs(client_module._LOGGER, level="DEBUG") as captured:
            first = asyncio.create_task(self.client.async_send_command("Ch1"))
            self.tasks.append(first)
            await asyncio.wait_for(self.writer.drain_started.wait(), 1)
            second = asyncio.create_task(self.client.async_send_command("Ch2"))
            self.tasks.append(second)
            await asyncio.sleep(0)
            self.assertEqual(self.writer.writes, [b"Ch1\r\n"])
            self.writer.drain_gate.set()
            await asyncio.gather(first, second)
        self.assertEqual(self.writer.writes, [b"Ch1\r\n", b"Ch2\r\n"])
        self.assertEqual(self.client.state, {})
        self.assertIn("TX /dev/test-kvm: b'Ch1\\r\\n'", "\n".join(captured.output))

    async def test_rejects_invalid_and_disconnected_commands(self) -> None:
        with self.assertRaises(ConnectionError):
            await self.client.async_send_command("Ch1")
        await self.client.async_connect()
        for command in ("", "\t", "Ch1\r\nW0", "\u00e9", "\x00"):
            with self.subTest(command=command), self.assertRaises(ValueError):
                await self.client.async_send_command(command)
        self.assertEqual(self.writer.writes, [])

    async def test_write_failure_invalidates_state_and_closes_port(self) -> None:
        await self.client.async_connect()
        self.client.state["channel"] = "Channel 1"
        self.writer.drain_error = client_module.SerialException("write failed")
        with (
            self.assertLogs(client_module._LOGGER, level="WARNING"),
            self.assertRaises(OSError),
        ):
            await self.client.async_send_command("Ch2")
        self.assertFalse(self.client.connected)
        self.assertEqual(self.client.state, {})
        self.assertTrue(self.writer.closed)

    async def test_retired_reader_cannot_restore_stale_state(self) -> None:
        await self.client.async_connect()
        read_started = asyncio.Event()
        release_read = asyncio.Event()
        reconnected = asyncio.Event()
        next_reader = asyncio.StreamReader()
        next_writer = FakeWriter(next_reader)
        observed = []
        self.client.add_listener(
            lambda: observed.append((self.client.connected, dict(self.client.state)))
        )

        async def delayed_read(size):
            read_started.set()
            await release_read.wait()
            return b"CH1\n"

        with patch.object(self.reader, "read", side_effect=delayed_read):
            self.start_reader()
            await asyncio.wait_for(read_started.wait(), 1)
            self.writer.drain_error = OSError("connection lost during write")
            with (
                self.assertLogs(client_module._LOGGER, level="WARNING"),
                self.assertRaises(OSError),
            ):
                await self.client.async_send_command("Ch2")
            self.opener.return_value = next_reader, next_writer
            self.client.add_listener(
                lambda: reconnected.set() if self.client.connected else None
            )
            release_read.set()
            await asyncio.wait_for(reconnected.wait(), 1)
        self.assertTrue(self.client.connected)
        self.assertEqual(self.client.state, {})
        self.assertTrue(all(state == {} for connected, state in observed))
        self.opener.assert_awaited()
        self.assertEqual(self.opener.await_count, 2)

    async def test_reconnect_backoff_is_bounded_and_state_is_fresh(self) -> None:
        next_reader = asyncio.StreamReader()
        next_writer = FakeWriter(next_reader)
        self.opener.side_effect = [
            (self.reader, self.writer),
            *[OSError("unplugged") for _ in range(6)],
            (next_reader, next_writer),
        ]
        await self.client.async_connect()
        self.client.state.update({"channel": "Channel 1", "buzzer": True})
        observed = []
        complete = asyncio.Event()

        def changed() -> None:
            observed.append((self.client.connected, dict(self.client.state)))
            if self.client.state.get("channel") == "Channel 3":
                complete.set()

        self.client.add_listener(changed)
        self.reader.feed_data(b"CH-")
        self.reader.feed_eof()
        next_reader.feed_data(b"CH-3\n")
        with (
            patch.object(
                self.client, "_wait_to_reconnect", new_callable=AsyncMock
            ) as wait,
            self.assertLogs(client_module._LOGGER, level="WARNING"),
        ):
            self.start_reader()
            await asyncio.wait_for(complete.wait(), 1)
        self.assertEqual(
            [call.args[0] for call in wait.await_args_list], [1, 2, 4, 8, 16, 30, 30]
        )
        self.assertIn((False, {}), observed)
        self.assertIn((True, {}), observed)
        self.assertEqual(self.client.state, {"channel": "Channel 3"})
        self.assertTrue(self.writer.closed)
        self.assertFalse(next_writer.closed)

    async def test_cancellation_closes_connection(self) -> None:
        await self.client.async_connect()
        task = self.start_reader()
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(self.client.connected)
        self.assertTrue(self.writer.closed)
        self.opener.assert_awaited_once()

    async def test_close_wakes_reconnect_delay(self) -> None:
        await self.client.async_connect()
        disconnected = asyncio.Event()
        self.client.add_listener(
            lambda: disconnected.set() if not self.client.connected else None
        )
        self.reader.feed_eof()
        with self.assertLogs(client_module._LOGGER, level="WARNING"):
            task = self.start_reader()
            await asyncio.wait_for(disconnected.wait(), 1)
            await self.client.async_close()
            await asyncio.wait_for(task, 1)
        self.opener.assert_awaited_once()

    async def test_connect_error_and_timeout_leave_client_disconnected(self) -> None:
        self.opener.side_effect = client_module.SerialException("backend failed")
        with self.assertRaises(OSError):
            await self.client.async_connect()
        self.assertFalse(self.client.connected)

        async def never_connect(**kwargs):
            await asyncio.Event().wait()

        self.opener.side_effect = never_connect
        with (
            patch.object(client_module, "CONNECT_TIMEOUT", 0.01),
            self.assertRaises(TimeoutError),
        ):
            await self.client.async_connect()
        self.assertFalse(self.client.connected)

    async def test_close_during_connect_does_not_leak_port(self) -> None:
        entered = asyncio.Event()
        finish = asyncio.Event()

        async def connect(**kwargs):
            entered.set()
            await finish.wait()
            return self.reader, self.writer

        self.opener.side_effect = connect
        connecting = asyncio.create_task(self.client.async_connect())
        await asyncio.wait_for(entered.wait(), 1)
        closing = asyncio.create_task(self.client.async_close())
        await asyncio.sleep(0)
        finish.set()
        with self.assertRaises(ConnectionError):
            await connecting
        await closing
        self.assertTrue(self.writer.closed)
        self.assertFalse(self.client.connected)

    async def test_actual_serialx_socket_transport(self) -> None:
        """Exercise real serialx streams against a local simulated device."""
        from serialx import open_serial_connection

        received = asyncio.get_running_loop().create_future()
        handler_done = asyncio.Event()

        async def device(reader, writer):
            try:
                writer.write(b"CH-")
                await writer.drain()
                await asyncio.sleep(0)
                writer.write(b"4\r\n")
                await writer.drain()
                received.set_result(await reader.readuntil(b"\r\n"))
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
                handler_done.set()

        server = await asyncio.start_server(device, "127.0.0.1", 0)
        self.addAsyncCleanup(server.wait_closed)
        self.addCleanup(server.close)
        port = server.sockets[0].getsockname()[1]
        self.client = ConnectProClient(SerialSettings(f"socket://127.0.0.1:{port}"))
        self.opener.side_effect = open_serial_connection
        complete = asyncio.Event()
        self.client.add_listener(
            lambda: (
                complete.set()
                if self.client.state.get("channel") == "Channel 4"
                else None
            )
        )
        await self.client.async_connect()
        task = self.start_reader()
        await self.client.async_send_command("Ch2")
        self.assertEqual(await asyncio.wait_for(received, 2), b"Ch2\r\n")
        await asyncio.wait_for(complete.wait(), 2)
        self.assertEqual(self.client.state, {"channel": "Channel 4"})
        await self.client.async_close()
        await asyncio.wait_for(task, 2)
        await asyncio.wait_for(handler_done.wait(), 2)


if __name__ == "__main__":
    unittest.main()
