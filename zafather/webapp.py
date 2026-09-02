"""Zafather — **Mini App** (Telegram Web App) bilan ishlash.

Uch qismdan iborat:

1. `validate()` — foydalanuvchi ma'lumotini tekshirish (eng muhimi!).
   Mini App'dan kelgan `initData` ni bot tokeni bilan tekshiradi.
2. `validate_third_party()` — token'siz tekshirish (Bot API 8.0+),
   Telegram'ning Ed25519 ochiq kaliti orqali.
3. `MiniApp` — bot tomonidagi metodlar: menyu tugmasi, `answerWebAppQuery`,
   tayyor xabar/tugmalar, emoji status.

::

    from zafather import validate, WebAppAuthError

    try:
        init = validate(init_data_string, TOKEN, max_age=3600)
        print(init.user.id, init.user.first_name)
    except WebAppAuthError as exc:
        print("Ishonchsiz ma'lumot:", exc)

**Hech qachon** `initData` ichidagi `user` ni tekshirmasdan ishonmang —
uni brauzerda istalgan odam o'zgartirishi mumkin.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional, Union
from urllib.parse import parse_qsl, quote, urlencode

from .filters import Filter

#: Telegram'ning Ed25519 ochiq kalitlari (uchinchi tomon tekshiruvi uchun)
TELEGRAM_PUBLIC_KEY_PROD = "e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d"
TELEGRAM_PUBLIC_KEY_TEST = "40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec"

#: initData ichida JSON bo'lgan maydonlar
_JSON_FIELDS = ("user", "receiver", "chat")


class WebAppAuthError(Exception):
    """initData ishonchsiz yoki eskirgan."""


class WebAppInitData:
    """Tekshirilgan `initData`. Maydonlarga atribut orqali murojaat qilinadi."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        value = (self.__dict__.get("_data") or {}).get(name)
        if isinstance(value, dict):
            return _Obj(value)
        return value

    @property
    def raw(self) -> dict:
        return self._data

    @property
    def user_id(self) -> Optional[int]:
        user = self._data.get("user") or {}
        return user.get("id")

    @property
    def age(self) -> float:
        """initData yaratilganidan beri o'tgan soniyalar."""
        return time.time() - float(self._data.get("auth_date", 0))

    def get(self, name: str, default: Any = None) -> Any:
        return self._data.get(name, default)

    def __contains__(self, item: str) -> bool:
        return item in self._data

    def __repr__(self) -> str:
        user = self._data.get("user") or {}
        return f"<WebAppInitData user={user.get('id')} @{user.get('username')}>"


class _Obj:
    """initData ichidagi JSON obyektlari (user, chat, receiver) uchun qobiq."""

    def __init__(self, data: dict) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return (self.__dict__.get("_data") or {}).get(name)

    @property
    def raw(self) -> dict:
        return self._data

    @property
    def full_name(self) -> str:
        parts = [self._data.get("first_name"), self._data.get("last_name")]
        return " ".join(p for p in parts if p)

    def __repr__(self) -> str:
        return f"<{self._data.get('username') or self._data.get('id')}>"


# --- ichki yordamchilar -------------------------------------------------------


def _pairs(init_data: str) -> list:
    if not init_data:
        raise WebAppAuthError("initData bo'sh")
    try:
        return parse_qsl(init_data, strict_parsing=True, keep_blank_values=True)
    except ValueError as exc:
        raise WebAppAuthError(f"initData formati noto'g'ri: {exc}") from exc


def _check_string(pairs: list, exclude=("hash", "signature")) -> str:
    return "\n".join(
        f"{key}={value}" for key, value in sorted(pairs) if key not in exclude
    )


def _build(pairs: list) -> WebAppInitData:
    data: Dict[str, Any] = dict(pairs)
    for field in _JSON_FIELDS:
        if field in data:
            try:
                data[field] = json.loads(data[field])
            except (ValueError, TypeError):
                pass
    for field in ("auth_date", "can_send_after"):
        if field in data:
            try:
                data[field] = int(data[field])
            except (ValueError, TypeError):
                pass
    return WebAppInitData(data)


def _check_age(data: WebAppInitData, max_age: int) -> None:
    if not max_age:
        return
    auth_date = data.raw.get("auth_date")
    if not auth_date:
        raise WebAppAuthError("auth_date yo'q — muddatni tekshirib bo'lmaydi")
    age = time.time() - float(auth_date)
    if age > max_age:
        raise WebAppAuthError(
            f"initData eskirgan: {int(age)}s o'tgan (ruxsat: {max_age}s)"
        )


