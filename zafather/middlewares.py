"""UZ: Tayyor middleware'lar: throttling, chat action va albomlarni yig'ish.
RU: Готовые middleware: throttling, chat action и сборка альбомов.
EN: Ready-made middlewares: throttling, chat action and album grouping.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from .router import NextHandler

log = logging.getLogger("zafather.middlewares")

KeyFunction = Callable[[Any, dict[str, Any]], Any]


class BaseMiddleware(ABC):
    """UZ: Sinf ko'rinishidagi middleware uchun asos: `__call__(event, data, next_)`.
    RU: Основа для middleware-классов: `__call__(event, data, next_)`.
    EN: Base for class-based middlewares: `__call__(event, data, next_)`.
    """

    @abstractmethod
    async def __call__(self, event: Any, data: dict[str, Any], next_: NextHandler) -> Any:
        """UZ: `next_` chaqirilmasa event to'xtaydi. RU: Без вызова `next_` событие
        останавливается. EN: Not calling `next_` stops the event.
        """


def _user_key(event: Any, data: dict[str, Any]) -> Any:
    return data.get("user_id")


class ThrottlingMiddleware(BaseMiddleware):
    """UZ: Bir kalitdan (standart — foydalanuvchi) `rate` soniyadan tez kelgan
    update'larni tashlaydi.
    RU: Отбрасывает update от одного ключа (по умолчанию — пользователя), пришедшие
    чаще, чем раз в `rate` секунд.
    EN: Drops updates from the same key (the user by default) arriving faster than
    once per `rate` seconds.
    """

    def __init__(
        self,
        rate: float = 0.5,
        key_func: KeyFunction | None = None,
        on_throttled: Callable[[Any, dict[str, Any]], Any] | None = None,
    ) -> None:
        self.rate = rate
        self.key_func = key_func or _user_key
        self.on_throttled = on_throttled
        self._last_seen: dict[Any, float] = {}
        self._next_cleanup = 0.0

    def _cleanup(self, now: float) -> None:
        if now < self._next_cleanup:
            return
        self._next_cleanup = now + max(self.rate * 10, 60.0)
        expired = [key for key, seen in self._last_seen.items() if now - seen >= self.rate]
        for key in expired:
            del self._last_seen[key]

    async def __call__(self, event: Any, data: dict[str, Any], next_: NextHandler) -> Any:
        key = self.key_func(event, data)
        if key is None:
            return await next_(event, data)
        now = time.monotonic()
        self._cleanup(now)
        last = self._last_seen.get(key)
        if last is not None and now - last < self.rate:
            if self.on_throttled is not None:
                result = self.on_throttled(event, data)
                if asyncio.iscoroutine(result):
                    await result
            return False
        self._last_seen[key] = now
        return await next_(event, data)


class ChatActionMiddleware(BaseMiddleware):
    """UZ: Handler ishlayotganda chatga "typing" kabi harakatni ko'rsatib turadi.
    RU: Пока handler работает, показывает в чате действие вроде "typing".
    EN: Shows an action such as "typing" in the chat while the handler runs.

    UZ: `delay` — birinchi yuborishdan oldin kutish (tez handlerlar uchun yuborilmaydi),
    `interval` — Telegram harakatni ~5 soniya ko'rsatgani uchun takrorlash oralig'i.
    RU: `delay` — пауза перед первой отправкой (для быстрых handler не отправляется),
    `interval` — период повтора, так как Telegram показывает действие ~5 секунд.
    EN: `delay` waits before the first send (fast handlers never trigger it) and
    `interval` repeats it, because Telegram shows an action for about 5 seconds.
    """

    def __init__(self, action: str = "typing", delay: float = 0.0, interval: float = 4.5) -> None:
        self.action = action
        self.delay = delay
        self.interval = interval

    async def _send(self, bot: Any, chat_id: int) -> bool:
        try:
            await bot.request("sendChatAction", chat_id=chat_id, action=self.action)
        except Exception as exc:
            log.debug("sendChatAction failed: %s", exc)
            return False
        return True

    async def _repeat(self, bot: Any, chat_id: int, first_delay: float) -> None:
        delay = first_delay
        while True:
            await asyncio.sleep(delay)
            if not await self._send(bot, chat_id):
                return
            delay = self.interval

    async def __call__(self, event: Any, data: dict[str, Any], next_: NextHandler) -> Any:
        bot, chat_id = data.get("bot"), data.get("chat_id")
        if bot is None or chat_id is None:
            return await next_(event, data)
        first_delay = self.delay
        if first_delay <= 0:
            await self._send(bot, chat_id)
            first_delay = self.interval
        repeater = asyncio.create_task(self._repeat(bot, chat_id, first_delay))
        try:
            return await next_(event, data)
        finally:
            repeater.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await repeater


class _Album:
    __slots__ = ("changed", "messages")

    def __init__(self, first: Any) -> None:
        self.messages = [first]
        self.changed = asyncio.Event()

    def add(self, message: Any) -> None:
        self.messages.append(message)
        self.changed.set()

    async def wait_until_quiet(self, latency: float) -> None:
        while True:
            self.changed.clear()
            try:
                await asyncio.wait_for(self.changed.wait(), timeout=latency)
            except asyncio.TimeoutError:
                return


class AlbumMiddleware(BaseMiddleware):
    """UZ: Bir `media_group_id` dagi xabarlarni bitta chaqiruvga yig'adi: handlerga
    `album` (message_id bo'yicha tartiblangan ro'yxat) keladi.
    RU: Собирает сообщения одного `media_group_id` в один вызов: в handler
    передаётся `album` (список, отсортированный по message_id).
    EN: Groups messages sharing a `media_group_id` into one call: the handler receives
    `album` (a list sorted by message_id).

    UZ: Update'lar parallel ishlanishi kerak (`concurrent=True`, standart).
    RU: Требуется параллельная обработка update (`concurrent=True`, по умолчанию).
    EN: Requires concurrent update processing (`concurrent=True`, the default).
    """

    def __init__(self, latency: float = 0.5) -> None:
        self.latency = latency
        self._albums: dict[str, _Album] = {}

    async def __call__(self, event: Any, data: dict[str, Any], next_: NextHandler) -> Any:
        group_id = getattr(event, "media_group_id", None)
        if not group_id:
            return await next_(event, data)
        album = self._albums.get(group_id)
        if album is not None:
            album.add(event)
            return True
        album = self._albums[group_id] = _Album(event)
        try:
            await album.wait_until_quiet(self.latency)
        finally:
            self._albums.pop(group_id, None)
        messages = sorted(
            album.messages, key=lambda message: getattr(message, "message_id", 0) or 0
        )
        return await next_(messages[0], {**data, "album": messages})


__all__ = ["AlbumMiddleware", "BaseMiddleware", "ChatActionMiddleware", "ThrottlingMiddleware"]
