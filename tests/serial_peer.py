"""In-memory peer at the serial stream boundary."""

import asyncio


class SerialReader(asyncio.StreamReader):
    """Signal when the client is ready for the next chunk of input."""

    def __init__(self) -> None:
        super().__init__()
        self.reading = asyncio.Event()

    async def read(self, n: int = -1) -> bytes:
        self.reading.set()
        return await super().read(n)

    async def receive(self, data: bytes) -> None:
        """Deliver one read and wait until the client has processed it."""
        await asyncio.wait_for(self.reading.wait(), 2)
        self.reading.clear()
        self.feed_data(data)
        await asyncio.wait_for(self.reading.wait(), 2)


class SerialWriter:
    """Record bytes and simulate drain, disconnect, and close."""

    def __init__(self, reader: SerialReader) -> None:
        self.reader = reader
        self.writes: list[bytes] = []
        self.closed = False
        self.close_count = 0
        self.closed_event = asyncio.Event()
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
        self.closed_event.set()

    async def wait_closed(self) -> None:
        await self.closed_event.wait()
