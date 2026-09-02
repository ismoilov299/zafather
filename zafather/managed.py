"""Zafather — **Managed Bots**: bot yaratadigan botlar (Bot API 9.6+).

Ish tartibi:

1. @BotFather'da manager botga *Bot Management Mode* yoqiladi.
2. Foydalanuvchiga havola beriladi: ``https://t.me/newbot/<manager>/<taklif_username>``
   yoki `ReplyKeyboard.request_bot()` tugmasi ko'rsatiladi.
3. Foydalanuvchi tasdiqlaydi → botga `managed_bot` update va
   `managed_bot_created` xizmat xabari keladi.
4. Manager `getManagedBotToken` orqali yangi botning tokenini oladi.
5. `BotFarm` o'sha token bilan yangi Zafather nusxasini ishga tushiradi.

::

    farm = BotFarm(child_router)

    @bot.managed_bot()
    async def on_new_bot(event, bot):
        token = await ManagedBots(bot).token(event.bot.id)
        await farm.add(token)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional
from urllib.parse import quote

log = logging.getLogger("zafather.managed")


class ManagedBots:
    """`getManagedBotToken` / `replaceManagedBotToken` ustidagi qulay qobiq.

    Metod parametrlari rasmiy hujjat bo'yicha uzatiladi — qo'shimcha
    kalitlarni `**params` orqali berish mumkin.
    """

    def __init__(self, bot) -> None:
        self.bot = bot

    @staticmethod
    def create_link(
        manager_username: str,
        suggested_username: str,
        name: Optional[str] = None,
    ) -> str:
        """Bot yaratish havolasi: ``t.me/newbot/<manager>/<username>?name=<nom>``."""
        manager = manager_username.lstrip("@")
        username = suggested_username.lstrip("@")
        url = f"https://t.me/newbot/{manager}/{username}"
        if name:
            url += f"?name={quote(name)}"
        return url

    async def token(self, bot_id: int = None, **params) -> Optional[str]:
        """Boshqariladigan botning tokenini oladi."""
        if bot_id is not None:
            params.setdefault("bot_id", bot_id)
        result = await self.bot.call("getManagedBotToken", **params)
        if isinstance(result, dict):
            return result.get("token") or result.get("access_token")
        return result

    async def replace_token(self, bot_id: int = None, **params) -> Optional[str]:
        """Tokenni yangilaydi (eskisi bekor bo'ladi)."""
        if bot_id is not None:
            params.setdefault("bot_id", bot_id)
        result = await self.bot.call("replaceManagedBotToken", **params)
        if isinstance(result, dict):
            return result.get("token") or result.get("access_token")
        return result

    async def access_settings(self, bot_id: int = None, **params):
        """`getManagedBotAccessSettings` (Bot API 10.0)."""
        if bot_id is not None:
            params.setdefault("bot_id", bot_id)
        return await self.bot.call("getManagedBotAccessSettings", **params)

    async def set_access_settings(self, bot_id: int = None, **params):
        """`setManagedBotAccessSettings` (Bot API 10.0)."""
        if bot_id is not None:
            params.setdefault("bot_id", bot_id)
        return await self.bot.call("setManagedBotAccessSettings", **params)

    async def save_prepared_button(self, **params):
        """`savePreparedKeyboardButton` — Mini App'dan bot/chat/user so'rash."""
        return await self.bot.call("savePreparedKeyboardButton", **params)


class BotFarm:
    """Bir vaqtda ko'p botni (yaratilgan "bola" botlarni) ishga tushiradi.

    Har bir bot alohida `Zafather` nusxasi bo'ladi, lekin handlerlar bitta
    `Router`dan olinadi — ya'ni kodni bir marta yozasiz::

        child = Router("child")

        @child.command("start")
        async def start(m): await m.answer("Men yangi botman!")

        farm = BotFarm(child, storage=MemoryStorage())
        await farm.add(token)
        await farm.run_forever()
    """

    def __init__(
        self,
        router,
        *,
        parse_mode: str = "HTML",
        storage=None,
        on_start: Optional[Callable] = None,
        api_url: str = "https://api.telegram.org",
    ) -> None:
        self.router = router
        self.parse_mode = parse_mode
        self.storage = storage
        self.on_start = on_start
        self.api_url = api_url
        self.bots: Dict[str, Any] = {}
        self._tasks: Dict[str, asyncio.Task] = {}

    def _key(self, token: str) -> str:
        return token.split(":")[0]

    async def add(self, token: str, **kwargs) -> Any:
        """Yangi botni fermaga qo'shadi va polling'ni boshlaydi."""
        from .app import Zafather  # aylanma importni oldini olish

        key = self._key(token)
        if key in self.bots:
            log.info("Bot %s allaqachon ishlayapti", key)
            return self.bots[key]

        app = Zafather(
            token,
            parse_mode=kwargs.pop("parse_mode", self.parse_mode),
            storage=kwargs.pop("storage", self.storage),
            api_url=self.api_url,
            name=f"farm:{key}",
            **kwargs,
        )
        app.include(self.router)
        app.data["farm"] = self
        self.bots[key] = app

        if self.on_start:
            result = self.on_start(app)
            if asyncio.iscoroutine(result):
                await result

        task = asyncio.create_task(app.start_polling(skip_updates=True, banner=False))
        self._tasks[key] = task
        task.add_done_callback(lambda t, k=key: self._tasks.pop(k, None))
        log.info("Fermaga bot qo'shildi: %s (jami: %s)", key, len(self.bots))
        return app

    async def remove(self, token_or_id: str) -> bool:
        """Botni to'xtatib, fermadan chiqaradi."""
        key = self._key(str(token_or_id))
        app = self.bots.pop(key, None)
        if app is None:
            return False
        await app.stop()
        task = self._tasks.pop(key, None)
        if task:
            task.cancel()
        log.info("Fermadan chiqarildi: %s", key)
        return True

    async def broadcast(self, chat_ids, text: str, **kwargs) -> int:
        """Ferma ichidagi barcha botlardan xabar yuborish."""
        sent = 0
        for app in list(self.bots.values()):
            for chat_id in chat_ids:
                try:
                    await app.bot.send_message(chat_id=chat_id, text=text, **kwargs)
                    sent += 1
                except Exception as exc:  # noqa: BLE001
                    log.warning("broadcast xatosi: %s", exc)
        return sent

    async def run_forever(self) -> None:
        """Ferma to'xtatilmaguncha kutib turadi."""
        while True:
            await asyncio.sleep(3600)

    async def stop_all(self) -> None:
        for key in list(self.bots):
            await self.remove(key)

    @property
    def count(self) -> int:
        return len(self.bots)

    def __repr__(self) -> str:
        return f"<BotFarm bots={len(self.bots)}>"
