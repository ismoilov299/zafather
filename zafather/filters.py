"""Zafather — filtrlar.

Filtr — bu `False` (mos emas), `True` (mos) yoki `dict` (mos + handlerga
qo'shimcha argument uzatish) qaytaradigan har qanday chaqiriluvchi obyekt.
"""
from __future__ import annotations

import inspect
import re
from typing import Any, Callable, Iterable, Optional, Union

_signature_cache: dict = {}


def _param_count(func: Callable) -> int:
    key = id(func)
    cached = _signature_cache.get(key)
    if cached is not None:
        return cached
    try:
        params = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):
        count = 1
    else:
        count = sum(
            1 for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        )
        if any(p.kind == p.VAR_POSITIONAL for p in params):
            count = 2
    _signature_cache[key] = count
    return count


async def check_filter(f: Callable, event, data: dict) -> tuple[bool, dict]:
    """Filtrni chaqirib, (mos_keldimi, qo'shimcha_ma'lumot) qaytaradi."""
    result = f(event, data) if _param_count(f) >= 2 else f(event)
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, dict):
        return True, result
    return bool(result), {}


class Filter:
    """Barcha filtrlar uchun asosiy sinf. `&`, `|`, `~` amallarini qo'llab-quvvatlaydi."""

    async def __call__(self, event, data: dict = None) -> Union[bool, dict]:
        raise NotImplementedError

    def __and__(self, other) -> "AndFilter":
        return AndFilter(self, other)

    def __or__(self, other) -> "OrFilter":
        return OrFilter(self, other)

    def __invert__(self) -> "NotFilter":
        return NotFilter(self)


class AndFilter(Filter):
    def __init__(self, *filters):
        self.filters = filters

    async def __call__(self, event, data: dict = None):
        extra: dict = {}
        for f in self.filters:
            ok, result = await check_filter(f, event, data or {})
            if not ok:
                return False
            extra.update(result)
        return extra or True


class OrFilter(Filter):
    def __init__(self, *filters):
        self.filters = filters

    async def __call__(self, event, data: dict = None):
        for f in self.filters:
            ok, result = await check_filter(f, event, data or {})
            if ok:
                return result or True
        return False


class NotFilter(Filter):
    def __init__(self, target):
        self.target = target

    async def __call__(self, event, data: dict = None):
        ok, _ = await check_filter(self.target, event, data or {})
        return not ok


class Command(Filter):
    """`/start`, `/help` kabi buyruqlar.

        @bot.message(Command("start", "boshla"))
        async def handler(m: Message, command: str, args: str | None): ...
    """

    def __init__(
        self,
        *commands: str,
        prefix: str = "/",
        ignore_case: bool = True,
        ignore_mention: bool = True,
    ):
        self.commands = [c.lstrip("/").lower() if ignore_case else c.lstrip("/") for c in commands]
        self.prefix = prefix
        self.ignore_case = ignore_case
        self.ignore_mention = ignore_mention

    async def __call__(self, event, data: dict = None):
        text = getattr(event, "text", None) or getattr(event, "caption", None)
        if not text:
            return False
        head, _, tail = text.partition(" ")
        if not head or head[0] not in self.prefix:
            return False
        command = head[1:]
        mention = None
        if "@" in command:
            command, _, mention = command.partition("@")
        if self.ignore_case:
            command = command.lower()
        if self.commands and command not in self.commands:
            return False
        return {
            "command": command,
            "args": tail.strip() or None,
            "mention": mention,
        }


