"""UZ: MTProto transport qatlamlari.
RU: Транспортные слои MTProto.
EN: MTProto transport layers.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional


class MTProtoTransportError(ConnectionError):
    """UZ/RU/EN: MTProto transport xatosi."""


class AbridgedTransport:
    """UZ: MTProto Abridged TCP transporti.
    RU: TCP-транспорт MTProto Abridged.
    EN: MTProto Abridged TCP transport.
    """

    def __init__(
        self,
        host: str = "149.154.167.50",
        port: int = 443,
        timeout: float = 30.0,
        open_connection: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._open_connection = open_connection or asyncio.open_connection
        self._reader: Any = None
        self._writer: Any = None
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return
        result = self._open_connection(self.host, self.port)
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            result = await result
        self._reader, self._writer = result
        try:
            self._writer.write(b"\xef")
            await self._writer.drain()
        except Exception as exc:  # noqa: BLE001
            await self.disconnect()
            raise MTProtoTransportError("MTProto Abridged handshake failed") from exc
        self._connected = True

    async def send(self, payload: bytes) -> None:
        if self._writer is None:
            raise MTProtoTransportError("Transport ulanmagan")
        if not isinstance(payload, bytes):
            raise TypeError("MTProto payload bytes bo'lishi kerak")
        words = (len(payload) + 3) // 4
        if words < 0x7F:
            header = bytes((words,))
        else:
            if words >= 1 << 24:
                raise ValueError("MTProto packet juda katta")
            header = b"\x7f" + words.to_bytes(3, "little")
        self._writer.write(header + payload)
        await self._writer.drain()

    async def receive(self) -> bytes:
        if self._reader is None:
            raise MTProtoTransportError("Transport ulanmagan")
        first = (await self._reader.readexactly(1))[0]
        if first == 0x7F:
            words = int.from_bytes(await self._reader.readexactly(3), "little")
        else:
            words = first
        return await self._reader.readexactly(words * 4)

    async def invoke(self, payload: bytes, *args: Any, **kwargs: Any) -> bytes:
        await self.send(payload)
        return await self.receive()

    async def disconnect(self) -> None:
        writer = self._writer
        self._reader = None
        self._writer = None
        self._connected = False
        if writer is not None:
            writer.close()
            wait_closed = getattr(writer, "wait_closed", None)
            if wait_closed is not None:
                result = wait_closed()
                if asyncio.iscoroutine(result):
                    await result


__all__ = ["AbridgedTransport", "MTProtoTransportError"]
