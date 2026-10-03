"""UZ: Webhook rejimi — Telegram update'larni HTTP POST orqali yuboradi.
RU: Режим webhook — Telegram присылает update через HTTP POST.
EN: Webhook mode — Telegram delivers updates via HTTP POST.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from aiohttp import web

log = logging.getLogger("zafather.webhook")

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
_SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,256}$")

FeedUpdate = Callable[[Mapping[str, Any]], Awaitable[Any]]


def validate_secret_token(secret_token: str | None) -> None:
    """UZ: Telegram talabi: 1-256 belgi, faqat `A-Z a-z 0-9 _ -`.
    RU: Требование Telegram: 1-256 символов, только `A-Z a-z 0-9 _ -`.
    EN: Telegram requires 1-256 characters from `A-Z a-z 0-9 _ -`.
    """
    if secret_token is not None and not _SECRET_PATTERN.match(secret_token):
        raise ValueError("secret_token must be 1-256 characters of A-Z, a-z, 0-9, _ or -")


class WebhookRequestHandler:
    """UZ: aiohttp handleri: maxfiy tokenni tekshiradi va update'ni uzatadi.
    RU: Обработчик aiohttp: проверяет секретный токен и передаёт update.
    EN: aiohttp handler: checks the secret token and forwards the update.

    UZ: `background=True` — Telegram'ga darhol 200 qaytariladi, update fonda
    ishlanadi; `close()` ularning tugashini kutadi.
    RU: `background=True` — Telegram сразу получает 200, update обрабатывается в фоне;
    `close()` дожидается их завершения.
    EN: With `background=True` Telegram gets an immediate 200 and the update is
    processed in the background; `close()` waits for those tasks.
    """

    def __init__(
        self,
        feed: FeedUpdate,
        *,
        secret_token: str | None = None,
        background: bool = True,
    ) -> None:
        validate_secret_token(secret_token)
        if secret_token is None:
            log.warning("Webhook has no secret_token: anyone who knows the URL can post updates")
        self.feed = feed
        self.secret_token = secret_token
        self.background = background
        self._tasks: set[asyncio.Task[None]] = set()

    def _authorized(self, request: web.Request) -> bool:
        if self.secret_token is None:
            return True
        received = request.headers.get(SECRET_HEADER, "")
        return hmac.compare_digest(received.encode(), self.secret_token.encode())

    async def _feed_safely(self, payload: Mapping[str, Any]) -> None:
        try:
            await self.feed(payload)
        except Exception:
            log.exception("Failed to process webhook update %s", payload.get("update_id"))

    async def handle(self, request: web.Request) -> web.Response:
        """UZ: aiohttp so'rov handleri. RU: Обработчик запроса aiohttp.
        EN: The aiohttp request handler.
        """
        if not self._authorized(request):
            return web.Response(status=403)
        try:
            payload = await request.json()
        except ValueError:
            return web.Response(status=400, text="invalid JSON")
        if not isinstance(payload, dict):
            return web.Response(status=400, text="update must be a JSON object")
        if self.background:
            task = asyncio.create_task(self._feed_safely(payload))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        else:
            await self._feed_safely(payload)
        return web.Response(text="ok")

    async def close(self, timeout: float | None = 30.0) -> None:
        if self._tasks:
            await asyncio.wait(set(self._tasks), timeout=timeout)


class WebhookServer:
    """UZ: Webhook uchun alohida aiohttp server.
    RU: Отдельный aiohttp-сервер для webhook.
    EN: A standalone aiohttp server for webhooks.
    """

    def __init__(
        self,
        feed: FeedUpdate,
        *,
        path: str = "/webhook",
        secret_token: str | None = None,
        host: str = "0.0.0.0",
        port: int = 8080,
        background: bool = True,
    ) -> None:
        self.path = path
        self.host = host
        self.port = port
        self.handler = WebhookRequestHandler(feed, secret_token=secret_token, background=background)
        self.web = web.Application()
        self.web.router.add_post(path, self.handler.handle)
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        self._runner = web.AppRunner(self.web)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.host, self.port).start()
        log.info("Webhook server listening on http://%s:%s%s", self.host, self.port, self.path)

    async def stop(self) -> None:
        await self.handler.close()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None


__all__ = ["SECRET_HEADER", "WebhookRequestHandler", "WebhookServer", "validate_secret_token"]