# --- asosiy tekshiruv ---------------------------------------------------------


def validate(
    init_data: str,
    token: str,
    max_age: int = 86400,
) -> WebAppInitData:
    """`initData` ni bot tokeni bilan tekshiradi (HMAC-SHA256).

    Xato bo'lsa `WebAppAuthError` ko'taradi, aks holda `WebAppInitData` qaytaradi.
    `max_age=0` — muddat tekshirilmaydi (tavsiya etilmaydi).
    """
    pairs = _pairs(init_data)
    received = dict(pairs).get("hash")
    if not received:
        raise WebAppAuthError("initData ichida `hash` yo'q")

    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(
        secret, _check_string(pairs).encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, received):
        raise WebAppAuthError("hash mos kelmadi — ma'lumot o'zgartirilgan bo'lishi mumkin")

    data = _build(pairs)
    _check_age(data, max_age)
    return data


def is_valid(init_data: str, token: str, max_age: int = 86400) -> bool:
    """`validate()` ning `True/False` qaytaradigan varianti."""
    try:
        validate(init_data, token, max_age)
        return True
    except WebAppAuthError:
        return False


def validate_third_party(
    init_data: str,
    bot_id: Union[int, str],
    max_age: int = 86400,
    test_env: bool = False,
    public_key: Optional[str] = None,
) -> WebAppInitData:
    """Token'siz tekshirish (Bot API 8.0+) — Telegram'ning Ed25519 imzosi orqali.

    Mini App'ni sizning nomingizdan boshqa xizmat qayta ishlaganda kerak bo'ladi:
    unga faqat `initData` va `bot_id` beriladi, token berilmaydi.

    `cryptography` paketi talab qilinadi: ``pip install cryptography``
    """
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:  # pragma: no cover
        raise WebAppAuthError(
            "Ed25519 tekshiruvi uchun `cryptography` kerak: pip install cryptography"
        ) from exc

    pairs = _pairs(init_data)
    signature = dict(pairs).get("signature")
    if not signature:
        raise WebAppAuthError("initData ichida `signature` yo'q")

    key_hex = public_key or (TELEGRAM_PUBLIC_KEY_TEST if test_env else TELEGRAM_PUBLIC_KEY_PROD)
    check_string = f"{bot_id}:WebAppData\n" + _check_string(pairs)

    padding = "=" * (-len(signature) % 4)
    try:
        raw_signature = base64.urlsafe_b64decode(signature + padding)
    except (ValueError, TypeError) as exc:
        raise WebAppAuthError("signature base64url formatida emas") from exc

    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex)).verify(
            raw_signature, check_string.encode()
        )
    except InvalidSignature as exc:
        raise WebAppAuthError("Ed25519 imzosi mos kelmadi") from exc

    data = _build(pairs)
    _check_age(data, max_age)
    return data


def parse_init_data(init_data: str) -> WebAppInitData:
    """Tekshirmasdan faqat o'qish (test/debug uchun). Ishonch uchun ishlatmang!"""
    return _build(_pairs(init_data))


