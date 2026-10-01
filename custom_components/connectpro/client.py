"""Asynchronous ConnectPro serial transport, independent of Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from serialx import Parity, SerialException, StopBits, open_serial_connection

from .protocol import IGNORED_RESPONSES, LineBuffer, encode_command, parse_response

_LOGGER = logging.getLogger(__name__)
CONNECT_TIMEOUT = 10.0
WRITE_TIMEOUT = 10.0
CLOSE_TIMEOUT = 5.0
RECONNECT_DELAY = 1.0
MAX_RECONNECT_DELAY = 30.0
READ_CHUNK_SIZE = 1024


@dataclass(frozen=True, slots=True)
class SerialSettings:
    """Port settings; hardware and software flow control are disabled."""

    device: str
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1


class ConnectProClient:
    """Own one serial connection and publish only observed device state.

    The caller owns the task running ``async_run`` and must cancel it during
    unload. ``async_close`` is also safe for a temporary connection check.
    """

    def __init__(self, settings: SerialSettings) -> None:
        """Create a disconnected client without scheduling background work."""
        self.settings = settings
        self.connected = False
        self.state: dict[str, str | bool] = {}
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lines = LineBuffer()
        self._listeners: set[Callable[[], None]] = set()
        self._connection_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._closed = asyncio.Event()
        self._running = False

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to connection/state changes on the current event loop."""
        self._listeners.add(callback)

        def unsubscribe() -> None:
            self._listeners.discard(callback)

        return unsubscribe

    def _notify_listeners(self) -> None:
        for callback in tuple(self._listeners):
            try:
                callback()
            except Exception:
                _LOGGER.exception("State listener failed for %s", self.settings.device)

    async def async_connect(self) -> None:
        """Open and configure the port, clearing state from previous sessions."""
        async with self._connection_lock:
            if self._closed.is_set():
                raise ConnectionError("Serial client is closed")
            if self.connected:
                return
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    reader, writer = await open_serial_connection(
                        url=self.settings.device,
                        baudrate=self.settings.baudrate,
                        byte_size=self.settings.bytesize,
                        parity=Parity(self.settings.parity),
                        stopbits=StopBits(self.settings.stopbits),
                        xonxoff=False,
                        rtscts=False,
                        dsrdtr=False,
                    )
            except SerialException as err:
                raise OSError(str(err)) from err
            if self._closed.is_set():
                await self._close_writer(writer)
                raise ConnectionError("Serial client is closed")
            self._reader = reader
            self._writer = writer
            self._lines = LineBuffer()
            self.state.clear()
            self.connected = True
            _LOGGER.info("Connected to serial device %s", self.settings.device)
            self._notify_listeners()

    async def async_send_command(self, command: str) -> None:
        """Write one command, without guessing or changing device state."""
        payload = encode_command(command)
        async with self._write_lock:
            writer = self._writer
            if not self.connected or writer is None or self._closed.is_set():
                raise ConnectionError("Serial device is not connected")
            _LOGGER.debug("TX %s: %r", self.settings.device, payload)
            try:
                writer.write(payload)
                async with asyncio.timeout(WRITE_TIMEOUT):
                    await writer.drain()
            except (OSError, SerialException) as err:
                _LOGGER.warning(
                    "Serial write failed for %s: %s", self.settings.device, err
                )
                await self._disconnect(writer)
                if isinstance(err, SerialException):
                    raise OSError(str(err)) from err
                raise

    async def async_run(self, *, initialize_state: bool = False) -> None:
        """Read and reconnect, optionally requesting state once per connection."""
        if self._running:
            raise RuntimeError("Serial read loop is already running")
        self._running = True
        delay = RECONNECT_DELAY
        initialized_writer: asyncio.StreamWriter | None = None
        try:
            while not self._closed.is_set():
                if not self.connected:
                    try:
                        await self.async_connect()
                    except OSError as err:
                        if self._closed.is_set():
                            break
                        _LOGGER.warning(
                            "Cannot connect to %s: %s; retrying in %.1fs",
                            self.settings.device,
                            err,
                            delay,
                        )
                        await self._wait_to_reconnect(delay)
                        delay = min(delay * 2, MAX_RECONNECT_DELAY)
                        continue
                reader, writer = self._reader, self._writer
                if reader is None or writer is None:
                    continue
                try:
                    if initialize_state and writer is not initialized_writer:
                        await self.async_send_command("k1p0")
                        initialized_writer = writer
                    chunk = await reader.read(READ_CHUNK_SIZE)
                    if self._closed.is_set():
                        break
                    # Log every received chunk before normalization, including
                    # any data that arrived while this connection was retired.
                    if chunk:
                        _LOGGER.debug("RX %s: %r", self.settings.device, chunk)
                    if writer is not self._writer or not self.connected:
                        _LOGGER.debug(
                            "RX %s: discarded data from retired connection",
                            self.settings.device,
                        )
                        continue
                    if not chunk:
                        raise ConnectionError("Serial device closed the connection")
                    self._process_chunk(chunk)
                    delay = RECONNECT_DELAY
                except (OSError, SerialException) as err:
                    if self._closed.is_set():
                        break
                    _LOGGER.warning(
                        "Serial read loop failed for %s: %s", self.settings.device, err
                    )
                    await self._disconnect(writer)
                    if not self._closed.is_set():
                        await self._wait_to_reconnect(delay)
                        delay = min(delay * 2, MAX_RECONNECT_DELAY)
        finally:
            await self._disconnect()
            self._running = False

    def _process_chunk(self, chunk: bytes) -> None:
        discarded_before = self._lines.discarded_lines
        for raw_line in self._lines.feed(chunk):
            # Match the stock serial sensor's UTF-8 decoding and outer trim.
            # Interior spacing and case remain significant to the parser.
            line = raw_line.decode("utf-8", errors="replace").strip()
            updates = parse_response(line)
            if not updates:
                kind = "ignored" if line in IGNORED_RESPONSES else "unrecognized"
                _LOGGER.debug("RX %s %s line: %r", self.settings.device, kind, line)
                continue
            if any(self.state.get(key) != value for key, value in updates.items()):
                self.state.update(updates)
                self._notify_listeners()
        if self._lines.discarded_lines > discarded_before:
            _LOGGER.debug("RX %s: discarded overlong line", self.settings.device)

    async def _wait_to_reconnect(self, delay: float) -> None:
        try:
            async with asyncio.timeout(delay):
                await self._closed.wait()
        except TimeoutError:
            pass

    async def _disconnect(
        self, expected_writer: asyncio.StreamWriter | None = None
    ) -> None:
        async with self._connection_lock:
            if expected_writer is not None and self._writer is not expected_writer:
                return
            writer = self._writer
            self._reader = None
            self._writer = None
            changed = self.connected or bool(self.state)
            self.connected = False
            self.state.clear()
            self._lines = LineBuffer()
            if changed:
                self._notify_listeners()
            if writer is not None:
                await self._close_writer(writer)

    async def _close_writer(self, writer: asyncio.StreamWriter) -> None:
        try:
            writer.close()
            async with asyncio.timeout(CLOSE_TIMEOUT):
                await writer.wait_closed()
        except (OSError, SerialException) as err:
            _LOGGER.debug(
                "Error closing serial device %s: %s", self.settings.device, err
            )

    async def async_close(self) -> None:
        """Release the port and wake any reconnect delay; safe to call twice."""
        self._closed.set()
        await self._disconnect()
