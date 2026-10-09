"""UZ: `UserBot` — userbot yozish uchun qulay fasad (qayta urinish va qayta ulanish bilan).
RU: `UserBot` — удобный фасад для userbot (с повторами и переподключением).
EN: `UserBot` — a convenient userbot facade (with retries and reconnects).

    userbot = UserBot(API_ID, API_HASH, session="me")

    @userbot.on_message(pattern=r"^\\.ping$", outgoing=True)
    async def ping(event):
        await event.edit("pong")

    asyncio.run(userbot.run())
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import Any, TypeVar

from .mtproto import events as default_events
from .mtproto.client import MTProtoClient
from .mtproto.errors import FloodWaitError

log = logging.getLogger("zafather.userbot")

ResultT = TypeVar("ResultT")
CallbackT = TypeVar("CallbackT", bound=Callable[..., Any])


def is_flood_wait(error: BaseException) -> bool:
    """UZ: FLOOD_WAIT xatosimi (Telethon/Pyrogram xatolari ham nomidan taniladi).
    RU: Ошибка ли это FLOOD_WAIT (ошибки Telethon/Pyrogram распознаются по имени).
    EN: Whether this is a FLOOD_WAIT error (Telethon/Pyrogram errors are matched by name).
    """
    if isinstance(error, FloodWaitError):
        return True
    return any("FloodWait" in cls.__name__ for cls in type(error).__mro__)


def flood_wait_seconds(error: BaseException) -> float | None:
    """UZ: FLOOD_WAIT xatosidagi kutish vaqti (`seconds` yoki `value`); boshqa xato — None.
    RU: Время ожидания из FLOOD_WAIT (`seconds` или `value`); для других ошибок — None.
    EN: The wait time of a FLOOD_WAIT error (`seconds` or `value`); None for other errors.
    """
    if not is_flood_wait(error):
        return None
    for attribute in ("seconds", "value"):
        seconds = getattr(error, attribute, None)
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
            return float(seconds)
    return None


def is_connection_error(error: BaseException) -> bool:
    """UZ: Ulanish uzilishimi. RU: Обрыв ли это соединения. EN: Whether the connection dropped."""
    return isinstance(error, (ConnectionError, OSError, asyncio.TimeoutError))


async def _resolve(result: Awaitable[ResultT] | ResultT) -> ResultT:
    if inspect.isawaitable(result):
        return await result
    return result


class UserBot:
    """UZ: `MTProtoClient` (yoki unga mos boshqa mijoz) ustidagi fasad: FLOOD_WAIT'da
    kutadi, uzilishda qayta ulanadi, handlerlarni qulay ro'yxatga oladi.
    RU: Фасад над `MTProtoClient` (или совместимым клиентом): ждёт при FLOOD_WAIT,
    переподключается при обрыве, удобно регистрирует обработчики.
    EN: A facade over `MTProtoClient` (or a compatible client): sleeps on FLOOD_WAIT,
    reconnects on drops and registers handlers conveniently.

    UZ: `retry_delay` — davomiyligi noma'lum FLOOD_WAIT uchun kutish. Ulanish uzilganda
    qayta ulanishlar orasidagi kutish `reconnect_delay * backoff ** (n - 1)`.
    RU: `retry_delay` — ожидание для FLOOD_WAIT без длительности. Между переподключениями
    ждём `reconnect_delay * backoff ** (n - 1)`.
    EN: `retry_delay` is the wait used for a FLOOD_WAIT without a duration. Reconnects wait
    `reconnect_delay * backoff ** (n - 1)`.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session: Any = "zafather_user",
        client: Any = None,
        events_module: ModuleType | Any = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        max_reconnects: int = 5,
        reconnect_delay: float = 2.0,
        backoff: float = 2.0,
        **client_options: Any,
    ) -> None:
        if not isinstance(api_id, int) or isinstance(api_id, bool) or api_id <= 0:
            raise ValueError("api_id must be a positive integer")
        if not isinstance(api_hash, str) or not api_hash.strip():
            raise ValueError("api_hash must not be empty")
        if max_retries < 0 or max_reconnects < 0:
            raise ValueError("max_retries and max_reconnects must not be negative")
        if retry_delay < 0 or reconnect_delay < 0 or backoff < 1:
            raise ValueError("Delays must not be negative and backoff must be at least 1")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_reconnects = max_reconnects
        self.reconnect_delay = reconnect_delay
        self.backoff = backoff
        self.client = client or MTProtoClient(api_id, api_hash, session=session, **client_options)
        self.events = events_module or default_events

    # --- UZ: qayta urinish / RU: повторы / EN: retries -----------------------------------------
    def _reconnect_delay(self, reconnects: int) -> float:
        return float(self.reconnect_delay * self.backoff ** (reconnects - 1))

    async def _reconnect(self) -> None:
        connect = getattr(self.client, "connect", None)
        if connect is None:
            return
        try:
            await _resolve(connect())
        except Exception as error:
            if not is_connection_error(error):
                raise
            log.warning("Reconnect failed: %s", error)

    async def _execute(
        self,
        operation: Callable[[], Awaitable[ResultT] | ResultT],
        *,
        repeat_on_disconnect: bool = True,
    ) -> ResultT:
        """UZ: FLOOD_WAIT'da kutib qaytaradi; uzilishda (ruxsat bo'lsa) qayta ulanib takrorlaydi.
        RU: При FLOOD_WAIT ждёт и повторяет; при обрыве (если разрешено) переподключается.
        EN: Sleeps and repeats on FLOOD_WAIT; reconnects and repeats on drops (if allowed).
        """
        retries = reconnects = 0
        while True:
            try:
                return await _resolve(operation())
            except Exception as error:
                if is_flood_wait(error):
                    if retries >= self.max_retries:
                        raise
                    retries += 1
                    wait = flood_wait_seconds(error)
                    wait = self.retry_delay if wait is None else wait
                    log.warning("FLOOD_WAIT: sleeping %ss (%s/%s)", wait, retries, self.max_retries)
                    await asyncio.sleep(wait)
                    continue
                if not (repeat_on_disconnect and is_connection_error(error)):
                    raise
                if reconnects >= self.max_reconnects:
                    raise
                reconnects += 1
                log.warning("Reconnecting (%s/%s): %s", reconnects, self.max_reconnects, error)
                await asyncio.sleep(self._reconnect_delay(reconnects))
                await self._reconnect()

    # --- UZ: handlerlar / RU: обработчики / EN: handlers ---------------------------------------
    def on(self, event_builder: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Istalgan hodisa uchun dekorator. RU: Декоратор для любого события.
        EN: A decorator for any event builder.
        """
        return self.client.on(event_builder)

    def on_message(self, *args: Any, **kwargs: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Yangi xabar handleri. RU: Обработчик новых сообщений. EN: A new message handler."""
        return self.on(self.events.NewMessage(*args, **kwargs))

    def on_edited(self, *args: Any, **kwargs: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Tahrirlangan xabar. RU: Отредактированное сообщение. EN: An edited message."""
        return self.on(self.events.MessageEdited(*args, **kwargs))

    def on_deleted(self, *args: Any, **kwargs: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: O'chirilgan xabarlar. RU: Удалённые сообщения. EN: Deleted messages."""
        return self.on(self.events.MessageDeleted(*args, **kwargs))

    def on_callback(self, *args: Any, **kwargs: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Inline tugma bosilishi. RU: Нажатие inline-кнопки. EN: An inline button press."""
        return self.on(self.events.CallbackQuery(*args, **kwargs))

    on_new_message = on_message
    on_callback_query = on_callback

    def add_handler(self, callback: Callable[..., Any], event_builder: Any = None) -> Any:
        """UZ: Handlerni dekoratorsiz qo'shadi. RU: Добавляет обработчик без декоратора.
        EN: Adds a handler without a decorator.
        """
        return self.client.add_event_handler(callback, event_builder)

    def remove_handler(self, callback: Callable[..., Any], event_builder: Any = None) -> Any:
        """UZ: Handlerni o'chiradi. RU: Удаляет обработчик. EN: Removes a handler."""
        return self.client.remove_event_handler(callback, event_builder)

    # --- UZ: hayot sikli / RU: жизненный цикл / EN: lifecycle --------------------------------
    async def start(self, phone: Any = None, **kwargs: Any) -> Any:
        """UZ: Ulanadi va kiradi (`MTProtoClient.start` argumentlari).
        RU: Подключается и входит (аргументы `MTProtoClient.start`).
        EN: Connects and logs in (accepts the `MTProtoClient.start` arguments).
        """
        if phone is not None:
            kwargs["phone"] = phone
        return await self._execute(lambda: self.client.start(**kwargs))

    async def run_until_disconnected(self) -> Any:
        """UZ: Uzilguncha ishlaydi; ulanish yo'qolsa qayta ulanadi.
        RU: Работает до отключения; при потере соединения переподключается.
        EN: Runs until disconnected, reconnecting when the connection is lost.
        """
        return await self._execute(self.client.run_until_disconnected)

    async def run(self) -> Any:
        """UZ: Kirib, uzilguncha ishlaydi. RU: Входит и работает до отключения.
        EN: Logs in and runs until disconnected.
        """
        await self.start()
        return await self.run_until_disconnected()

    async def disconnect(self) -> None:
        """UZ: Ulanishni yopadi. RU: Закрывает соединение. EN: Closes the connection."""
        await _resolve(self.client.disconnect())

    # --- UZ: so'rovlar / RU: запросы / EN: requests --------------------------------------------
    async def send_message(self, entity: Any, message: Any, **kwargs: Any) -> Any:
        """UZ: Xabar yuboradi. Uzilishda takrorlanmaydi: dublikat bo'lmasligi uchun mijoz
        so'rovni o'zi (o'sha `random_id` bilan) qayta yuboradi.
        RU: Отправляет сообщение. При обрыве не повторяется: клиент сам переотправляет
        запрос (с тем же `random_id`), чтобы не было дублей.
        EN: Sends a message. It is not repeated after a drop: the client itself resends the
        request (with the same `random_id`) so no duplicates appear.
        """
        return await self._execute(
            lambda: self.client.send_message(entity, message, **kwargs),
            repeat_on_disconnect=False,
        )

    async def call(self, method: str | Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """UZ: Mijoz metodini nomi yoki o'zi bilan chaqiradi (qayta urinish bilan).
        Faqat qayta bajarish xavfsiz bo'lgan metodlar uchun ishlating.
        RU: Вызывает метод клиента по имени или напрямую (с повторами).
        Используйте для методов, которые безопасно повторять.
        EN: Calls a client method by name or reference (with retries).
        Use it for methods that are safe to repeat.
        """
        target = getattr(self.client, method) if isinstance(method, str) else method
        return await self._execute(lambda: target(*args, **kwargs))

    request = call

    async def invoke(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        """UZ: Xom TL so'rovi; o'sha obyekt qayta yuboriladi, shuning uchun `random_id`
        saqlanadi. RU: Сырой TL-запрос; повторно отправляется тот же объект, поэтому
        `random_id` сохраняется. EN: A raw TL request; the same object is resent, so its
        `random_id` is preserved.
        """
        invoke = getattr(self.client, "invoke", None) or self.client
        return await self._execute(lambda: invoke(request, *args, **kwargs))

    async def __aenter__(self) -> UserBot:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.disconnect()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_") or name == "client":
            raise AttributeError(name)
        return getattr(self.client, name)


__all__ = ["UserBot", "flood_wait_seconds", "is_connection_error", "is_flood_wait"]
