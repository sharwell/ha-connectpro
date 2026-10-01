"""Serial lifecycle tests using asyncio streams, without Home Assistant."""

from __future__ import annotations

import asyncio
import importlib
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

    def start_reader(self) -> asyncio.Task:
        task = asyncio.create_task(self.client.async_run())
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
        self.assertEqual(changes, [True])
        remove()
        remove()
        await self.client.async_close()
        await self.client.async_close()
        self.assertFalse(self.client.connected)
        self.assertEqual(self.writer.close_count, 1)
        self.assertEqual(changes, [True])
        with self.assertRaises(ConnectionError):
            await self.client.async_connect()

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
