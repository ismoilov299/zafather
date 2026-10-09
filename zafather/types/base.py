"""UZ: Telegram JSON obyektlari uchun asosiy qobiq.
RU: Базовая обёртка для JSON-объектов Telegram.
EN: Base wrapper for Telegram JSON objects.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

if TYPE_CHECKING:
    from ..bot import Bot

T = TypeVar("T", bound="TelegramObject")


def wrap_value(value: Any, model: type[TelegramObject], bot: Bot | None) -> Any:
    """UZ: JSON qiymatini (ichma-ich ro'yxatlar bilan) modelga o'raydi.
    RU: Оборачивает JSON-значение (включая вложенные списки) в модель.
    EN: Wraps a JSON value (including nested lists) into a model.
    """
    if isinstance(value, Mapping):
        return model(value, bot)
    if isinstance(value, list):
        return [wrap_value(item, model, bot) for item in value]
    return value


class TelegramObject:
    """UZ: Telegram obyektining yengil, faqat o'qiladigan qobig'i.
    RU: Лёгкая обёртка объекта Telegram, только для чтения.
    EN: A lightweight, read-only wrapper over a Telegram object.

    UZ: Maydonlarga atribut orqali murojaat qilinadi; mavjud bo'lmagan maydon `None`
    qaytaradi. Ichki obyektlar avtomatik o'raladi, `from` maydoni `from_user` deb
    ham o'qiladi.
    RU: Поля доступны как атрибуты; отсутствующее поле возвращает `None`. Вложенные
    объекты оборачиваются автоматически, поле `from` доступно как `from_user`.
    EN: Fields are available as attributes; a missing field returns `None`. Nested
    objects are wrapped automatically and the `from` field is exposed as `from_user`.

    UZ: Misol / RU: Пример / EN: Example::

        message.chat.id, message.from_user.first_name, update.raw["update_id"]
    """

    #: UZ: Maydon nomi -> model sinfi. RU: Имя поля -> класс модели.
    #: EN: Field name -> model class.
    FIELD_TYPES: ClassVar[Mapping[str, type[TelegramObject]]] = {}
    #: UZ: Python nomi -> JSON kaliti. RU: Имя Python -> ключ JSON.
    #: EN: Python name -> JSON key.
    FIELD_ALIASES: ClassVar[Mapping[str, str]] = {"from_user": "from"}

    __slots__ = ("_bot", "_cache", "_data")

    def __init__(self, data: Mapping[str, Any] | None = None, bot: Bot | None = None) -> None:
        self._data: dict[str, Any] = dict(data) if data is not None else {}
        self._bot = bot
        self._cache: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        key = self.FIELD_ALIASES.get(name, name)
        if key in self._cache:
            return self._cache[key]
        if key not in self._data:
            return None
        value = wrap_value(self._data[key], self.FIELD_TYPES.get(key, TelegramObject), self._bot)
        self._cache[key] = value
        return value

    def get_bot(self) -> Bot | None:
        """UZ: Obyekt bog'langan `Bot` klienti (bo'lmasa `None`).
        RU: Клиент `Bot`, к которому привязан объект (или `None`).
        EN: The `Bot` client this object is bound to (or `None`).
        """
        return self._bot

    def bind(self: T, bot: Bot) -> T:
        """UZ: Shu ma'lumot bilan, lekin boshqa `Bot` ga bog'langan nusxa qaytaradi.
        RU: Возвращает копию с теми же данными, привязанную к другому `Bot`.
        EN: Returns a copy with the same data bound to another `Bot`.
        """
        return type(self)(self._data, bot)

    def _client(self) -> Bot:
        if self._bot is None:
            raise RuntimeError(
                f"{type(self).__name__} is not bound to a Bot; use obj.bind(bot) first"
            )
        return self._bot

    @property
    def raw(self) -> dict[str, Any]:
        """UZ: Xom JSON lug'ati. RU: Исходный словарь JSON. EN: The raw JSON dict."""
        return self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return self._data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TelegramObject):
            return NotImplemented
        return type(self) is type(other) and self._data == other._data

    __hash__ = None  # type: ignore[assignment]

    def __dir__(self) -> list[str]:
        return sorted({*super().__dir__(), *self._data, *self.FIELD_ALIASES})

    def __repr__(self) -> str:
        body = json.dumps(self._data, ensure_ascii=False, default=str)
        if len(body) > 240:
            body = body[:240] + "…"
        return f"{type(self).__name__}({body})"


__all__ = ["TelegramObject", "wrap_value"]