def sign(data: dict, token: str) -> str:
    """Test uchun: berilgan maydonlardan haqiqiy `initData` qatorini yasaydi."""
    payload = {}
    for key, value in data.items():
        payload[key] = json.dumps(value, separators=(",", ":")) if isinstance(value, (dict, list)) else str(value)
    payload.setdefault("auth_date", str(int(time.time())))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    check = _check_string(list(payload.items()))
    payload["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


# --- havolalar ----------------------------------------------------------------


def direct_link(
    bot_username: str,
    app_name: str,
    start_param: Optional[str] = None,
    mode: Optional[str] = None,
) -> str:
    """To'g'ridan-to'g'ri Mini App havolasi: ``t.me/<bot>/<app>?startapp=...``

    `mode="fullscreen"` — to'liq ekranda ochadi (Bot API 8.0+).
    """
    url = f"https://t.me/{bot_username.lstrip('@')}/{app_name}"
    params = {}
    if start_param:
        params["startapp"] = start_param
    if mode:
        params["mode"] = mode
    return f"{url}?{urlencode(params)}" if params else url


def main_app_link(bot_username: str, start_param: Optional[str] = None) -> str:
    """Botning asosiy Mini App'i: ``t.me/<bot>?startapp=...`` (Bot API 7.8+)."""
    url = f"https://t.me/{bot_username.lstrip('@')}"
    return f"{url}?startapp={quote(start_param)}" if start_param else url


def attach_link(bot_username: str, start_param: Optional[str] = None) -> str:
    """Attachment menu havolasi: ``t.me/<bot>?attach=...``"""
    url = f"https://t.me/{bot_username.lstrip('@')}?attach={bot_username.lstrip('@')}"
    return f"{url}&startattach={quote(start_param)}" if start_param else url


# --- bot tomonidagi metodlar --------------------------------------------------


class MiniApp:
    """Mini App bilan bog'liq Bot API metodlari ustidagi qobiq.

        app = MiniApp(bot.bot)
        await app.set_menu_button("🚀 Ochish", "https://example.com/app")
    """

    def __init__(self, bot) -> None:
        self.bot = bot

    async def set_menu_button(
        self, text: str, url: str, chat_id: Optional[int] = None
    ):
        """Chatdagi menyu tugmasini Mini App'ga aylantiradi."""
        return await self.bot.call(
            "setChatMenuButton",
            chat_id=chat_id,
            menu_button={"type": "web_app", "text": text, "web_app": {"url": url}},
        )

    async def reset_menu_button(self, chat_id: Optional[int] = None):
        """Menyu tugmasini standart holatga qaytaradi."""
        return await self.bot.call(
            "setChatMenuButton", chat_id=chat_id, menu_button={"type": "commands"}
        )

    async def get_menu_button(self, chat_id: Optional[int] = None):
        return await self.bot.call("getChatMenuButton", chat_id=chat_id)

    async def answer_query(self, query_id: str, result: dict):
        """`answerWebAppQuery` — Mini App nomidan chatga xabar yuboradi.

        `query_id` — `initData.query_id`, `result` — InlineQueryResult dict.
        """
        return await self.bot.call(
            "answerWebAppQuery", web_app_query_id=query_id, result=result
        )

    async def answer_text(self, query_id: str, text: str, **kwargs):
        """`answer_query` ning matn uchun qisqartmasi."""
        result = {
            "type": "article",
            "id": kwargs.pop("id", str(int(time.time() * 1000))),
            "title": kwargs.pop("title", text[:60]),
            "input_message_content": {
                "message_text": text,
                "parse_mode": kwargs.pop("parse_mode", "HTML"),
            },
        }
        result.update(kwargs)
        return await self.answer_query(query_id, result)

    async def save_prepared_message(self, user_id: int, result: dict, **kwargs):
        """`savePreparedInlineMessage` — Mini App'dan `shareMessage` uchun."""
        return await self.bot.call(
            "savePreparedInlineMessage", user_id=user_id, result=result, **kwargs
        )

    async def save_prepared_button(self, **params):
        """`savePreparedKeyboardButton` (Bot API 9.6+) — Mini App'dan
        foydalanuvchi/chat/managed bot so'rash uchun tugma tayyorlaydi."""
        return await self.bot.call("savePreparedKeyboardButton", **params)

    async def set_emoji_status(
        self, user_id: int, custom_emoji_id: str, expiration_date: Optional[int] = None
    ):
        """Foydalanuvchi emoji statusini o'rnatadi (avval ruxsat so'ralishi kerak)."""
        return await self.bot.call(
            "setUserEmojiStatus",
            user_id=user_id,
            emoji_status_custom_emoji_id=custom_emoji_id,
            emoji_status_expiration_date=expiration_date,
        )


# --- filtr --------------------------------------------------------------------


class WebAppData(Filter):
    """Mini App `sendData()` orqali yuborgan ma'lumot (faqat reply-keyboard app'lar).

        @bot.message(WebAppData())
        async def on_data(m, web_app_data):
            await m.answer(f"Qabul qilindi: {web_app_data}")

    JSON bo'lsa avtomatik `dict` ga aylantiriladi. Ushbu kanal **imzolanmagan**,
    shuning uchun muhim amallar uchun `initData` bilan backend tekshiruvidan
    foydalaning.
    """

    def __init__(self, button_text: Optional[str] = None):
        self.button_text = button_text

    async def __call__(self, event, data: dict = None):
        payload = getattr(event, "web_app_data", None)
        if payload is None:
            return False
        if self.button_text and payload.button_text != self.button_text:
            return False
        value = payload.data
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            pass
        return {"web_app_data": value, "web_app_button": payload.button_text}


#: qisqa nom
parse = parse_init_data
