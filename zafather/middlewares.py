"""UZ: Middleware yordamchilari: throttling, chat action, album grouping.
RU: Middleware helpers: throttling, chat action, группировка album.
EN: Middleware helpers: throttling, chat action, album grouping.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional


class ThrottlingMiddleware:
    """UZ: Bir foydalanuvchidan tez-tez kelgan update'larni tashlaydi.
    RU: Пропускает частые update от одного пользователя.
    EN: Drops frequent updates from the same user.
    """

    def __init__(self, rate: float = 0.5, key_func: Optional[Callable[[Any], Any]] = None):
        self.rate = rate
        self.key_func = key_func or (lambda event, data: data.get("user_id"))
        self._last_time: Dict[Any, float] = {}

    async def __call__(self, event, data: dict, next_):
        key = self.key_func(event, data)
        now = time.monotonic()
        last = self._last_time.get(key)
        if last is not None and now - last < self.rate:
            return False
        self._last_time[key] = now
        return await next_(event, data)


class ChatActionMiddleware:
    """UZ: Uzoq handlerlar oldida `typing` actionini yuboradi.
    RU: Отправляет `typing` перед длительным handler.
    EN: Sends a `typing` action before a long handler.
    """

    def __init__(self, action: str = "typing", delay: float = 0.0):
        self.action = action
        self.delay = delay

    async def __call__(self, event, data: dict, next_):
        bot = data.get("bot")
        chat_id = data.get("chat_id")
        if bot is not None and chat_id is not None and self.delay <= 0:
            await bot.request("sendChatAction", chat_id=chat_id, action=self.action)
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        return await next_(event, data)


class AlbumMiddleware:
    """UZ: `media_group_id` bo'yicha bir xil guruhdagi media'larni birlashtiradi.
    RU: Группирует media по `media_group_id`.
    EN: Groups media with the same `media_group_id`.
    """

    def __init__(self, delay: float = 0.5):
        self.delay = delay
        self._buffer: Dict[str, List[Any]] = defaultdict(list)
        self._timer: Dict[str, asyncio.Task] = {}

    async def __call__(self, event, data: dict, next_):
        media_group_id = getattr(event, "media_group_id", None) or data.get("media_group_id")
        if not media_group_id:
            return await next_(event, data)

        self._buffer[media_group_id].append(event)
        if media_group_id in self._timer:
            await asyncio.sleep(self.delay)
            items = self._buffer.pop(media_group_id, [])
            if items:
                payload = dict(data)
                payload["album"] = items
                await next_(event, payload)
            self._timer.pop(media_group_id, None)
            return True

        async def flush():
            await asyncio.sleep(self.delay)
            items = self._buffer.pop(media_group_id, [])
            if items:
                payload = dict(data)
                payload["album"] = items
                await next_(event, payload)
            self._timer.pop(media_group_id, None)

        self._timer[media_group_id] = asyncio.create_task(flush())
        return False


__all__ = ["ThrottlingMiddleware", "ChatActionMiddleware", "AlbumMiddleware"]
