"""UZ: Long polling — Telegram'dan update'larni `getUpdates` orqali olish.
RU: Long polling — получение update из Telegram через `getUpdates`.
EN: Long polling — receiving updates from Telegram via `getUpdates`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any

from .api import RetryPolicy
from .enums import UpdateType
from .exceptions import NetworkError, TelegramAPIError, Unauthorized
from .types import Update

if TYPE_CHECKING:
    from .bot import Bot

log = logging.getLogger("zafather.polling")

UpdateHandler = Callable[[Update], Awaitable[Any]]


class _StopRequested(Exception):
    pass


class LongPolling:
    """UZ: `getUpdates` siklini boshqaradi: offset, xatolarda kutish, parallel ishlov.
    RU: Управляет циклом `getUpdates`: offset, паузы при ошибках, параллельная обработка.
    EN: Runs the `getUpdates` loop: offsets, backoff on errors, concurrent processing.

    UZ: `stop()` kutilayotgan so'rovni darhol bekor qiladi; ishlayotgan handlerlar
    `shutdown_timeout` gacha kutiladi.
    RU: `stop()` сразу отменяет ожидающий запрос; работающие handlers ждут до
    `shutdown_timeout`.
    EN: `stop()` cancels the pending request immediately; running handlers get up to
    `shutdown_timeout` seconds to finish.
    """

    def __init__(
        self,
        bot: Bot,
        handle_update: UpdateHandler,
        *,
        timeout: int = 30,
        limit: int = 100,
        allowed_updates: Sequence[str] | None = None,
        drop_pending_updates: bool = True,
        concurrent: bool = True,
        max_concurrent: int | None = None,
        shutdown_timeout: float | None = 30.0,
        backoff: RetryPolicy | None = None,
    ) -> None:
        self.bot = bot
        self.handle_update = handle_update
        self.timeout = timeout
        self.limit = limit
        self.allowed_updates = (
            list(allowed_updates) if allowed_updates is not None else list(UpdateType.ALL)
        )
        self.drop_pending_updates = drop_pending_updates
        self.concurrent = concurrent
        self.shutdown_timeout = shutdown_timeout
        self.backoff = backoff or RetryPolicy(backoff_base=1.0, max_backoff=30.0)
        self._semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else None
        self._tasks: set[asyncio.Task[None]] = set()
        self._stop = asyncio.Event()
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def stop(self) -> None:
        """UZ: Pollingni to'xtatishni so'raydi (`run()` dan oldin chaqirilsa ham amal qiladi).
        RU: Запрашивает остановку polling (действует, даже если вызван до `run()`).
        EN: Requests the polling loop to stop (also honoured when called before `run()`).
        """
        self._stop.set()

    async def run(self) -> None:
        if self._running:
            raise RuntimeError("Polling is already running")
        self._running = True
        try:
            await self.bot.call("deleteWebhook", drop_pending_updates=self.drop_pending_updates)
            await self._loop()
        finally:
            await self._drain()
            self._running = False
            self._stop.clear()

    async def _loop(self) -> None:
        offset: int | None = None
        failures = 0
        while not self._stop.is_set():
            try:
                updates = await self._fetch(offset)
            except _StopRequested:
                return
            except Unauthorized:
                raise
            except (TelegramAPIError, NetworkError) as error:
                failures += 1
                delay = self._error_delay(error, failures)
                log.warning("getUpdates failed (%s); retrying in %.1fs", error, delay)
                if await self._sleep_or_stop(delay):
                    return
                continue
            failures = 0
            for raw in updates:
                offset = int(raw["update_id"]) + 1
                await self._dispatch(Update(raw, self.bot))

    def _error_delay(self, error: Exception, failures: int) -> float:
        if isinstance(error, TelegramAPIError) and error.retry_after:
            return float(error.retry_after)
        return self.backoff.backoff(failures)

    async def _fetch(self, offset: int | None) -> list[dict[str, Any]]:
        request = asyncio.ensure_future(
            self.bot.call(
                "getUpdates",
                offset=offset,
                timeout=self.timeout,
                limit=self.limit,
                allowed_updates=self.allowed_updates,
            )
        )
        stopper = asyncio.ensure_future(self._stop.wait())
        try:
            done, _ = await asyncio.wait({request, stopper}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stopper.cancel()
        if request not in done:
            request.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await request
            raise _StopRequested
        return list(request.result() or [])

    async def _sleep_or_stop(self, delay: float) -> bool:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=delay)
        except asyncio.TimeoutError:
            return False
        return True

    async def _dispatch(self, update: Update) -> None:
        if not self.concurrent:
            await self._process(update)
            return
        if self._semaphore is not None:
            await self._semaphore.acquire()
        task = asyncio.create_task(self._process(update))
        self._tasks.add(task)
        task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if self._semaphore is not None:
            self._semaphore.release()

    async def _process(self, update: Update) -> None:
        try:
            await self.handle_update(update)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Failed to process update %s", update.raw.get("update_id"))

    async def _drain(self) -> None:
        if not self._tasks:
            return
        _, pending = await asyncio.wait(set(self._tasks), timeout=self.shutdown_timeout)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


__all__ = ["LongPolling"]
