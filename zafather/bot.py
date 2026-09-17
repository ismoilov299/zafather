"""UZ: Zafather — Telegram Bot API klienti.
RU: Zafather — клиент Telegram Bot API.
EN: Zafather — Telegram Bot API client.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Optional, Union

import aiohttp

from .types import Message, TelegramObject, Update, User

log = logging.getLogger("zafather.bot")

#: UZ: Matn yuboradigan metodlar — ularga parse_mode avtomatik qo'shiladi.
#: RU: Методы отправки текста — к ним автоматически добавляется parse_mode.
#: EN: Text-sending methods — parse_mode is attached to them automatically.
_PARSE_MODE_METHODS = {
    "sendMessage",
    "sendPhoto",
    "sendVideo",
    "sendAudio",
    "sendDocument",
    "sendAnimation",
    "sendVoice",
    "editMessageText",
    "editMessageCaption",
    "sendPoll",
}


class TelegramError(Exception):
    """UZ: Telegram API xatosi.
    RU: Ошибка Telegram API.
    EN: Telegram API error.
    """

    def __init__(self, method: str, code: int, description: str, parameters: dict = None):
        self.method = method
        self.code = code
        self.description = description
        self.parameters = parameters or {}
        super().__init__(f"[{code}] {method}: {description}")


class NetworkError(Exception):
    """UZ: Tarmoq bilan bog'liq xato.
    RU: Ошибка, связанная с сетью.
    EN: Network-related error.
    """


class InputFile:
    """UZ: Lokal fayl yoki baytlarni yuklash uchun.
    RU: Для загрузки локального файла или байтов.
    EN: For uploading a local file or raw bytes.

        await m.answer_photo(InputFile("rasm.jpg"))
    """

    def __init__(self, file: Union[str, bytes, os.PathLike], filename: str = None):
        self.file = file
        if filename:
            self.filename = filename
        elif isinstance(file, (str, os.PathLike)):
            self.filename = os.path.basename(str(file))
        else:
            self.filename = "file.dat"

    def read(self) -> bytes:
        if isinstance(self.file, bytes):
            return self.file
        with open(self.file, "rb") as f:
            return f.read()


def _to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(p.capitalize() for p in rest)


class Bot:
    """UZ: Telegram Bot API bilan muloqot qiladigan klient.
    RU: Клиент для работы с Telegram Bot API.
    EN: Client that talks to the Telegram Bot API.

    UZ: Har qanday API metodini snake_case ko'rinishida chaqirish mumkin.
    RU: Любой метод API можно вызывать в виде snake_case.
    EN: Any API method can be called in snake_case form.::

        await bot.send_message(chat_id=1, text="salom")   -> sendMessage
        await bot.get_chat_member(chat_id=1, user_id=2)   -> getChatMember
    """

    def __init__(
        self,
        token: str,
        parse_mode: Optional[str] = None,
        api_url: str = "https://api.telegram.org",
        timeout: int = 60,
    ) -> None:
        if not token or ":" not in token:
            raise ValueError("Token noto'g'ri. @BotFather bergan tokenni kiriting.")
        self.token = token
        self.parse_mode = parse_mode
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self._me: Optional[User] = None

    # --- UZ: sessiya / RU: сессия / EN: session --------------------------------
    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout + 15)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # --- UZ: so'rov yuborish / RU: отправка запроса / EN: sending a request ---
    def _prepare(self, method: str, params: dict) -> tuple[dict, dict]:
        payload, files = {}, {}
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, InputFile):
                files[key] = value
            elif hasattr(value, "to_dict") and not isinstance(value, TelegramObject):
                payload[key] = value.to_dict()
            elif isinstance(value, TelegramObject):
                payload[key] = value.raw
            else:
                payload[key] = value
        if method in _PARSE_MODE_METHODS and self.parse_mode and "parse_mode" not in payload:
            payload["parse_mode"] = self.parse_mode
        return payload, files

    async def call(self, method: str, **params) -> Any:
        """UZ: API metodini chaqirish (xom natija bilan).
        RU: Вызов метода API (с сырым результатом).
        EN: Call an API method (returns the raw result).
        """
        url = f"{self.api_url}/bot{self.token}/{method}"
        payload, files = self._prepare(method, params)
        session = await self.session()

        for attempt in range(4):
            try:
                if files:
                    form = aiohttp.FormData()
                    for key, value in payload.items():
                        form.add_field(
                            key,
                            json.dumps(value, ensure_ascii=False)
                            if isinstance(value, (dict, list))
                            else str(value),
                        )
                    for key, f in files.items():
                        form.add_field(key, f.read(), filename=f.filename)
                    request = session.post(url, data=form)
                else:
                    request = session.post(url, json=payload)

                async with request as resp:
                    data = await resp.json(content_type=None)
            except asyncio.CancelledError:
                raise
            except aiohttp.ClientError as e:
                if attempt == 3:
                    raise NetworkError(f"{method}: {e}") from e
                await asyncio.sleep(1.5 * (attempt + 1))
                continue

            if data.get("ok"):
                return data.get("result")

            code = data.get("error_code", 0)
            params_ = data.get("parameters") or {}
            if code == 429 and attempt < 3:
                retry_after = params_.get("retry_after", 2)
                log.warning("Flood limit: %ss kutilmoqda (%s)", retry_after, method)
                await asyncio.sleep(retry_after)
                continue
            raise TelegramError(method, code, data.get("description", ""), params_)

        raise NetworkError(f"{method}: barcha urinishlar muvaffaqiyatsiz")

    # --- UZ: natijani modelga o'rash / RU: обертка результата в модель / EN: wrap result ---
    def _wrap(self, result: Any) -> Any:
        if isinstance(result, dict):
            if "message_id" in result and "chat" in result:
                return Message(result, self)
            if "is_bot" in result and "id" in result:
                return User(result, self)
            if "update_id" in result:
                return Update(result, self)
            return TelegramObject(result, self)
        if isinstance(result, list):
            return [self._wrap(item) for item in result]
        return result

    async def request(self, method: str, **params) -> Any:
        """UZ: API metodini chaqirib, natijani modelga o'raydi.
        RU: Вызывает метод API и оборачивает результат в модель.
        EN: Calls an API method and wraps the result in a model.
        """
        return self._wrap(await self.call(method, **params))

    def __getattr__(self, name: str):
        """UZ: bot.send_message(...) -> sendMessage. Barcha API metodlari ishlaydi.
        RU: bot.send_message(...) -> sendMessage. Работают все методы API.
        EN: bot.send_message(...) -> sendMessage. All API methods work this way.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        method = _to_camel(name)

        async def api_method(**kwargs):
            return await self.request(method, **kwargs)

        api_method.__name__ = name
        return api_method

    # --- UZ: qulayliklar / RU: удобства / EN: helpers -----------------------------
    async def send_rich(self, chat_id: int, rich, **kwargs):
        """UZ: Rich message yuborish (Bot API 10.1+).
        RU: Отправка rich-сообщения (Bot API 10.1+).
        EN: Send a rich message (Bot API 10.1+).
        """
        payload = rich.to_dict() if hasattr(rich, "to_dict") else rich
        return await self.request(
            "sendRichMessage", chat_id=chat_id, rich_message=payload, **kwargs
        )

    def stream_rich(self, chat_id: int, **kwargs):
        """UZ: AI javobini oqim bilan yuborish uchun `RichStream` yaratadi.
        RU: Создаёт `RichStream` для потоковой отправки ответа ИИ.
        EN: Creates a `RichStream` to send an AI answer as a stream.
        """
        from .rich import RichStream

        return RichStream(self, chat_id, **kwargs)

    async def me(self) -> User:
        if self._me is None:
            self._me = await self.request("getMe")
        return self._me

    async def __aenter__(self) -> "Bot":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"<Bot id={self.token.split(':')[0]}>"
