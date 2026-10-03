"""UZ: Zafather — filtrlar.
RU: Zafather — фильтры.
EN: Zafather — filters.

UZ: Filtr — `False` (mos emas), `True` (mos) yoki `dict` (mos + handlerga qo'shimcha
argumentlar) qaytaradigan har qanday chaqiriluvchi obyekt. Ikkinchi pozitsion
parametr bo'lsa, unga kontekst (`data`) uzatiladi.
RU: Фильтр — любой вызываемый объект, который возвращает `False` (не подходит),
`True` (подходит) или `dict` (подходит + дополнительные аргументы для handler). Если
есть второй позиционный параметр, в него передаётся контекст (`data`).
EN: A filter is any callable returning `False` (no match), `True` (match) or a
`dict` (match + extra handler arguments). When it has a second positional
parameter, the context (`data`) is passed to it.
"""

from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from typing import Any

FilterResult = bool | Mapping[str, Any] | None


def _positional_arity(target: Any) -> int:
    try:
        parameters = inspect.signature(target).parameters.values()
    except (TypeError, ValueError):
        return 1
    if any(p.kind is p.VAR_POSITIONAL for p in parameters):
        return 2
    return sum(1 for p in parameters if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD))


class CompiledFilter:
    """UZ: Istalgan filtrni yagona async interfeysga keltiradi (bir marta tahlil qilinadi).
    RU: Приводит любой фильтр к единому async-интерфейсу (анализ выполняется один раз).
    EN: Adapts any filter to one async interface (the signature is inspected once).
    """

    __slots__ = ("_wants_data", "target")

    def __init__(self, target: Any) -> None:
        if isinstance(target, CompiledFilter):
            target = target.target
        if not callable(target):
            raise TypeError(f"Filter must be callable, got {target!r}")
        self.target: Any = target
        self._wants_data = _positional_arity(target) >= 2

    async def check(self, event: Any, data: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
        result = self.target(event, data) if self._wants_data else self.target(event)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, Mapping):
            return True, dict(result)
        return bool(result), {}

    def __repr__(self) -> str:
        return f"<CompiledFilter {self.target!r}>"


def compile_filter(target: Any) -> CompiledFilter:
    """UZ: Filtrni `CompiledFilter` ga aylantiradi. RU: Превращает фильтр в `CompiledFilter`.
    EN: Turns a filter into a `CompiledFilter`.
    """
    return target if isinstance(target, CompiledFilter) else CompiledFilter(target)


class Filter(ABC):
    """UZ: Filtrlar uchun asosiy sinf; `&`, `|`, `~` amallarini qo'llab-quvvatlaydi.
    RU: Базовый класс фильтров; поддерживает операторы `&`, `|`, `~`.
    EN: Base class for filters; supports the `&`, `|` and `~` operators.
    """

    @abstractmethod
    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        """UZ: Filtr natijasi. RU: Результат фильтра. EN: The filter result."""

    def __and__(self, other: Any) -> AndFilter:
        return AndFilter(self, other)

    def __rand__(self, other: Any) -> AndFilter:
        return AndFilter(other, self)

    def __or__(self, other: Any) -> OrFilter:
        return OrFilter(self, other)

    def __ror__(self, other: Any) -> OrFilter:
        return OrFilter(other, self)

    def __invert__(self) -> NotFilter:
        return NotFilter(self)


class AndFilter(Filter):
    """UZ: Hamma filtr mos kelsa mos. RU: Подходит, если подходят все.
    EN: Matches when every filter matches.
    """

    def __init__(self, *filters: Any) -> None:
        self.filters = tuple(compile_filter(f) for f in filters)

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        extra: dict[str, Any] = {}
        for item in self.filters:
            matched, result = await item.check(event, {**(data or {}), **extra})
            if not matched:
                return False
            extra.update(result)
        return extra or True


class OrFilter(Filter):
    """UZ: Birortasi mos kelsa mos. RU: Подходит, если подходит любой.
    EN: Matches when any filter matches.
    """

    def __init__(self, *filters: Any) -> None:
        self.filters = tuple(compile_filter(f) for f in filters)

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        for item in self.filters:
            matched, result = await item.check(event, data or {})
            if matched:
                return result or True
        return False


class NotFilter(Filter):
    """UZ: Filtrni inkor qiladi. RU: Инвертирует фильтр. EN: Negates a filter."""

    def __init__(self, target: Any) -> None:
        self.target = compile_filter(target)

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        matched, _ = await self.target.check(event, data or {})
        return not matched


def _event_text(event: Any, *, include_data: bool = True) -> str | None:
    text = getattr(event, "text", None) or getattr(event, "caption", None)
    if text is None and include_data:
        text = getattr(event, "data", None)
    return text if isinstance(text, str) else None


