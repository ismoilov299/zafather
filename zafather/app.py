"""UZ: Zafather — ilova fasadi: router + dispatcher + polling/webhook + hayot sikli.
RU: Zafather — фасад приложения: router + dispatcher + polling/webhook + жизненный цикл.
EN: Zafather — the application facade: router + dispatcher + polling/webhook + lifecycle.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, TypeVar
from urllib.parse import urlparse

from .api import PRODUCTION, BaseSession, RetryPolicy, TelegramAPIServer
from .bot import Bot
from .dispatcher import Dispatcher
from .enums import UpdateType
from .fsm import BaseStorage, FSMStrategy, MemoryStorage
from .handler import CallableSpec
from .polling import LongPolling
from .router import Router
from .types import Update
from .webhook import WebhookServer, validate_secret_token

if TYPE_CHECKING:
    from .managed import BotFarm
    from .webapp import MiniApp, WebAppInitData
    from .webserver import MiniAppServer

log = logging.getLogger("zafather")

HookT = TypeVar("HookT", bound=Callable[..., Any])

BANNER = r"""
 ______        __        _   _
|__  / __ _  / _| __ _ | |_| |__   ___ _ __
  / / / _` || |_ / _` || __| '_ \ / _ \ '__|
 / /_| (_| ||  _| (_| || |_| | | |  __/ |
/____|\__,_||_|  \__,_| \__|_| |_|\___|_|
"""


class Zafather(Router):
    """UZ: Botni yaratish va ishga tushirish uchun asosiy sinf (u o'zi ham Router).
    RU: Основной класс для создания и запуска бота (сам является Router).
    EN: The main class for building and running a bot (it is a Router itself).

    UZ: Misol / RU: Пример / EN: Example::

        bot = Zafather("TOKEN")

        @bot.command("start")
        async def start(message: Message):
            await message.answer("Salom!")

        bot.run()                       # long polling
        # bot.run_webhook("https://example.com/webhook", secret_token="...")
    """

    def __init__(
        self,
        token: str | Bot,
        parse_mode: str | None = "HTML",
        storage: BaseStorage | None = None,
        api_url: str | TelegramAPIServer = PRODUCTION,
        polling_timeout: int = 30,
        concurrent: bool = True,
        name: str = "zafather",
        *,
        session: BaseSession | None = None,
        retry: RetryPolicy | None = None,
        request_timeout: float = 60.0,
        fsm_strategy: FSMStrategy = FSMStrategy.USER_IN_CHAT,
        max_concurrent_updates: int | None = None,
        close_storage: bool = True,
    ) -> None:
        super().__init__(name=name)
        self.bot = (
            token
            if isinstance(token, Bot)
            else Bot(token, parse_mode, api_url, request_timeout, session=session, retry=retry)
        )
        self.storage: BaseStorage = storage or MemoryStorage()
        self.data: dict[str, Any] = {}
        self.polling_timeout = polling_timeout
        self.concurrent = concurrent
        self.max_concurrent_updates = max_concurrent_updates
        self.dispatcher = Dispatcher(
            self,
            bot=self.bot,
            storage=self.storage,
            strategy=fsm_strategy,
            context=self.data,
            app=self,
        )
        self._close_storage = close_storage
        self._startup_hooks: list[CallableSpec] = []
        self._shutdown_hooks: list[CallableSpec] = []
        self._polling: LongPolling | None = None
        self._stop_event: asyncio.Event | None = None
        self._stop_requested = False
        self._mini_app: MiniApp | None = None

    # --- UZ: hook'lar / RU: хуки / EN: hooks ---------------------------------------------------
    def on_startup(self, hook: HookT) -> HookT:
        """UZ: Ishga tushganda chaqiriladi; `app`, `bot` va `data` kalitlarini olishi mumkin.
        RU: Вызывается при запуске; может принимать `app`, `bot` и ключи `data`.
        EN: Called on startup; may accept `app`, `bot` and any `data` key.
        """
        self._startup_hooks.append(CallableSpec(hook, positional=0))
        return hook

    def on_shutdown(self, hook: HookT) -> HookT:
        """UZ: To'xtashda chaqiriladi. RU: Вызывается при остановке. EN: Called on shutdown."""
        self._shutdown_hooks.append(CallableSpec(hook, positional=0))
        return hook

    def _hook_context(self) -> dict[str, Any]:
        return {**self.data, "app": self, "bot": self.bot}

    async def _startup(self) -> None:
        for hook in self._startup_hooks:
            await hook(context=self._hook_context())

    async def _shutdown(self) -> None:
        for hook in self._shutdown_hooks:
            try:
                await hook(context=self._hook_context())
            except Exception:
                log.exception("on_shutdown hook failed")

    async def _release_resources(self) -> None:
        if self._close_storage:
            await self.storage.close()
        await self.bot.close()

    # --- UZ: update'lar / RU: update / EN: updates -------------------------------------
    async def feed_update(self, update: Update) -> bool:
        """UZ: Bitta update'ni qayta ishlaydi. RU: Обрабатывает один update.
        EN: Processes a single update.
        """
        return await self.dispatcher.feed_update(update)

    async def feed_raw_update(self, payload: Mapping[str, Any]) -> bool:
        return await self.dispatcher.feed_raw_update(payload)

    async def handle_webhook(self, payload: Mapping[str, Any]) -> bool:
        """UZ: Tashqi web-frameworkdan (FastAPI, aiohttp) kelgan JSON'ni qayta ishlaydi.
        RU: Обрабатывает JSON из внешнего веб-фреймворка (FastAPI, aiohttp).
        EN: Processes JSON received by an external web framework (FastAPI, aiohttp).
        """
        return await self.feed_raw_update(payload)

    # --- UZ: polling / RU: polling / EN: polling -----------------------------------------------
    async def start_polling(
        self, skip_updates: bool = True, allowed_updates: Sequence[str] | None = None
    ) -> None:
        """UZ: Long polling. `allowed_updates=None` — barcha update turlari so'raladi.
        RU: Long polling. `allowed_updates=None` — запрашиваются все типы update.
        EN: Long polling. `allowed_updates=None` requests every update type.

        UZ: Muhim: `managed_bot`, `guest_message`, `message_reaction` kabi turlar aniq
        so'ralmasa Telegram ularni yubormaydi.
        RU: Важно: типы вроде `managed_bot`, `guest_message`, `message_reaction` Telegram
        присылает только если они явно запрошены.
        EN: Telegram only sends types such as `managed_bot`, `guest_message` or
        `message_reaction` when they are requested explicitly.
        """
        polling = LongPolling(
            self.bot,
            self.feed_update,
            timeout=self.polling_timeout,
            allowed_updates=allowed_updates,
            drop_pending_updates=skip_updates,
            concurrent=self.concurrent,
            max_concurrent=self.max_concurrent_updates,
        )
        self._polling = polling
        if self._stop_requested:
            polling.stop()
        try:
            me = await self.bot.me()
            log.info("Polling started: @%s (id=%s)", me.username, me.id)
            await self._startup()
            try:
                await polling.run()
            finally:
                await self._shutdown()
        finally:
            self._polling = None
            self._stop_requested = False
            await self._release_resources()
            log.info("Stopped.")

    # --- UZ: webhook / RU: webhook / EN: webhook ---------------------------------------------
    async def start_webhook(
        self,
        url: str,
        *,
        path: str | None = None,
        host: str = "0.0.0.0",
        port: int = 8080,
        secret_token: str | None = None,
        drop_pending_updates: bool = False,
        allowed_updates: Sequence[str] | None = None,
        delete_on_shutdown: bool = False,
        **webhook_params: Any,
    ) -> None:
        """UZ: Webhook o'rnatadi va server ishga tushadi (to'xtatilguncha ishlaydi).
        RU: Устанавливает webhook и запускает сервер (работает до остановки).
        EN: Sets the webhook and serves it until stopped.
        """
        validate_secret_token(secret_token)
        server = WebhookServer(
            self.feed_raw_update,
            path=path or urlparse(url).path or "/webhook",
            secret_token=secret_token,
            host=host,
            port=port,
        )
        self._stop_event = asyncio.Event()
        if self._stop_requested:
            self._stop_event.set()
        try:
            await self._startup()
            try:
                await self.bot.call(
                    "setWebhook",
                    url=url,
                    secret_token=secret_token,
                    drop_pending_updates=drop_pending_updates,
                    allowed_updates=list(allowed_updates or UpdateType.ALL),
                    **webhook_params,
                )
                await server.start()
                try:
                    await self._stop_event.wait()
                finally:
                    await server.stop()
                    if delete_on_shutdown:
                        await self.bot.call("deleteWebhook")
            finally:
                await self._shutdown()
        finally:
            self._stop_event = None
            self._stop_requested = False
            await self._release_resources()

    async def stop(self) -> None:
        """UZ: Polling yoki webhook'ni to'xtatadi (ishga tushish arafasida ham).
        RU: Останавливает polling или webhook (в том числе ещё не начавшийся запуск).
        EN: Stops polling or the webhook server (including a run that is about to start).
        """
        self._stop_requested = True
        if self._polling is not None:
            self._polling.stop()
        if self._stop_event is not None:
            self._stop_event.set()

    # --- UZ: sinxron ishga tushirish / RU: синхронный запуск / EN: blocking runners ----------
    def run(
        self,
        skip_updates: bool = True,
        allowed_updates: Sequence[str] | None = None,
        log_level: int = logging.INFO,
        banner: bool = True,
    ) -> None:
        """UZ: Polling'ni ishga tushiradi (Ctrl+C yoki SIGTERM bilan to'xtaydi).
        RU: Запускает polling (останавливается по Ctrl+C или SIGTERM).
        EN: Runs polling until Ctrl+C or SIGTERM.
        """
        self._run_blocking(
            lambda: self.start_polling(skip_updates=skip_updates, allowed_updates=allowed_updates),
            log_level=log_level,
            banner=banner,
        )

    def run_webhook(
        self,
        url: str,
        *,
        log_level: int = logging.INFO,
        banner: bool = True,
        **kwargs: Any,
    ) -> None:
        """UZ: `start_webhook()` ning sinxron varianti. RU: Синхронный вариант `start_webhook()`.
        EN: Blocking variant of `start_webhook()`.
        """
        self._run_blocking(
            lambda: self.start_webhook(url, **kwargs), log_level=log_level, banner=banner
        )

    def _run_blocking(
        self, runner: Callable[[], Awaitable[None]], *, log_level: int, banner: bool
    ) -> None:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        if banner:
            log.info("%s", BANNER)

        async def main() -> None:
            loop = asyncio.get_running_loop()
            for signum in (signal.SIGINT, signal.SIGTERM):
                with contextlib.suppress(NotImplementedError, RuntimeError):
                    loop.add_signal_handler(signum, lambda: asyncio.ensure_future(self.stop()))
            await runner()

        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(main())

    # --- UZ: boshqariladigan botlar / RU: управляемые боты / EN: managed bots -----------------
    def spawn(self, token: str, **kwargs: Any) -> Zafather:
        """UZ: Shu botning handlerlari bilan ishlaydigan yangi bot nusxasini yaratadi.
        RU: Создаёт копию бота с тем же набором handlers.
        EN: Creates a new bot instance that shares this bot's handlers.

            token = await ManagedBots(app.bot).token(bot_id)
            child = app.spawn(token)
            await child.start_polling()
        """
        child = Zafather(
            token,
            parse_mode=kwargs.pop("parse_mode", self.bot.parse_mode),
            storage=kwargs.pop("storage", self.storage),
            api_url=kwargs.pop("api_url", self.bot.server),
            name=kwargs.pop("name", f"child:{token.split(':', 1)[0]}"),
            close_storage=kwargs.pop("close_storage", False),
            **kwargs,
        )
        child.include(self)
        child.data.update(self.data)
        child.data["parent"] = self
        return child

    def farm(self, router: Router | None = None, **kwargs: Any) -> BotFarm:
        """UZ: Ko'p bolalar botni yuritish uchun `BotFarm` yaratadi.
        RU: Создаёт `BotFarm` для управления множеством дочерних ботов.
        EN: Creates a `BotFarm` that runs many child bots.
        """
        from .managed import BotFarm

        kwargs.setdefault("storage", self.storage)
        return BotFarm(router or self, **kwargs)

    # --- Mini App ------------------------------------------------------------------------
    @property
    def mini_app(self) -> MiniApp:
        """UZ: Mini App metodlari. RU: Методы Mini App. EN: Mini App methods."""
        from .webapp import MiniApp

        if self._mini_app is None:
            self._mini_app = MiniApp(self.bot)
        return self._mini_app

    def serve_mini_app(self, static_dir: str | None = None, **kwargs: Any) -> MiniAppServer:
        """UZ: Mini App uchun backend server. RU: Backend-сервер для Mini App.
        EN: A backend server for the Mini App.
        """
        from .webserver import MiniAppServer

        return MiniAppServer(self, static_dir=static_dir, **kwargs)

    def validate_init_data(self, init_data: str, max_age: int = 3600) -> WebAppInitData:
        """UZ: `initData` ni shu bot tokeni bilan tekshiradi.
        RU: Проверяет `initData` токеном этого бота.
        EN: Validates `initData` with this bot's token.
        """
        from .webapp import validate

        return validate(init_data, self.bot.token, max_age)


__all__ = ["BANNER", "Zafather"]
