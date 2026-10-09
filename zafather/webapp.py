"""UZ: Zafather — **Mini App** (Telegram Web App) bilan ishlash.
RU: Zafather — работа с **Mini App** (Telegram Web App).
EN: Zafather — working with **Mini App** (Telegram Web App).

UZ: Asosiy qism — `initData` ni server tomonda tekshirish: `validate()` (bot tokeni,
HMAC-SHA256) yoki `validate_third_party()` (tokensiz, Ed25519, Bot API 8.0+).
RU: Главное — проверка `initData` на сервере: `validate()` (токен бота, HMAC-SHA256)
или `validate_third_party()` (без токена, Ed25519, Bot API 8.0+).
EN: The key part is validating `initData` on the server: `validate()` (bot token,
HMAC-SHA256) or `validate_third_party()` (no token, Ed25519, Bot API 8.0+).

::

    try:
        init = validate(init_data, TOKEN, max_age=3600)
        print(init.user.id, init.user.first_name)
    except WebAppAuthError as exc:
        print("Ishonchsiz / Недоверенные / Untrusted:", exc)

UZ: **Hech qachon** tekshirilmagan `user` ga ishonmang — uni brauzerda o'zgartirish mumkin.
RU: **Никогда** не доверяйте непроверенному `user` — его можно подменить в браузере.
EN: **Never** trust an unvalidated `user` — it can be forged in the browser.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import time
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, quote, urlencode

from .exceptions import OptionalDependencyError, ZafatherError
from .filters import Filter, FilterResult

if TYPE_CHECKING:
    from .bot import Bot

#: UZ: Telegram Ed25519 ochiq kalitlari. RU: Открытые ключи Ed25519 Telegram.
#: EN: Telegram's Ed25519 public keys.
TELEGRAM_PUBLIC_KEY_PROD = "e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d"
TELEGRAM_PUBLIC_KEY_TEST = "40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec"

_JSON_FIELDS = ("user", "receiver", "chat")
_INT_FIELDS = ("auth_date", "can_send_after")
_UNSIGNED_FIELDS = ("hash", "signature")


class WebAppAuthError(ZafatherError):
    """UZ: `initData` ishonchsiz yoki eskirgan. RU: `initData` недоверенный или устаревший.
    EN: `initData` is untrusted or expired.
    """


class WebAppObject:
    """UZ: `initData` ichidagi JSON obyekt (user, chat, receiver).
    RU: JSON-объект внутри `initData` (user, chat, receiver).
    EN: A JSON object inside `initData` (user, chat, receiver).
    """

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = dict(data)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._data.get(name)

    @property
    def raw(self) -> dict[str, Any]:
        return self._data

    @property
    def full_name(self) -> str:
        return " ".join(
            part for part in (self._data.get("first_name"), self._data.get("last_name")) if part
        )

    def __repr__(self) -> str:
        return f"<WebAppObject {self._data.get('username') or self._data.get('id')}>"


class WebAppInitData:
    """UZ: Tekshirilgan `initData`; maydonlar atribut orqali o'qiladi.
    RU: Проверенный `initData`; поля доступны как атрибуты.
    EN: Validated `initData`; fields are available as attributes.
    """

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = dict(data)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        value = self._data.get(name)
        return WebAppObject(value) if isinstance(value, dict) else value

    @property
    def raw(self) -> dict[str, Any]:
        return self._data

    @property
    def user_id(self) -> int | None:
        user = self._data.get("user")
        return user.get("id") if isinstance(user, dict) else None

    @property
    def age(self) -> float:
        """UZ: Yaratilganidan beri o'tgan soniyalar. RU: Секунды с момента создания.
        EN: Seconds since creation.
        """
        return time.time() - float(self._data.get("auth_date") or 0)

    def get(self, name: str, default: Any = None) -> Any:
        return self._data.get(name, default)

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def __repr__(self) -> str:
        user = self._data.get("user") or {}
        return f"<WebAppInitData user={user.get('id')}>"


def _pairs(init_data: str) -> list[tuple[str, str]]:
    if not init_data:
        raise WebAppAuthError("initData is empty")
    try:
        return parse_qsl(init_data, strict_parsing=True, keep_blank_values=True)
    except ValueError as exc:
        raise WebAppAuthError(f"Malformed initData: {exc}") from exc


def data_check_string(
    pairs: Iterable[tuple[str, str]], exclude: Iterable[str] = _UNSIGNED_FIELDS
) -> str:
    """UZ: Imzolanadigan satr: `kalit=qiymat` juftliklari, alifbo tartibida, `\\n` bilan.
    RU: Подписываемая строка: пары `ключ=значение` по алфавиту через `\\n`.
    EN: The signed string: alphabetically sorted `key=value` pairs joined by `\\n`.
    """
    skipped = set(exclude)
    return "\n".join(f"{key}={value}" for key, value in sorted(pairs) if key not in skipped)


def _build(pairs: list[tuple[str, str]]) -> WebAppInitData:
    data: dict[str, Any] = dict(pairs)
    for field in _JSON_FIELDS:
        if field in data:
            with contextlib.suppress(TypeError, ValueError):
                data[field] = json.loads(data[field])
    for field in _INT_FIELDS:
        if field in data:
            with contextlib.suppress(TypeError, ValueError):
                data[field] = int(data[field])
    return WebAppInitData(data)


def _check_age(data: WebAppInitData, max_age: int) -> None:
    if not max_age:
        return
    auth_date = data.raw.get("auth_date")
    if not auth_date:
        raise WebAppAuthError("auth_date is missing; cannot check freshness")
    age = time.time() - float(auth_date)
    if age > max_age:
        raise WebAppAuthError(f"initData expired: {int(age)}s old (allowed {max_age}s)")


def _secret_key(token: str) -> bytes:
    return hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()


def validate(init_data: str, token: str, max_age: int = 86400) -> WebAppInitData:
    """UZ: `initData` ni bot tokeni bilan tekshiradi (HMAC-SHA256); `max_age=0` — muddat
    tekshirilmaydi (tavsiya etilmaydi).
    RU: Проверяет `initData` токеном бота (HMAC-SHA256); `max_age=0` — без проверки
    срока (не рекомендуется).
    EN: Validates `initData` with the bot token (HMAC-SHA256); `max_age=0` skips the
    freshness check (not recommended).
    """
    pairs = _pairs(init_data)
    received = dict(pairs).get("hash")
    if not received:
        raise WebAppAuthError("initData has no hash")
    expected = hmac.new(
        _secret_key(token), data_check_string(pairs).encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise WebAppAuthError("hash mismatch: initData was tampered with or belongs to another bot")
    data = _build(pairs)
    _check_age(data, max_age)
    return data


def is_valid(init_data: str, token: str, max_age: int = 86400) -> bool:
    """UZ: `validate()` ning True/False varianti. RU: Вариант `validate()` с True/False.
    EN: A True/False variant of `validate()`.
    """
    try:
        validate(init_data, token, max_age)
    except WebAppAuthError:
        return False
    return True


def validate_third_party(
    init_data: str,
    bot_id: int | str,
    max_age: int = 86400,
    test_env: bool = False,
    public_key: str | None = None,
) -> WebAppInitData:
    """UZ: Tokensiz tekshiruv (Bot API 8.0+), Telegram Ed25519 imzosi orqali;
    `pip install "zafather[miniapp]"` talab qiladi.
    RU: Проверка без токена (Bot API 8.0+) по подписи Ed25519 Telegram; требует
    `pip install "zafather[miniapp]"`.
    EN: Token-less validation (Bot API 8.0+) using Telegram's Ed25519 signature; needs
    `pip install "zafather[miniapp]"`.
    """
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise OptionalDependencyError("cryptography", "miniapp") from exc

    pairs = _pairs(init_data)
    signature = dict(pairs).get("signature")
    if not signature:
        raise WebAppAuthError("initData has no signature")
    key_hex = public_key or (TELEGRAM_PUBLIC_KEY_TEST if test_env else TELEGRAM_PUBLIC_KEY_PROD)
    message = f"{bot_id}:WebAppData\n{data_check_string(pairs)}".encode()
    try:
        raw_signature = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex)).verify(raw_signature, message)
    except (ValueError, InvalidSignature) as exc:
        raise WebAppAuthError("Ed25519 signature mismatch") from exc
    data = _build(pairs)
    _check_age(data, max_age)
    return data


def parse_init_data(init_data: str) -> WebAppInitData:
    """UZ: Tekshirmasdan o'qiydi (faqat debug uchun!). RU: Читает без проверки (только для
    отладки!). EN: Parses without validation (debugging only!).
    """
    return _build(_pairs(init_data))


def sign_init_data(fields: Mapping[str, Any], token: str) -> str:
    """UZ: Testlar uchun haqiqiy imzoli `initData` yasaydi.
    RU: Создаёт подписанный `initData` для тестов.
    EN: Builds a correctly signed `initData` string for tests.
    """
    payload = {
        key: json.dumps(value, separators=(",", ":"))
        if isinstance(value, (dict, list))
        else str(value)
        for key, value in fields.items()
    }
    payload.setdefault("auth_date", str(int(time.time())))
    check = data_check_string(payload.items())
    payload["hash"] = hmac.new(_secret_key(token), check.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


#: UZ: Qisqa nomlar. RU: Короткие имена. EN: Short aliases.
parse = parse_init_data
sign = sign_init_data


def direct_link(
    bot_username: str, app_name: str, start_param: str | None = None, mode: str | None = None
) -> str:
    """UZ: `t.me/<bot>/<app>?startapp=...`; `mode="fullscreen"` (8.0+).
    RU: `t.me/<bot>/<app>?startapp=...`; `mode="fullscreen"` (8.0+).
    EN: `t.me/<bot>/<app>?startapp=...`; `mode="fullscreen"` (8.0+).
    """
    url = f"https://t.me/{bot_username.lstrip('@')}/{app_name}"
    params = {key: value for key, value in (("startapp", start_param), ("mode", mode)) if value}
    return f"{url}?{urlencode(params)}" if params else url


def main_app_link(bot_username: str, start_param: str | None = None) -> str:
    """UZ: Asosiy Mini App: `t.me/<bot>?startapp=...`. RU: Главный Mini App.
    EN: The main Mini App: `t.me/<bot>?startapp=...`.
    """
    url = f"https://t.me/{bot_username.lstrip('@')}"
    return f"{url}?startapp={quote(start_param)}" if start_param else url


def attach_link(bot_username: str, start_param: str | None = None) -> str:
    """UZ: Attachment menyu havolasi. RU: Ссылка меню вложений. EN: An attachment menu link."""
    username = bot_username.lstrip("@")
    url = f"https://t.me/{username}?attach={username}"
    return f"{url}&startattach={quote(start_param)}" if start_param else url


class MiniApp:
    """UZ: Mini App bilan bog'liq Bot API metodlari (`app.mini_app`).
    RU: Методы Bot API, связанные с Mini App (`app.mini_app`).
    EN: Mini App related Bot API methods (`app.mini_app`).
    """

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def set_menu_button(self, text: str, url: str, chat_id: int | None = None) -> Any:
        menu_button = {"type": "web_app", "text": text, "web_app": {"url": url}}
        return await self.bot.call("setChatMenuButton", chat_id=chat_id, menu_button=menu_button)

    async def reset_menu_button(self, chat_id: int | None = None) -> Any:
        return await self.bot.call(
            "setChatMenuButton", chat_id=chat_id, menu_button={"type": "commands"}
        )

    async def get_menu_button(self, chat_id: int | None = None) -> Any:
        return await self.bot.call("getChatMenuButton", chat_id=chat_id)

    async def answer_query(self, query_id: str, result: Mapping[str, Any]) -> Any:
        """UZ: `answerWebAppQuery` — Mini App nomidan xabar. RU: Сообщение от имени Mini App.
        EN: `answerWebAppQuery` — sends a message on behalf of the Mini App.
        """
        return await self.bot.call("answerWebAppQuery", web_app_query_id=query_id, result=result)

    async def answer_text(self, query_id: str, text: str, **fields: Any) -> Any:
        result: dict[str, Any] = {
            "type": "article",
            "id": fields.pop("id", str(time.time_ns())),
            "title": fields.pop("title", text[:60]),
            "input_message_content": {
                "message_text": text,
                "parse_mode": fields.pop("parse_mode", "HTML"),
            },
            **fields,
        }
        return await self.answer_query(query_id, result)

    async def save_prepared_message(
        self, user_id: int, result: Mapping[str, Any], **params: Any
    ) -> Any:
        return await self.bot.call(
            "savePreparedInlineMessage", user_id=user_id, result=result, **params
        )

    async def save_prepared_button(self, **params: Any) -> Any:
        return await self.bot.call("savePreparedKeyboardButton", **params)

    async def set_emoji_status(
        self, user_id: int, custom_emoji_id: str, expiration_date: int | None = None
    ) -> Any:
        return await self.bot.call(
            "setUserEmojiStatus",
            user_id=user_id,
            emoji_status_custom_emoji_id=custom_emoji_id,
            emoji_status_expiration_date=expiration_date,
        )


class WebAppData(Filter):
    """UZ: Mini App `sendData()` orqali yuborgan ma'lumot (reply-klaviatura ilovalari).
    Handlerga `web_app_data` (JSON bo'lsa `dict`) va `web_app_button` keladi.
    RU: Данные, отправленные Mini App через `sendData()` (приложения reply-клавиатуры).
    В handler передаются `web_app_data` (для JSON — `dict`) и `web_app_button`.
    EN: Data sent by a Mini App via `sendData()` (reply-keyboard apps). Injects
    `web_app_data` (a `dict` for JSON) and `web_app_button`.

    UZ: Bu kanal imzolanmagan — muhim amallar uchun `initData` tekshiruvidan foydalaning.
    RU: Этот канал не подписан — для важных действий проверяйте `initData`.
    EN: This channel is unsigned — use `initData` validation for important actions.
    """

    def __init__(self, button_text: str | None = None) -> None:
        self.button_text = button_text

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        payload = getattr(event, "web_app_data", None)
        if payload is None:
            return False
        button_text = payload.button_text
        if self.button_text is not None and button_text != self.button_text:
            return False
        value: Any = payload.data
        with contextlib.suppress(TypeError, ValueError):
            value = json.loads(value)
        return {"web_app_data": value, "web_app_button": button_text}


__all__ = [
    "TELEGRAM_PUBLIC_KEY_PROD",
    "TELEGRAM_PUBLIC_KEY_TEST",
    "MiniApp",
    "WebAppAuthError",
    "WebAppData",
    "WebAppInitData",
    "WebAppObject",
    "attach_link",
    "data_check_string",
    "direct_link",
    "is_valid",
    "main_app_link",
    "parse",
    "parse_init_data",
    "sign",
    "sign_init_data",
    "validate",
    "validate_third_party",
]
