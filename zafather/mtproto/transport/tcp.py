"""UZ: TCP transporti (Abridged yoki Intermediate ramkalash bilan).
RU: TCP-транспорт (с кадрированием Abridged или Intermediate).
EN: TCP transport (with Abridged or Intermediate framing).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from ..errors import TransportError
from .base import AbridgedCodec, FrameCodec, Transport, check_transport_error

OpenConnection = Callable[..., Awaitable[tuple[Any, Any]]]


class TcpTransport(Transport):
    """UZ: Data-markazga oddiy TCP ulanishi.
    RU: Обычное TCP-соединение с дата-центром.
    EN: A plain TCP connection to a data center.

    UZ: `open_connection` testlarda soxta oqimlarni ulash uchun almashtiriladi.
    RU: `open_connection` заменяется в тестах для подключения фейковых потоков.
    EN: `open_connection` is replaced in tests to plug in fake streams.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        codec: FrameCodec | None = None,
        connect_timeout: float = 10.0,
        open_connection: OpenConnection = asyncio.open_connection,
    ) -> None:
        self.host = host
        self.port = port
        self.codec = codec or AbridgedCodec()
        self.connect_timeout = connect_timeout
        self._open_connection = open_connection
        self._reader: Any = None
        self._writer: Any = None

    @property
    def connected(self) -> bool:
        return self._writer is not None

    async def connect(self) -> None:
        if self.connected:
            return
        try:
            self._reader, self._writer = await asyncio.wait_for(
                self._open_connection(self.host, self.port), timeout=self.connect_timeout
            )
            self._writer.write(self.codec.tag)
            await self._writer.drain()
        except (OSError, asyncio.TimeoutError) as exc:
            await self.close()
            raise TransportError(f"Cannot connect to {self.host}:{self.port}: {exc}") from exc

    async def send(self, packet: bytes) -> None:
        if self._writer is None:
            raise TransportError("Transport is not connected")
        try:
            self._writer.write(self.codec.encode(packet))
            await self._writer.drain()
        except OSError as exc:
            raise TransportError(f"Send failed: {exc}") from exc

    async def receive(self) -> bytes:
        if self._reader is None:
            raise TransportError("Transport is not connected")
        try:
            packet = await self.codec.read_frame(self._reader)
        except (asyncio.IncompleteReadError, OSError) as exc:
            raise TransportError("Connection closed by the server") from exc
        check_transport_error(packet)
        return packet

    async def close(self) -> None:
        writer, self._reader, self._writer = self._writer, None, None
        if writer is None:
            return
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()

    def __repr__(self) -> str:
        return f"<TcpTransport {self.host}:{self.port} {type(self.codec).__name__}>"


__all__ = ["OpenConnection", "TcpTransport"]
