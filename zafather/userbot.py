"""UZ: MTProto userbot adapteri.
RU: Адаптер userbot на базе MTProto.
EN: MTProto userbot adapter.
"""
from __future__ import annotations

import inspect
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

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session: str = "zafather_user",
        client: Any = None,
        events_module: Any = None,
        **kwargs: Any,
    ) -> None:
        if not isinstance(api_id, int) or api_id <= 0:
            raise ValueError("api_id musbat integer bo'lishi kerak")
        if not isinstance(api_hash, str) or not api_hash.strip():
            raise ValueError("api_hash bo'sh bo'lmasligi kerak")

        if client is None or events_module is None:
            try:
                from telethon import TelegramClient, events
            except ImportError as exc:
                raise RuntimeError(
                    "UserBot support requires the optional dependency 'telethon'. "
                    "Install with: pip install zafather[userbot]"
                ) from exc
            if client is None:
                client = TelegramClient(session, api_id, api_hash, **kwargs)
            if events_module is None:
                events_module = events

        self.client = client
        self.events = events_module

    def on(self, event_builder: Any) -> Callable:
        """UZ/RU/EN: Telethon event builder uchun umumiy decorator."""
        return self.client.on(event_builder)

    def on_message(self, *args: Any, **kwargs: Any) -> Callable:
        """UZ/RU/EN: Yangi xabarlar uchun handler decoratori."""
        return self.client.on(self.events.NewMessage(*args, **kwargs))

    def on_callback(self, *args: Any, **kwargs: Any) -> Callable:
        """UZ/RU/EN: Callback query lar uchun handler decoratori."""
        return self.client.on(self.events.CallbackQuery(*args, **kwargs))

    def on_new_message(self, *args: Any, **kwargs: Any) -> Callable:
        """UZ/RU/EN: `on_message()` ning aniq nomlangan aliasi."""
        return self.on_message(*args, **kwargs)

    def on_callback_query(self, *args: Any, **kwargs: Any) -> Callable:
        """UZ/RU/EN: `on_callback()` ning aniq nomlangan aliasi."""
        return self.on_callback(*args, **kwargs)

    async def start(self, phone: Optional[str] = None, **kwargs: Any) -> Any:
        """UZ/RU/EN: Userbot sessiyasini ishga tushiradi."""
        if phone is None:
            return await self.client.start(**kwargs)
        return await self.client.start(phone=phone, **kwargs)

    async def run_until_disconnected(self) -> Any:
        """UZ/RU/EN: Userbot uzilguncha event loop'ni kutadi."""
        return await self.client.run_until_disconnected()

    async def run(self) -> Any:
        """UZ/RU/EN: Userbotni ishga tushirib, uzilguncha kutadi."""
        await self.start()
        return await self.run_until_disconnected()

    async def disconnect(self) -> None:
        """UZ/RU/EN: Userbot sessiyasini yopadi."""
        await self.client.disconnect()

    async def send_message(self, entity: Any, message: Any, **kwargs: Any) -> Any:
        """UZ/RU/EN: User nomidan xabar yuboradi."""
        return await self.client.send_message(entity, message, **kwargs)

    async def call(self, method: Any, *args: Any, **kwargs: Any) -> Any:
        """UZ: Istalgan Telethon client metodini nomi yoki callable orqali chaqiradi.
        RU: Вызывает любой метод клиента Telethon по имени или callable.
        EN: Calls any Telethon client method by name or callable.
        """
        target = getattr(self.client, method) if isinstance(method, str) else method
        result = target(*args, **kwargs)
        return await result if inspect.isawaitable(result) else result

    async def request(self, method: Any, *args: Any, **kwargs: Any) -> Any:
        """UZ/RU/EN: `call()` ning request-uslubidagi aliasi."""
        return await self.call(method, *args, **kwargs)

    async def invoke(self, request: Any) -> Any:
        """UZ: Telethon raw MTProto request obyektini bajaradi.
        RU: Выполняет сырой объект MTProto-запроса Telethon.
        EN: Executes a raw Telethon MTProto request object.
        """
        result = self.client(request)
        return await result if inspect.isawaitable(result) else result

    def add_handler(self, callback: Callable, event_builder: Any) -> Any:
        """UZ/RU/EN: Tayyor handlerni clientga qo'shadi."""
        return self.client.add_event_handler(callback, event_builder)

    def remove_handler(self, callback: Callable, event_builder: Any = None) -> Any:
        """UZ/RU/EN: Handlerni clientdan olib tashlaydi."""
        return self.client.remove_event_handler(callback, event_builder)

    async def __aenter__(self) -> "UserBot":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        result = self.disconnect()
        if inspect.isawaitable(result):
            await result

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.client, name)


__all__ = ["UserBot"]
