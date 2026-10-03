"""UZ: FSM storage interfeysi va kalit.
RU: Интерфейс хранилища FSM и ключ.
EN: FSM storage interface and key.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StorageKey:
    """UZ: Holat kaliti: bot, chat, foydalanuvchi va (ixtiyoriy) forum mavzusi.
    RU: Ключ состояния: бот, чат, пользователь и (опционально) тема форума.
    EN: State key: bot, chat, user and (optionally) a forum topic.

    UZ: `bot_id` bitta storage bir nechta bot (masalan, `BotFarm`) bilan
    ishlatilganda holatlar aralashib ketmasligi uchun kerak.
    RU: `bot_id` нужен, чтобы состояния не смешивались, когда одно хранилище
    используют несколько ботов (например, `BotFarm`).
    EN: `bot_id` keeps states apart when one storage serves several bots (for
    example a `BotFarm`).
    """

    bot_id: int
    chat_id: int
    user_id: int
    thread_id: int | None = None

    def to_string(self, separator: str = ":") -> str:
        parts = [self.bot_id, self.chat_id, self.user_id]
        if self.thread_id is not None:
            parts.append(self.thread_id)
        return separator.join(str(part) for part in parts)

    @classmethod
    def from_string(cls, value: str, separator: str = ":") -> StorageKey:
        parts = [int(part) for part in value.split(separator)]
        if len(parts) not in (3, 4):
            raise ValueError(f"Invalid storage key: {value!r}")
        return cls(*parts)


class BaseStorage(ABC):
    """UZ: FSM holati va ma'lumotlari uchun storage interfeysi.
    RU: Интерфейс хранилища состояний и данных FSM.
    EN: Storage interface for FSM states and data.
    """

    @abstractmethod
    async def get_state(self, key: StorageKey) -> str | None:
        """UZ: Joriy holat. RU: Текущее состояние. EN: The current state."""

    @abstractmethod
    async def set_state(self, key: StorageKey, state: str | None) -> None:
        """UZ: `None` — holatni o'chiradi. RU: `None` — удаляет состояние.
        EN: `None` removes the state.
        """

    @abstractmethod
    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        """UZ: Ma'lumot nusxasi. RU: Копия данных. EN: A copy of the data."""

    @abstractmethod
    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        """UZ: Ma'lumotni almashtiradi. RU: Заменяет данные. EN: Replaces the data."""

    async def update_data(self, key: StorageKey, data: Mapping[str, Any]) -> dict[str, Any]:
        """UZ: Ma'lumotni birlashtiradi va natijani qaytaradi.
        RU: Объединяет данные и возвращает результат.
        EN: Merges the data and returns the result.
        """
        current = await self.get_data(key)
        current.update(data)
        await self.set_data(key, current)
        return current

    async def close(self) -> None:  # noqa: B027
        """UZ: Resurslarni bo'shatadi. RU: Освобождает ресурсы. EN: Releases resources."""


__all__ = ["BaseStorage", "StorageKey"]
