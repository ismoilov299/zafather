"""UZ: Zafather — asosiy ilova sinfi (dispatcher + polling).
RU: Zafather — основной класс приложения (dispatcher + polling).
EN: Zafather — main application class (dispatcher + polling).
"""
from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any, Callable, List, Optional, Set

from .bot import Bot, NetworkError, TelegramError
from .enums import UpdateType
from .fsm import BaseStorage, FSMContext, MemoryStorage
from .router import Router
from .types import Update

log = logging.getLogger("zafather")

BANNER = r"""
 ______        __        _   _
|__  / __ _  / _| __ _ | |_| |__   ___ _ __
  / / / _` || |_ / _` || __| '_ \ / _ \ '__|
 / /_| (_| ||  _| (_| || |_| | | |  __/ |
/____|\__,_||_|  \__,_| \__|_| |_|\___|_|
"""


class Zafather(Router):
    """UZ: Botni yaratish va ishga tushirish uchun asosiy sinf.
    RU: Основной класс для создания и запуска бота.
    EN: Main class for creating and running a bot.

    UZ: Misol:
    RU: Пример:
    EN: Example:

        bot = Zafather("TOKEN")

        @bot.command("start")
        async def start(m: Message):
            await m.answer("Salom!")

        bot.run()
    """

    def __init__(
        self,
        token: str,
        parse_mode: Optional[str] = "HTML",
        storage: Optional[BaseStorage] = None,
        api_url: str = "https://api.telegram.org",
        polling_timeout: int = 30,
        concurrent: bool = True,
        name: str = "zafather",
    ) -> None:
        super().__init__(name=name)
        self.bot = Bot(token, parse_mode=parse_mode, api_url=api_url, timeout=polling_timeout)
        self.storage: BaseStorage = storage or MemoryStorage()
        self.polling_timeout = polling_timeout
        self.concurrent = concurrent
        self.data: dict = {}  # global kontekst (DB, config va h.k.)
        self._offset: Optional[int] = None
        self._running = False
        self._tasks: Set[asyncio.Task] = set()
        self._mini_app = None
        self._startup: List[Callable] = []
        self._shutdown: List[Callable] = []

    # --- UZ: hook'lar / RU: хуки / EN: hooks -----------------------------------
    def on_startup(self, func: Callable) -> Callable:
        self._startup.append(func)
        return func

    def on_shutdown(self, func: Callable) -> Callable:
        self._shutdown.append(func)
        return func

    # --- UZ: update'ni qayta ishlash / RU: обработка update / EN: update handling ---
    def _make_context(self, event, event_type: str) -> dict:
        chat = getattr(event, "chat", None)
        if chat is None:
            message = getattr(event, "message", None)
            chat = getattr(message, "chat", None) if message else None
        user = getattr(event, "from_user", None)
        chat_id = chat.id if chat else (user.id if user else 0)
        user_id = user.id if user else chat_id
        return {"key": (chat_id, user_id), "chat_id": chat_id, "user_id": user_id}

    async def feed_update(self, update: Update) -> bool:
        """UZ: Bitta update'ni handlerlarga uzatadi.
        RU: Передаёт один update обработчикам.
        EN: Passes a single update to handlers.
        """
        event_type = update.event_type
        event = update.event
        if event_type is None or event is None:
            log.debug("Qo'llab-quvvatlanmaydigan update: %s", update.raw.keys())
            return False

        ctx = self._make_context(event, event_type)
        state = FSMContext(self.storage, ctx["key"])
        data = {
            **self.data,
            "bot": self.bot,
            "app": self,
            "update": update,
            "event_type": event_type,
            "state": state,
            "raw_state": await state.get_state(),
            "chat_id": ctx["chat_id"],
            "user_id": ctx["user_id"],
        }
        try:
            return await self.trigger(event_type, event, data)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            handled = await self.handle_error(event, exc, data)
            if not handled:
                log.exception("Handler xatosi (%s): %s", event_type, exc)
            return False

    async def _spawn(self, update: Update) -> None:
        task = asyncio.create_task(self.feed_update(update))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    # --- UZ: polling / RU: polling / EN: polling -------------------------------
    async def start_polling(
        self,
        skip_updates: bool = True,
        allowed_updates: Optional[List[str]] = None,
        banner: bool = False,
    ) -> None:
        """UZ: Long polling. `allowed_updates=None` — barcha update turlari so'raladi.
        RU: Long polling. `allowed_updates=None` — запрашиваются все типы update.
        EN: Long polling. `allowed_updates=None` requests all update types.

        UZ: Bu muhim: `managed_bot`, `guest_message`, `message_reaction`,
        `subscription` kabi yangi turlar aniq so'ralmasa Telegram ularni
        yubormaydi.
        RU: Это важно: если новые типы вроде `managed_bot`, `guest_message`,
        `message_reaction`, `subscription` не указаны явно, Telegram их не
        присылает.
        EN: This matters because Telegram will not send newer types such as
        `managed_bot`, `guest_message`, `message_reaction`, or `subscription`
        unless they are explicitly requested.
        """
        self._running = True
        if allowed_updates is None:
            allowed_updates = list(UpdateType.ALL)
        me = await self.bot.me()
        log.info("Ishga tushdi: @%s (id=%s)", me.username, me.id)

        for hook in self._startup:
            await self._maybe_await(hook)

        if skip_updates:
            pending = await self.bot.call("getUpdates", offset=-1, timeout=0)
            if pending:
                self._offset = pending[-1]["update_id"] + 1

        try:
            while self._running:
                try:
                    raw_updates = await self.bot.call(
                        "getUpdates",
                        offset=self._offset,
                        timeout=self.polling_timeout,
                        allowed_updates=allowed_updates,
                    )
                except asyncio.CancelledError:
                    raise
                except (NetworkError, TelegramError) as exc:
                    log.warning("getUpdates xatosi: %s — 3s dan keyin qayta urinish", exc)
                    await asyncio.sleep(3)
                    continue

                for raw in raw_updates or []:
                    self._offset = raw["update_id"] + 1
                    update = Update(raw, self.bot)
                    if self.concurrent:
                        await self._spawn(update)
                    else:
                        await self.feed_update(update)
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        self._running = False
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
        for hook in self._shutdown:
            try:
                await self._maybe_await(hook)
            except Exception:  # noqa: BLE001
                log.exception("on_shutdown xatosi")
        await self.storage.close()
        await self.bot.close()
        log.info("To'xtatildi.")

    async def stop(self) -> None:
        self._running = False

    @staticmethod
    async def _maybe_await(func: Callable) -> Any:
        result = func() if callable(func) else func
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            return await result
        return result

    # --- managed bots ---------------------------------------------------------
    def spawn(self, token: str, **kwargs) -> "Zafather":
        """Yangi (yaratilgan) bot uchun nusxa qaytaradi — handlerlar meros bo'ladi.

            token = await ManagedBots(bot.bot).token(bot_id)
            child = bot.spawn(token)
            await child.start_polling()
        """
        child = Zafather(
            token,
            parse_mode=kwargs.pop("parse_mode", self.bot.parse_mode),
            storage=kwargs.pop("storage", self.storage),
            api_url=kwargs.pop("api_url", self.bot.api_url),
            name=kwargs.pop("name", f"child:{token.split(':')[0]}"),
            **kwargs,
        )
        child.sub_routers.append(self)   # ota-bot handlerlaridan foydalanadi
        child.data.update(self.data)
        child.data["parent"] = self
        return child

    def farm(self, router=None, **kwargs):
        """Ko'p bolalar botni yuritish uchun `BotFarm` yaratadi."""
        from .managed import BotFarm

        return BotFarm(router or self, storage=self.storage, **kwargs)

    # --- Mini App -------------------------------------------------------------
    @property
    def mini_app(self):
        """Mini App metodlari: menyu tugmasi, answerWebAppQuery va h.k."""
        from .webapp import MiniApp

        if self._mini_app is None:
            self._mini_app = MiniApp(self.bot)
        return self._mini_app

    def serve_mini_app(self, static_dir: str = None, **kwargs):
        """Mini App uchun backend server yaratadi."""
        from .webserver import MiniAppServer

        return MiniAppServer(self, static_dir=static_dir, **kwargs)

    def validate_init_data(self, init_data: str, max_age: int = 3600):
        """Mini App'dan kelgan `initData` ni shu botning tokeni bilan tekshiradi."""
        from .webapp import validate

        return validate(init_data, self.bot.token, max_age)

    # --- webhook uchun --------------------------------------------------------
    async def handle_webhook(self, payload: dict) -> bool:
        """Webhook'dan kelgan JSON'ni qayta ishlash (FastAPI/aiohttp bilan)."""
        return await self.feed_update(Update(payload, self.bot))

    # --- sinxron ishga tushirish ---------------------------------------------
    def run(
        self,
        skip_updates: bool = True,
        allowed_updates: Optional[List[str]] = None,
        log_level: int = logging.INFO,
        banner: bool = True,
    ) -> None:
        """Botni ishga tushiradi (Ctrl+C bilan to'xtatiladi)."""
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        if banner:
            print(BANNER)

        async def main() -> None:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
                except (NotImplementedError, AttributeError):
                    pass  # Windows
            await self.start_polling(
                skip_updates=skip_updates,
                allowed_updates=allowed_updates,
                banner=False,
            )

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            log.info("Ctrl+C — to'xtatilmoqda…")

    def __repr__(self) -> str:
        total = sum(len(v) for v in self.handlers.values())
        return f"<Zafather handlers={total} routers={len(self.sub_routers)}>"
