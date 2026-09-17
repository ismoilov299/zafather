"""UZ: Zafather uchun mustaqil MTProto client yadrosi.
RU: Независимое ядро MTProto-клиента для Zafather.
EN: Independent MTProto client foundation for Zafather.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

from .transport import AbridgedTransport


@dataclass(frozen=True)
class EventBuilder:
    """UZ/RU/EN: UserBot event filtri uchun yengil builder."""

    kind: str
    args: Tuple[Any, ...] = ()
    kwargs: dict = None

    def __post_init__(self) -> None:
        if self.kwargs is None:
            object.__setattr__(self, "kwargs", {})


class Events:
    """UZ/RU/EN: UserBot event builderlari."""

    @staticmethod
    def NewMessage(*args: Any, **kwargs: Any) -> EventBuilder:
        return EventBuilder("new_message", args, kwargs)

    @staticmethod
    def CallbackQuery(*args: Any, **kwargs: Any) -> EventBuilder:
        return EventBuilder("callback_query", args, kwargs)


class MTProtoClient:
    """UZ: Telethon'siz mustaqil client interfeysi.
    RU: Независимый клиент без Telethon.
    EN: Standalone client without Telethon.

    UZ: `transport` auth va binary MTProto qatlamini ulash uchun backenddir.
    RU: `transport` подключает auth и бинарный слой MTProto.
    EN: `transport` is the backend for auth and binary MTProto transport.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session: str = "zafather_user",
        transport: Any = None,
        **kwargs: Any,
    ) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.session = session
        if transport is None:
            transport = AbridgedTransport(
                host=kwargs.pop("dc_host", "149.154.167.50"),
                port=kwargs.pop("dc_port", 443),
            )
        self.transport = transport
        self.options = kwargs
        self.handlers: List[Tuple[EventBuilder, Callable]] = []
        self.connected = False
        self._stopped = asyncio.Event()

    async def connect(self) -> None:
        if self.transport is not None and hasattr(self.transport, "connect"):
            result = self.transport.connect()
            if asyncio.iscoroutine(result):
                await result
        self.connected = True
        self._stopped.clear()

    async def disconnect(self) -> None:
        if self.transport is not None and hasattr(self.transport, "disconnect"):
            result = self.transport.disconnect()
            if asyncio.iscoroutine(result):
                await result
        self.connected = False
        self._stopped.set()

    async def start(self, **kwargs: Any) -> "MTProtoClient":
        await self.connect()
        if self.transport is not None and hasattr(self.transport, "start"):
            result = self.transport.start(**kwargs)
            if asyncio.iscoroutine(result):
                await result
        return self

    async def run_until_disconnected(self) -> None:
        await self._stopped.wait()

    def on(self, event: EventBuilder) -> Callable:
        def decorator(callback: Callable) -> Callable:
            self.handlers.append((event, callback))
            return callback
        return decorator

    def add_event_handler(self, callback: Callable, event: EventBuilder) -> None:
        self.handlers.append((event, callback))

    def remove_event_handler(self, callback: Callable, event: Optional[EventBuilder] = None) -> None:
        self.handlers[:] = [
            (registered, handler)
            for registered, handler in self.handlers
            if handler is not callback or (event is not None and registered != event)
        ]

    async def __call__(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        if self.transport is None or not hasattr(self.transport, "invoke"):
            raise NotImplementedError(
                "MTProto TL schema va auth transport hali ulanmagan; "
                "transport='...' backendini bering"
            )
        payload = request.to_bytes() if hasattr(request, "to_bytes") else request
        result = self.transport.invoke(payload, *args, **kwargs)
        return await result if asyncio.iscoroutine(result) else result


__all__ = ["EventBuilder", "Events", "MTProtoClient"]
