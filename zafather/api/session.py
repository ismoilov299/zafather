"""UZ: HTTP sessiyalari — Bot API bilan transport darajasidagi aloqa.
RU: HTTP-сессии — транспортный уровень общения с Bot API.
EN: HTTP sessions — the transport layer that talks to the Bot API.

UZ: `Bot` faqat `BaseSession` interfeysiga tayanadi, shuning uchun testlarda yoki
boshqa HTTP kutubxonasi bilan o'z sessiyangizni berishingiz mumkin.
RU: `Bot` зависит только от интерфейса `BaseSession`, поэтому в тестах или с
другой HTTP-библиотекой можно передать собственную сессию.
EN: `Bot` depends only on the `BaseSession` interface, so tests or another HTTP
library can supply their own session.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import ExitStack
from types import TracebackType
from typing import Any

import aiohttp

from ..exceptions import NetworkError
from .request import RequestPayload


class BaseSession(ABC):
    """UZ: HTTP sessiya interfeysi.
    RU: Интерфейс HTTP-сессии.
    EN: HTTP session interface.
    """

    @abstractmethod
    async def request(self, url: str, payload: RequestPayload, *, timeout: float) -> dict[str, Any]:
        """UZ: So'rovni yuborib, Bot API JSON javobini qaytaradi.
        RU: Отправляет запрос и возвращает JSON-ответ Bot API.
        EN: Sends the request and returns the Bot API JSON response.

        UZ: Tarmoq muammosida `NetworkError` ko'taradi.
        RU: При сетевой проблеме выбрасывает `NetworkError`.
        EN: Raises `NetworkError` on transport failures.
        """

    @abstractmethod
    def stream(self, url: str, *, timeout: float, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        """UZ: Faylni bo'laklab yuklab oladi. RU: Скачивает файл по частям.
        EN: Downloads a file in chunks.
        """

    @abstractmethod
    async def close(self) -> None:
        """UZ: Resurslarni bo'shatadi. RU: Освобождает ресурсы. EN: Releases resources."""

    async def __aenter__(self) -> BaseSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()


_NOT_SENT_ERRORS: tuple[type[BaseException], ...] = tuple(
    error
    for error in (
        aiohttp.ClientConnectorError,
        getattr(aiohttp, "ConnectionTimeoutError", None),
    )
    if error is not None
)


def _network_error(exc: BaseException, timeout: float) -> NetworkError:
    if isinstance(exc, asyncio.TimeoutError) and not isinstance(exc, aiohttp.ClientError):
        message = f"Request timed out after {timeout}s"
    else:
        message = str(exc) or type(exc).__name__
    return NetworkError(message, request_sent=not isinstance(exc, _NOT_SENT_ERRORS))


def _form_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


class AiohttpSession(BaseSession):
    """UZ: `aiohttp` asosidagi standart sessiya (ixtiyoriy HTTP proksi bilan).
    RU: Стандартная сессия на `aiohttp` (с опциональным HTTP-прокси).
    EN: Default `aiohttp`-based session (with an optional HTTP proxy).
    """

    def __init__(self, *, proxy: str | None = None, connection_limit: int = 100) -> None:
        self._proxy = proxy
        self._connection_limit = connection_limit
        self._session: aiohttp.ClientSession | None = None

    def _client(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=self._connection_limit)
            )
        return self._session

    @staticmethod
    def _build_form(payload: RequestPayload, stack: ExitStack) -> aiohttp.FormData:
        form = aiohttp.FormData(quote_fields=False)
        for key, value in payload.fields.items():
            form.add_field(key, _form_value(value))
        for key, file in payload.files.items():
            form.add_field(key, stack.enter_context(file.open()), filename=file.filename)
        return form

    @staticmethod
    def _decode(body: bytes, status: int) -> dict[str, Any]:
        try:
            data = json.loads(body)
        except ValueError as exc:
            raise NetworkError(f"Non-JSON response (HTTP {status})") from exc
        if not isinstance(data, dict) or "ok" not in data:
            raise NetworkError(f"Unexpected response (HTTP {status})")
        return data

    async def request(self, url: str, payload: RequestPayload, *, timeout: float) -> dict[str, Any]:
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        try:
            with ExitStack() as stack:
                if payload.is_multipart:
                    request = self._client().post(
                        url,
                        data=self._build_form(payload, stack),
                        proxy=self._proxy,
                        timeout=client_timeout,
                    )
                else:
                    request = self._client().post(
                        url, json=payload.fields, proxy=self._proxy, timeout=client_timeout
                    )
                async with request as response:
                    body = await response.read()
                    status = response.status
        except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
            raise _network_error(exc, timeout) from exc
        return self._decode(body, status)

    async def stream(
        self, url: str, *, timeout: float, chunk_size: int = 65536
    ) -> AsyncIterator[bytes]:
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        try:
            async with self._client().get(
                url, proxy=self._proxy, timeout=client_timeout
            ) as response:
                if response.status != 200:
                    raise NetworkError(f"Download failed (HTTP {response.status})")
                async for chunk in response.content.iter_chunked(chunk_size):
                    yield chunk
        except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
            raise _network_error(exc, timeout) from exc

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None


__all__ = ["AiohttpSession", "BaseSession"]
