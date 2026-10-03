"""UZ: Telegram Bot API klienti.
RU: Клиент Telegram Bot API.
EN: Telegram Bot API client.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import IO, TYPE_CHECKING, Any, Union

from .api import PRODUCTION, AiohttpSession, BaseSession, PayloadBuilder, RetryPolicy
from .api.server import TelegramAPIServer
from .exceptions import (
    NetworkError,
    RetryAfter,
    ServerError,
    TelegramAPIError,
    TelegramError,
    api_error_from_response,
)
from .files import InputFile
from .payments import StarsAPI
from .types import TelegramObject, User, wrap_result

if TYPE_CHECKING:
    from .rich import RichStream

log = logging.getLogger("zafather.bot")

_TOKEN_PATTERN = re.compile(r"^\d+:\S+$")

Destination = Union[str, "os.PathLike[str]", IO[bytes]]


def to_camel_case(name: str) -> str:
    """UZ: snake_case nomni camelCase ga o'giradi (`send_message` -> `sendMessage`).
    RU: Преобразует имя из snake_case в camelCase.
    EN: Converts a snake_case name to camelCase.
    """
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


class Bot:
    """UZ: Telegram Bot API bilan muloqot qiladigan klient.
    RU: Клиент для работы с Telegram Bot API.
    EN: Client that talks to the Telegram Bot API.

    UZ: Har qanday API metodini snake_case ko'rinishida chaqirish mumkin; natija
    mos modelga o'raladi.
    RU: Любой метод API можно вызвать в snake_case; результат оборачивается в
    подходящую модель.
    EN: Any API method can be called in snake_case; the result is wrapped into the
    matching model::

        await bot.send_message(chat_id=1, text="salom")   # -> sendMessage
        await bot.get_chat_member(chat_id=1, user_id=2)   # -> getChatMember

    UZ: `session`, `retry` va `api_url` orqali transport, qayta urinish va server
    almashtiriladi (masalan, testlarda soxta sessiya).
    RU: Через `session`, `retry` и `api_url` заменяются транспорт, повторы и сервер
    (например, фейковая сессия в тестах).
    EN: `session`, `retry` and `api_url` replace the transport, retry policy and
    server (for example a fake session in tests).
    """

    def __init__(
        self,
        token: str,
        parse_mode: str | None = None,
        api_url: str | TelegramAPIServer = PRODUCTION,
        timeout: float = 60.0,
        *,
        session: BaseSession | None = None,
        retry: RetryPolicy | None = None,
    ) -> None:
        if not isinstance(token, str) or not _TOKEN_PATTERN.match(token):
            raise ValueError("Invalid bot token: expected '<id>:<secret>' from @BotFather")
        self.token = token
        self.id = int(token.split(":", 1)[0])
        self.server = (
            api_url if isinstance(api_url, TelegramAPIServer) else TelegramAPIServer(api_url)
        )
        self.timeout = float(timeout)
        self.retry = retry or RetryPolicy()
        self.session: BaseSession = session or AiohttpSession()
        self._owns_session = session is None
        self._payloads = PayloadBuilder(parse_mode)
        self._me: User | None = None
        self.stars = StarsAPI(self)

    # --- UZ: sozlamalar / RU: настройки / EN: settings -----------------------------------
    @property
    def parse_mode(self) -> str | None:
        return self._payloads.default_parse_mode

    @parse_mode.setter
    def parse_mode(self, value: str | None) -> None:
        self._payloads.default_parse_mode = value

    @property
    def api_url(self) -> str:
        return self.server.base

    # --- UZ: so'rovlar / RU: запросы / EN: requests ---------------------------------------
    def _request_timeout(self, method: str, params: dict[str, Any]) -> float:
        if method == "getUpdates":
            return self.timeout + float(params.get("timeout") or 0)
        return self.timeout

    def _api_error_delay(self, method: str, error: TelegramAPIError, attempt: int) -> float | None:
        if not self.retry.can_retry(attempt):
            return None
        if isinstance(error, RetryAfter):
            retry_after = error.retry_after
            return self.retry.flood_delay(1 if retry_after is None else retry_after)
        if (
            isinstance(error, ServerError)
            and self.retry.retry_server_errors
            and self.retry.allows_resend(method, request_sent=True)
        ):
            return self.retry.backoff(attempt)
        return None

    def _network_error_delay(self, method: str, error: NetworkError, attempt: int) -> float | None:
        if self.retry.can_retry(attempt) and self.retry.allows_resend(
            method, request_sent=error.request_sent
        ):
            return self.retry.backoff(attempt)
        return None

    async def call(self, method: str, **params: Any) -> Any:
        """UZ: API metodini chaqirib, xom natijani qaytaradi.
        RU: Вызывает метод API и возвращает сырой результат.
        EN: Calls an API method and returns the raw result.

        UZ: Xatoda `TelegramAPIError` (yoki uning vorisi) yoki `NetworkError` ko'taradi.
        RU: При ошибке выбрасывает `TelegramAPIError` (или наследника) либо `NetworkError`.
        EN: Raises `TelegramAPIError` (or a subclass) or `NetworkError` on failure.
        """
        payload = self._payloads.build(method, params)
        url = self.server.method_url(self.token, method)
        timeout = self._request_timeout(method, params)
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self.session.request(url, payload, timeout=timeout)
            except NetworkError as error:
                delay = self._network_error_delay(method, error, attempt)
                if delay is None:
                    raise
                log.warning("%s: network error (%s), retrying in %.1fs", method, error, delay)
                await asyncio.sleep(delay)
                continue
            if response.get("ok"):
                return response.get("result")
            api_error = api_error_from_response(method, response)
            delay = self._api_error_delay(method, api_error, attempt)
            if delay is None:
                raise api_error
            log.warning("%s: %s, retrying in %.1fs", method, api_error.description, delay)
            await asyncio.sleep(delay)

    async def request(self, method: str, **params: Any) -> Any:
        """UZ: API metodini chaqirib, natijani modelga o'raydi.
        RU: Вызывает метод API и оборачивает результат в модель.
        EN: Calls an API method and wraps the result into a model.
        """
        return wrap_result(await self.call(method, **params), self)

    def __getattr__(self, name: str) -> Callable[..., Awaitable[Any]]:
        if name.startswith("_"):
            raise AttributeError(name)
        method = to_camel_case(name)

        async def api_method(**params: Any) -> Any:
            return await self.request(method, **params)

        api_method.__name__ = name
        api_method.__qualname__ = f"Bot.{name}"
        return api_method

    # --- UZ: yordamchilar / RU: помощники / EN: helpers -----------------------------------
    async def me(self) -> User:
        """UZ: `getMe` natijasi (keshlanadi). RU: Результат `getMe` (кешируется).
        EN: The `getMe` result (cached).
        """
        if self._me is None:
            self._me = User(await self.call("getMe"), self)
        return self._me

    def file_url(self, file_path: str) -> str:
        return self.server.file_url(self.token, file_path)

    async def _file_path(self, file: str | TelegramObject) -> str:
        if isinstance(file, TelegramObject):
            if file.file_path:
                return str(file.file_path)
            file_id = file.file_id
        else:
            file_id = file
        result = await self.call("getFile", file_id=file_id)
        return str(result["file_path"])

    async def download(
        self,
        file: str | TelegramObject,
        destination: Destination | None = None,
        *,
        chunk_size: int = 65536,
        timeout: float | None = None,
    ) -> bytes | None:
        """UZ: Faylni yuklab oladi. `destination` berilmasa baytlar qaytariladi.
        RU: Скачивает файл. Без `destination` возвращает байты.
        EN: Downloads a file. Without `destination` the bytes are returned.

        UZ: `file` — `file_id` yoki `File`/`PhotoSize`/`Document` kabi obyekt.
        RU: `file` — `file_id` или объект вроде `File`/`PhotoSize`/`Document`.
        EN: `file` is a `file_id` or an object such as `File`/`PhotoSize`/`Document`.
        """
        file_path = await self._file_path(file)
        if self.server.is_local:
            return await asyncio.to_thread(_copy_local_file, file_path, destination)
        chunks = self.session.stream(
            self.file_url(file_path), timeout=timeout or self.timeout, chunk_size=chunk_size
        )
        if destination is None:
            buffer = bytearray()
            async for chunk in chunks:
                buffer += chunk
            return bytes(buffer)
        if isinstance(destination, (str, os.PathLike)):
            stream = await asyncio.to_thread(open, destination, "wb")
            try:
                async for chunk in chunks:
                    await asyncio.to_thread(stream.write, chunk)
            finally:
                await asyncio.to_thread(stream.close)
        else:
            async for chunk in chunks:
                destination.write(chunk)
        return None

    async def send_rich(self, chat_id: int | str, rich: Any, **kwargs: Any) -> Any:
        """UZ: Rich xabar yuboradi (Bot API 10.1+). RU: Отправляет rich-сообщение.
        EN: Sends a rich message (Bot API 10.1+).
        """
        return await self.request("sendRichMessage", chat_id=chat_id, rich_message=rich, **kwargs)

    def stream_rich(self, chat_id: int | str, **kwargs: Any) -> RichStream:
        """UZ: AI javobini oqim bilan yuborish uchun `RichStream` yaratadi.
        RU: Создаёт `RichStream` для потоковой отправки ответа ИИ.
        EN: Creates a `RichStream` that streams an AI answer.
        """
        from .rich import RichStream

        return RichStream(self, chat_id, **kwargs)

    async def answer_pre_checkout_query(
        self, pre_checkout_query_id: str, ok: bool = True, **kwargs: Any
    ) -> Any:
        return await self.request(
            "answerPreCheckoutQuery", pre_checkout_query_id=pre_checkout_query_id, ok=ok, **kwargs
        )

    # --- UZ: hayot sikli / RU: жизненный цикл / EN: lifecycle ----------------------------
    async def close(self) -> None:
        """UZ: O'zi yaratgan HTTP sessiyani yopadi.
        RU: Закрывает HTTP-сессию, если создал её сам.
        EN: Closes the HTTP session if this client created it.
        """
        if self._owns_session:
            await self.session.close()

    async def __aenter__(self) -> Bot:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"<Bot id={self.id}>"


def _copy_local_file(file_path: str, destination: Destination | None) -> bytes | None:
    if destination is None:
        with open(file_path, "rb") as source:
            return source.read()
    if isinstance(destination, (str, os.PathLike)):
        shutil.copyfile(file_path, destination)
        return None
    with open(file_path, "rb") as source:
        shutil.copyfileobj(source, destination)
    return None


__all__ = [
    "Bot",
    "InputFile",
    "NetworkError",
    "TelegramAPIError",
    "TelegramError",
    "to_camel_case",
]