class Command(Filter):
    """UZ: `/start`, `/help` kabi buyruqlar. Handlerga `command`, `args`, `mention` keladi.
    RU: Команды вроде `/start`, `/help`. В handler передаются `command`, `args`, `mention`.
    EN: Commands such as `/start`, `/help`. Injects `command`, `args` and `mention`.

    UZ: `/start@BoshqaBot` kabi boshqa botga yozilgan buyruqlar o'tkazib yuboriladi
    (`ignore_mention=True` bilan o'chiriladi).
    RU: Команды для другого бота (`/start@OtherBot`) пропускаются (отключается через
    `ignore_mention=True`).
    EN: Commands addressed to another bot (`/start@OtherBot`) are skipped (disable
    with `ignore_mention=True`).

        @router.message(Command("start", "boshla"))
        async def handler(message, command, args): ...
    """

    def __init__(
        self,
        *commands: str,
        prefix: str = "/",
        ignore_case: bool = True,
        ignore_mention: bool = False,
    ) -> None:
        self.ignore_case = ignore_case
        self.commands = tuple(self._normalize(command.lstrip(prefix)) for command in commands)
        self.prefix = prefix
        self.ignore_mention = ignore_mention

    def _normalize(self, command: str) -> str:
        return command.lower() if self.ignore_case else command

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        text = _event_text(event, include_data=False)
        if not text or text[0] not in self.prefix:
            return False
        head, *tail = text.split(maxsplit=1)
        command, _, mention = head[1:].partition("@")
        command = self._normalize(command)
        if not command or (self.commands and command not in self.commands):
            return False
        if mention and not self.ignore_mention and not await _addressed_to_me(mention, data):
            return False
        return {
            "command": command,
            "args": tail[0].strip() if tail and tail[0].strip() else None,
            "mention": mention or None,
        }


async def _addressed_to_me(mention: str, data: Mapping[str, Any] | None) -> bool:
    bot = (data or {}).get("bot")
    if bot is None:
        return True
    me = await bot.me()
    return str(me.username or "").lower() == mention.lower()


class Text(Filter):
    """UZ: Matn bo'yicha moslash (`text`, `caption` yoki callback `data`).
    RU: Сопоставление по тексту (`text`, `caption` или callback `data`).
    EN: Matches by text (`text`, `caption` or callback `data`).
    """

    def __init__(
        self,
        equals: str | Iterable[str] | None = None,
        contains: str | None = None,
        startswith: str | None = None,
        endswith: str | None = None,
        ignore_case: bool = True,
    ) -> None:
        self.ignore_case = ignore_case
        if isinstance(equals, str):
            equals = [equals]
        self.equals = None if equals is None else frozenset(self._norm(v) for v in equals)
        self.contains = None if contains is None else self._norm(contains)
        self.startswith = None if startswith is None else self._norm(startswith)
        self.endswith = None if endswith is None else self._norm(endswith)

    def _norm(self, value: str) -> str:
        return value.lower() if self.ignore_case else value

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        text = _event_text(event)
        if text is None:
            return False
        text = self._norm(text)
        if self.equals is not None:
            return text in self.equals
        if self.contains is not None:
            return self.contains in text
        if self.startswith is not None:
            return text.startswith(self.startswith)
        if self.endswith is not None:
            return text.endswith(self.endswith)
        return bool(text)


class Regex(Filter):
    """UZ: Regex bo'yicha moslash; handlerga `match` keladi.
    RU: Сопоставление по regex; в handler передаётся `match`.
    EN: Matches by regex; injects `match` into the handler.
    """

    def __init__(self, pattern: str | re.Pattern[str], flags: int = 0) -> None:
        self.pattern = re.compile(pattern, flags) if isinstance(pattern, str) else pattern

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        text = _event_text(event)
        match = self.pattern.search(text) if text is not None else None
        return {"match": match} if match else False


def _event_chat(event: Any) -> Any:
    chat = getattr(event, "chat", None)
    if chat is None:
        message = getattr(event, "message", None)
        chat = getattr(message, "chat", None)
    return chat


class ChatType(Filter):
    """UZ: Chat turi: private / group / supergroup / channel.
    RU: Тип чата: private / group / supergroup / channel.
    EN: Chat type: private / group / supergroup / channel.
    """

    def __init__(self, *types: str) -> None:
        self.types = frozenset(types)

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        chat = _event_chat(event)
        return chat is not None and chat.type in self.types


