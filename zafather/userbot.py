"""UZ: Mustaqil MTProto userbot API.
RU: Независимый API userbot на MTProto.
EN: Standalone MTProto userbot API.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable, Optional

from .mtproto import Events, MTProtoClient

log = logging.getLogger("zafather.userbot")


class UserBot:
    """UZ: Telethon'siz ishlaydigan MTProto userbot fasadi.
    RU: Фасад userbot на MTProto без Telethon.
    EN: Telethon-free MTProto userbot facade.

    `transport` mustaqil auth, crypto va TL backendini ulaydi. UZ/RU/EN::

        userbot = UserBot(12345, "api-hash", transport=my_transport)
        @userbot.on_new_message(pattern="/hello")
        async def hello(event):
            await event.respond("Salom!")
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session: str = "zafather_user",
        client: Any = None,
        events_module: Any = None,
        transport: Any = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        max_reconnects: int = 5,
        reconnect_delay: float = 2.0,
        backoff: float = 2.0,
        **kwargs: Any,
    ) -> None:
        if not isinstance(api_id, int) or api_id <= 0:
            raise ValueError("api_id musbat integer bo'lishi kerak")
        if not isinstance(api_hash, str) or not api_hash.strip():
            raise ValueError("api_hash bo'sh bo'lmasligi kerak")
        if max_retries < 0 or max_reconnects < 0:
            raise ValueError("max_retries va max_reconnects manfiy bo'lmasligi kerak")
        if retry_delay < 0 or reconnect_delay < 0 or backoff < 1:
            raise ValueError("delay manfiy emas, backoff esa kamida 1 bo'lishi kerak")

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_reconnects = max_reconnects
        self.reconnect_delay = reconnect_delay
        self.backoff = backoff
        self.client = client or MTProtoClient(
            api_id, api_hash, session=session, transport=transport, **kwargs
        )
        self.events = events_module or Events

    @staticmethod
    def _flood_wait_seconds(error: BaseException) -> Optional[float]:
        if type(error).__name__ != "FloodWaitError":
            return None
        seconds = getattr(error, "seconds", None)
        return float(seconds) if isinstance(seconds, (int, float)) else None

    @staticmethod
    def _is_connection_error(error: BaseException) -> bool:
        return isinstance(error, (ConnectionError, OSError, asyncio.TimeoutError))

    async def _sleep(self, delay: float) -> None:
        if delay > 0:
            await asyncio.sleep(delay)

    async def _execute(self, operation: Callable[[], Any]) -> Any:
        retries = 0
        reconnects = 0
        while True:
            try:
                result = operation()
                return await result if inspect.isawaitable(result) else result
            except Exception as exc:  # noqa: BLE001
                flood_wait = self._flood_wait_seconds(exc)
                if flood_wait is not None:
                    if retries >= self.max_retries:
                        raise
                    retries += 1
                    log.warning("FloodWait: %ss kutilmoqda", flood_wait)
                    await self._sleep(flood_wait)
                    continue
                if not self._is_connection_error(exc) or reconnects >= self.max_reconnects:
                    raise
                reconnects += 1
                log.warning("UserBot reconnect %s/%s", reconnects, self.max_reconnects)
                await self._sleep(self.reconnect_delay * (self.backoff ** (reconnects - 1)))
                connect = getattr(self.client, "connect", None)
                if connect is not None:
                    result = connect()
                    if inspect.isawaitable(result):
                        await result

    def on(self, event_builder: Any) -> Callable:
        return self.client.on(event_builder)

    def on_message(self, *args: Any, **kwargs: Any) -> Callable:
        return self.client.on(self.events.NewMessage(*args, **kwargs))

    def on_callback(self, *args: Any, **kwargs: Any) -> Callable:
        return self.client.on(self.events.CallbackQuery(*args, **kwargs))

    def on_new_message(self, *args: Any, **kwargs: Any) -> Callable:
        return self.on_message(*args, **kwargs)

    def on_callback_query(self, *args: Any, **kwargs: Any) -> Callable:
        return self.on_callback(*args, **kwargs)

    async def start(self, phone: Optional[str] = None, **kwargs: Any) -> Any:
        if phone is not None:
            kwargs["phone"] = phone
        return await self._execute(lambda: self.client.start(**kwargs))

    async def run_until_disconnected(self) -> Any:
        reconnects = 0
        while True:
            try:
                return await self.client.run_until_disconnected()
            except Exception as exc:  # noqa: BLE001
                if not self._is_connection_error(exc) or reconnects >= self.max_reconnects:
                    raise
                reconnects += 1
                await self._sleep(self.reconnect_delay * (self.backoff ** (reconnects - 1)))
                connect = getattr(self.client, "connect", None)
                if connect is not None:
                    result = connect()
                    if inspect.isawaitable(result):
                        await result

    async def run(self) -> Any:
        await self.start()
        return await self.run_until_disconnected()

    async def disconnect(self) -> None:
        result = self.client.disconnect()
        if inspect.isawaitable(result):
            await result

    async def send_message(self, entity: Any, message: Any, **kwargs: Any) -> Any:
        return await self._execute(lambda: self.client.send_message(entity, message, **kwargs))

    async def call(self, method: Any, *args: Any, **kwargs: Any) -> Any:
        target = getattr(self.client, method) if isinstance(method, str) else method
        return await self._execute(lambda: target(*args, **kwargs))

    async def request(self, method: Any, *args: Any, **kwargs: Any) -> Any:
        return await self.call(method, *args, **kwargs)

    async def invoke(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        return await self._execute(lambda: self.client(request, *args, **kwargs))

    def add_handler(self, callback: Callable, event_builder: Any) -> Any:
        return self.client.add_event_handler(callback, event_builder)

    def remove_handler(self, callback: Callable, event_builder: Any = None) -> Any:
        return self.client.remove_event_handler(callback, event_builder)

    async def __aenter__(self) -> "UserBot":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.disconnect()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.client, name)


__all__ = ["UserBot"]
