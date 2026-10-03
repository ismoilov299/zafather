"""UZ: Zafather — **Managed Bots**: bot yaratadigan botlar (Bot API 9.6+).
RU: Zafather — **Managed Bots**: боты, создающие ботов (Bot API 9.6+).
EN: Zafather — **Managed Bots**: bots that create bots (Bot API 9.6+).

UZ: Ish tartibi / RU: Порядок работы / EN: Workflow:

1. UZ: @BotFather'da manager botga *Bot Management Mode* yoqiladi.
   RU: В @BotFather для manager-бота включается *Bot Management Mode*.
   EN: Enable *Bot Management Mode* for the manager bot in @BotFather.
2. UZ: Foydalanuvchiga `ManagedBots.create_link()` havolasi yoki
   `ReplyKeyboard.request_bot()` tugmasi beriladi.
   RU: Пользователь получает ссылку `ManagedBots.create_link()` или кнопку
   `ReplyKeyboard.request_bot()`.
   EN: The user gets a `ManagedBots.create_link()` link or a
   `ReplyKeyboard.request_bot()` button.
3. UZ: Tasdiqlangach `managed_bot` update keladi; token `ManagedBots.token()` bilan olinadi.
   RU: После подтверждения приходит update `managed_bot`; токен берётся через
   `ManagedBots.token()`.
   EN: After confirmation a `managed_bot` update arrives; fetch the token with
   `ManagedBots.token()`.
4. UZ: `BotFarm.add(token)` yangi botni shu zahoti ishga tushiradi.
   RU: `BotFarm.add(token)` сразу запускает нового бота.
   EN: `BotFarm.add(token)` starts the new bot right away.

::

    farm = BotFarm(child_router)

    @app.managed_bot()
    async def on_new_bot(event: ManagedBotUpdated, bot: Bot):
        token = await ManagedBots(bot).token(event.bot_id)
        await farm.add(token)
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from .api import PRODUCTION, TelegramAPIServer
from .fsm import BaseStorage

if TYPE_CHECKING:
    from .app import Zafather
    from .bot import Bot
    from .router import Router

log = logging.getLogger("zafather.managed")


def _token_from_result(result: Any) -> str | None:
    if isinstance(result, dict):
        return result.get("token") or result.get("access_token")
    return result if isinstance(result, str) else None


def bot_id_from_token(token: str) -> int:
    """UZ: Tokenning bot ID qismi. RU: ID бота из токена. EN: The bot ID part of a token."""
    return int(str(token).split(":", 1)[0])


class ManagedBots:
    """UZ: Boshqariladigan bot metodlari ustidagi qobiq.
    RU: Обёртка над методами управляемых ботов.
    EN: A wrapper over the managed bot methods.

    UZ: Qo'shimcha parametrlar rasmiy hujjat bo'yicha `**params` orqali beriladi.
    RU: Дополнительные параметры передаются через `**params` по документации.
    EN: Extra parameters are passed through `**params` as documented.
    """

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @staticmethod
    def create_link(manager_username: str, suggested_username: str, name: str | None = None) -> str:
        """UZ: Bot yaratish havolasi: `t.me/newbot/<manager>/<username>?name=<nom>`.
        RU: Ссылка создания бота: `t.me/newbot/<manager>/<username>?name=<имя>`.
        EN: A bot creation link: `t.me/newbot/<manager>/<username>?name=<name>`.
        """
        url = f"https://t.me/newbot/{manager_username.lstrip('@')}/{suggested_username.lstrip('@')}"
        return f"{url}?name={quote(name)}" if name else url

    @staticmethod
    def _params(bot_id: int | None, params: dict[str, Any]) -> dict[str, Any]:
        if bot_id is not None:
            params.setdefault("bot_id", bot_id)
        return params

    async def token(self, bot_id: int | None = None, **params: Any) -> str | None:
        """UZ: Boshqariladigan bot tokeni. RU: Токен управляемого бота.
        EN: The managed bot token.
        """
        result = await self.bot.call("getManagedBotToken", **self._params(bot_id, params))
        return _token_from_result(result)

    async def replace_token(self, bot_id: int | None = None, **params: Any) -> str | None:
        """UZ: Tokenni yangilaydi (eskisi bekor bo'ladi).
        RU: Заменяет токен (старый становится недействительным).
        EN: Replaces the token (the old one stops working).
        """
        result = await self.bot.call("replaceManagedBotToken", **self._params(bot_id, params))
        return _token_from_result(result)

    async def access_settings(self, bot_id: int | None = None, **params: Any) -> Any:
        return await self.bot.call("getManagedBotAccessSettings", **self._params(bot_id, params))

    async def set_access_settings(self, bot_id: int | None = None, **params: Any) -> Any:
        return await self.bot.call("setManagedBotAccessSettings", **self._params(bot_id, params))

    async def save_prepared_button(self, **params: Any) -> Any:
        """UZ: `savePreparedKeyboardButton` — Mini App uchun tayyor tugma.
        RU: `savePreparedKeyboardButton` — подготовленная кнопка для Mini App.
        EN: `savePreparedKeyboardButton` — a prepared button for a Mini App.
        """
        return await self.bot.call("savePreparedKeyboardButton", **params)


class BotFarm:
    """UZ: Bir nechta "bola" botni bitta jarayonda ishga tushiradi.
    RU: Запускает несколько "дочерних" ботов в одном процессе.
    EN: Runs several child bots in one process.

    UZ: Har bir bot alohida `Zafather` nusxasi, lekin handlerlar bitta routerdan:
    kod bir marta yoziladi. Umumiy storage bot ID bo'yicha ajratiladi.
    RU: Каждый бот — отдельный экземпляр `Zafather`, но handlers берутся из одного
    router: код пишется один раз. Общее хранилище разделяется по ID бота.
    EN: Each bot is a separate `Zafather` instance sharing one router, so the code is
    written once. A shared storage is partitioned by bot ID.
    """

    def __init__(
        self,
        router: Router,
        *,
        parse_mode: str | None = "HTML",
        storage: BaseStorage | None = None,
        on_start: Callable[[Zafather], Any] | None = None,
        api_url: str | TelegramAPIServer = PRODUCTION,
    ) -> None:
        self.router = router
        self.parse_mode = parse_mode
        self.storage = storage
        self.on_start = on_start
        self.api_url = api_url
        self.bots: dict[int, Zafather] = {}
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._closed = asyncio.Event()

    def _create_app(self, token: str, **kwargs: Any) -> Zafather:
        from .app import Zafather

        app = Zafather(
            token,
            parse_mode=kwargs.pop("parse_mode", self.parse_mode),
            storage=kwargs.pop("storage", self.storage),
            api_url=kwargs.pop("api_url", self.api_url),
            name=kwargs.pop("name", f"farm:{bot_id_from_token(token)}"),
            close_storage=kwargs.pop("close_storage", False),
            **kwargs,
        )
        app.include(self.router)
        app.data["farm"] = self
        return app

    async def add(self, token: str, **kwargs: Any) -> Zafather:
        """UZ: Botni fermaga qo'shib, polling'ni boshlaydi. RU: Добавляет бота и запускает polling.
        EN: Adds a bot to the farm and starts polling.
        """
        bot_id = bot_id_from_token(token)
        if bot_id in self.bots:
            log.info("Bot %s is already running", bot_id)
            return self.bots[bot_id]
        app = self._create_app(token, **kwargs)
        if self.on_start is not None:
            result = self.on_start(app)
            if asyncio.iscoroutine(result):
                await result
        self.bots[bot_id] = app
        task = asyncio.create_task(app.start_polling(skip_updates=True))
        self._tasks[bot_id] = task
        task.add_done_callback(functools.partial(self._on_finished, bot_id))
        log.info("Bot %s joined the farm (total: %s)", bot_id, len(self.bots))
        return app

    def _on_finished(self, bot_id: int, task: asyncio.Task[None]) -> None:
        if self._tasks.get(bot_id) is task:
            del self._tasks[bot_id]
            self.bots.pop(bot_id, None)
        if not task.cancelled() and task.exception() is not None:
            log.error("Bot %s stopped with an error", bot_id, exc_info=task.exception())

    async def remove(self, token_or_id: str | int) -> bool:
        """UZ: Botni to'xtatib, fermadan chiqaradi. RU: Останавливает бота и убирает из фермы.
        EN: Stops a bot and removes it from the farm.
        """
        bot_id = bot_id_from_token(str(token_or_id))
        app = self.bots.pop(bot_id, None)
        task = self._tasks.pop(bot_id, None)
        if app is None:
            return False
        await app.stop()
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(task, timeout=35)
        log.info("Bot %s left the farm", bot_id)
        return True

    async def broadcast(self, chat_ids: Iterable[int | str], text: str, **kwargs: Any) -> int:
        """UZ: Fermadagi har bir botdan xabar yuboradi; muvaffaqiyatlilar sonini qaytaradi.
        RU: Отправляет сообщение от каждого бота фермы; возвращает число успешных.
        EN: Sends a message from every farm bot; returns the number of successes.
        """
        targets = list(chat_ids)
        sent = 0
        for app in list(self.bots.values()):
            for chat_id in targets:
                try:
                    await app.bot.call("sendMessage", chat_id=chat_id, text=text, **kwargs)
                except Exception as exc:
                    log.warning("Broadcast from bot %s failed: %s", app.bot.id, exc)
                else:
                    sent += 1
        return sent

    async def run_forever(self) -> None:
        """UZ: `stop_all()` chaqirilguncha kutadi. RU: Ждёт до вызова `stop_all()`.
        EN: Waits until `stop_all()` is called.
        """
        await self._closed.wait()

    async def stop_all(self) -> None:
        for bot_id in list(self.bots):
            await self.remove(bot_id)
        self._closed.set()

    @property
    def count(self) -> int:
        return len(self.bots)

    def __contains__(self, token_or_id: object) -> bool:
        try:
            return bot_id_from_token(str(token_or_id)) in self.bots
        except ValueError:
            return False

    def __len__(self) -> int:
        return len(self.bots)

    def __repr__(self) -> str:
        return f"<BotFarm bots={len(self.bots)}>"


__all__ = ["BotFarm", "ManagedBots", "bot_id_from_token"]