class Text(Filter):
    """Matn bo'yicha moslash."""

    def __init__(
        self,
        equals: Union[str, Iterable[str], None] = None,
        contains: Optional[str] = None,
        startswith: Optional[str] = None,
        endswith: Optional[str] = None,
        ignore_case: bool = True,
    ):
        self.equals = [equals] if isinstance(equals, str) else (list(equals) if equals else None)
        self.contains = contains
        self.startswith = startswith
        self.endswith = endswith
        self.ignore_case = ignore_case

    def _norm(self, value: str) -> str:
        return value.lower() if self.ignore_case else value

    async def __call__(self, event, data: dict = None):
        text = (
            getattr(event, "text", None)
            or getattr(event, "caption", None)
            or getattr(event, "data", None)
        )
        if not isinstance(text, str):
            return False
        text = self._norm(text)
        if self.equals is not None:
            return text in [self._norm(v) for v in self.equals]
        if self.contains is not None:
            return self._norm(self.contains) in text
        if self.startswith is not None:
            return text.startswith(self._norm(self.startswith))
        if self.endswith is not None:
            return text.endswith(self._norm(self.endswith))
        return bool(text)


class Regex(Filter):
    """Regex bo'yicha moslash. Handlerga `match` argumentini uzatadi."""

    def __init__(self, pattern: Union[str, re.Pattern], flags: int = 0):
        self.pattern = re.compile(pattern, flags) if isinstance(pattern, str) else pattern

    async def __call__(self, event, data: dict = None):
        text = (
            getattr(event, "text", None)
            or getattr(event, "caption", None)
            or getattr(event, "data", None)
        )
        if not isinstance(text, str):
            return False
        match = self.pattern.search(text)
        return {"match": match} if match else False


class ChatType(Filter):
    """private / group / supergroup / channel."""

    def __init__(self, *types: str):
        self.types = types

    async def __call__(self, event, data: dict = None):
        chat = getattr(event, "chat", None)
        if chat is None and getattr(event, "message", None) is not None:
            chat = event.message.chat
        return bool(chat) and chat.type in self.types


class UserFilter(Filter):
    """Faqat ma'lum foydalanuvchi ID'lari uchun (masalan, adminlar)."""

    def __init__(self, *user_ids: int):
        self.user_ids = set(user_ids)

    async def __call__(self, event, data: dict = None):
        user = getattr(event, "from_user", None)
        return bool(user) and user.id in self.user_ids


class ContentType(Filter):
    """photo, document, voice, video, sticker, location, contact ..."""

    def __init__(self, *types: str):
        self.types = types

    async def __call__(self, event, data: dict = None):
        return any(getattr(event, t, None) is not None for t in self.types)


class StateFilter(Filter):
    """FSM holati bo'yicha filtr. `None` — holat yo'q, `"*"` — istalgan holat."""

    def __init__(self, *states):
        self.states = []
        for s in states:
            self.states.append(getattr(s, "state", s))

    async def __call__(self, event, data: dict = None):
        current = (data or {}).get("raw_state")
        for expected in self.states:
            if expected == "*":
                return current is not None
            if expected == current:
                return True
        return False


class Service(Filter):
    """Xizmat xabarlari filtri: managed_bot_created, gift, community_chat_added ..."""

    def __init__(self, *fields: str):
        self.fields = fields

    async def __call__(self, event, data: dict = None):
        for name in self.fields:
            value = getattr(event, name, None)
            if value is not None:
                return {"service": name, "service_data": value}
        return False


class Ephemeral(Filter):
    """Faqat ephemeral (bir foydalanuvchiga ko'rinadigan) xabarlar — Bot API 10.2."""

    async def __call__(self, event, data: dict = None):
        return getattr(event, "ephemeral_message_id", None) is not None


class Premium(Filter):
    """Foydalanuvchida Telegram Premium bo'lsa."""

    async def __call__(self, event, data: dict = None):
        user = getattr(event, "from_user", None)
        return bool(user and user.is_premium)


class HasCustomEmoji(Filter):
    """Xabarda premium (custom) emoji bo'lsa."""

    async def __call__(self, event, data: dict = None):
        entities = (getattr(event, "entities", None) or []) + (
            getattr(event, "caption_entities", None) or []
        )
        ids = [
            e.custom_emoji_id
            for e in entities
            if getattr(e, "type", None) == "custom_emoji" and e.custom_emoji_id
        ]
        return {"custom_emoji_ids": ids} if ids else False


# qisqa nomlar
IsPrivate = ChatType("private")
IsGroup = ChatType("group", "supergroup")
