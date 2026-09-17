"""UZ: MTProto userbot adapteri.
RU: Адаптер userbot на базе MTProto.
EN: MTProto userbot adapter.
"""
from __future__ import annotations

from typing import Any, Callable, Optional


class UserBot:
    """UZ: Telethon asosidagi userbot klienti.
    RU: Клиент userbot на базе Telethon.
    EN: Telethon-based userbot client.

    Telethon majburiy dependency emas. O'rnatish / Установка / Installation::

        pip install zafather[userbot]

    Misol / Пример / Example::

        userbot = UserBot(12345, "api-hash", session="my-account")

        @userbot.on_message(pattern="/hello")
        async def hello(event):
            await event.respond("Salom!")

        await userbot.start()
        await userbot.run_until_disconnected()
    """

    def __init__(self, api_id: int, api_hash: str, session: str = "zafather_user", **kwargs: Any) -> None:
        try:
            from telethon import TelegramClient, events
        except ImportError as exc:
            raise RuntimeError(
                "UserBot support requires the optional dependency 'telethon'. "
                "Install with: pip install zafather[userbot]"
            ) from exc

        self.client = TelegramClient(session, api_id, api_hash, **kwargs)
        self.events = events

    def on(self, event_builder: Any) -> Callable:
        """UZ/RU/EN: Telethon event builder uchun umumiy decorator."""
        return self.client.on(event_builder)

    def on_message(self, *args: Any, **kwargs: Any) -> Callable:
        """UZ/RU/EN: Yangi xabarlar uchun handler decoratori."""
        return self.client.on(self.events.NewMessage(*args, **kwargs))

    def on_callback(self, *args: Any, **kwargs: Any) -> Callable:
        """UZ/RU/EN: Callback query lar uchun handler decoratori."""
        return self.client.on(self.events.CallbackQuery(*args, **kwargs))

    async def start(self, phone: Optional[str] = None, **kwargs: Any) -> Any:
        """UZ/RU/EN: Userbot sessiyasini ishga tushiradi."""
        if phone is None:
            return await self.client.start(**kwargs)
        return await self.client.start(phone=phone, **kwargs)

    async def run_until_disconnected(self) -> Any:
        """UZ/RU/EN: Userbot uzilguncha event loop'ni kutadi."""
        return await self.client.run_until_disconnected()

    async def disconnect(self) -> None:
        """UZ/RU/EN: Userbot sessiyasini yopadi."""
        await self.client.disconnect()

    async def send_message(self, entity: Any, message: Any, **kwargs: Any) -> Any:
        """UZ/RU/EN: User nomidan xabar yuboradi."""
        return await self.client.send_message(entity, message, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.client, name)


__all__ = ["UserBot"]