class UserFilter(Filter):
    """UZ: Faqat ko'rsatilgan foydalanuvchilar (masalan, adminlar).
    RU: Только указанные пользователи (например, администраторы).
    EN: Only the listed users (for example, admins).
    """

    def __init__(self, *user_ids: int) -> None:
        self.user_ids = frozenset(user_ids)

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in self.user_ids


class ContentType(Filter):
    """UZ: Kontent turi: photo, document, voice, video, sticker, location ...
    RU: Тип контента: photo, document, voice, video, sticker, location ...
    EN: Content type: photo, document, voice, video, sticker, location ...
    """

    def __init__(self, *types: str) -> None:
        self.types = tuple(types)

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        return any(getattr(event, name, None) is not None for name in self.types)


class StateFilter(Filter):
    """UZ: FSM holati bo'yicha. `None` — holatsiz, `"*"` — istalgan (bo'sh bo'lmagan)
    holat; `StatesGroup` berilsa — guruhdagi istalgan holat.
    RU: По состоянию FSM. `None` — без состояния, `"*"` — любое (непустое) состояние;
    `StatesGroup` — любое состояние группы.
    EN: Matches the FSM state. `None` means no state, `"*"` any non-empty state and a
    `StatesGroup` any state of that group.
    """

    ANY = "*"

    def __init__(self, *states: Any) -> None:
        self.states: tuple[str | None, ...] = tuple(_expand_states(states))

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        current = (data or {}).get("raw_state")
        return any(
            expected == current or (expected == self.ANY and current is not None)
            for expected in self.states
        )


def _expand_states(states: Iterable[Any]) -> Iterable[str | None]:
    for state in states:
        group_states = getattr(state, "__states__", None)
        if isinstance(state, type) and group_states is not None:
            yield from (item.state for item in group_states)
        else:
            yield getattr(state, "state", state)


class Service(Filter):
    """UZ: Xizmat xabarlari: managed_bot_created, gift, community_chat_added ...
    RU: Служебные сообщения: managed_bot_created, gift, community_chat_added ...
    EN: Service messages: managed_bot_created, gift, community_chat_added ...
    """

    def __init__(self, *fields: str) -> None:
        self.fields = tuple(fields)

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        for name in self.fields:
            value = getattr(event, name, None)
            if value is not None:
                return {"service": name, "service_data": value}
        return False


class Ephemeral(Filter):
    """UZ: Ephemeral xabarlar (Bot API 10.2+). RU: Ephemeral-сообщения (Bot API 10.2+).
    EN: Ephemeral messages (Bot API 10.2+).
    """

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        return getattr(event, "ephemeral_message_id", None) is not None


class Premium(Filter):
    """UZ: Telegram Premium foydalanuvchilari. RU: Пользователи Telegram Premium.
    EN: Telegram Premium users.
    """

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        user = getattr(event, "from_user", None)
        return bool(user is not None and user.is_premium)


class HasCustomEmoji(Filter):
    """UZ: Premium (custom) emoji bor xabarlar; handlerga `custom_emoji_ids` keladi.
    RU: Сообщения с premium (custom) emoji; в handler передаётся `custom_emoji_ids`.
    EN: Messages containing premium (custom) emoji; injects `custom_emoji_ids`.
    """

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        entities = [
            *(getattr(event, "entities", None) or []),
            *(getattr(event, "caption_entities", None) or []),
        ]
        ids = [
            entity.custom_emoji_id
            for entity in entities
            if getattr(entity, "type", None) == "custom_emoji" and entity.custom_emoji_id
        ]
        return {"custom_emoji_ids": ids} if ids else False


class ExceptionTypeFilter(Filter):
    """UZ: Xato handlerlari uchun: xato turi bo'yicha moslash.
    RU: Для обработчиков ошибок: сопоставление по типу исключения.
    EN: For error handlers: matches by exception type.

        @router.error(ExceptionTypeFilter(TelegramAPIError))
        async def on_api_error(event, exception): ...
    """

    def __init__(self, *types: type[BaseException]) -> None:
        self.types = tuple(types)

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        return isinstance((data or {}).get("exception"), self.types)


#: UZ: Qisqa nomlar. RU: Короткие имена. EN: Shortcuts.
IsPrivate = ChatType("private")
IsGroup = ChatType("group", "supergroup")

__all__ = [
    "AndFilter",
    "ChatType",
    "Command",
    "CompiledFilter",
    "ContentType",
    "Ephemeral",
    "ExceptionTypeFilter",
    "Filter",
    "FilterResult",
    "HasCustomEmoji",
    "IsGroup",
    "IsPrivate",
    "NotFilter",
    "OrFilter",
    "Premium",
    "Regex",
    "Service",
    "StateFilter",
    "Text",
    "UserFilter",
    "compile_filter",
]
