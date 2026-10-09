"""UZ: `FSMContext` — handler ichida holat bilan ishlash.
RU: `FSMContext` — работа с состоянием внутри handler.
EN: `FSMContext` — working with the state inside a handler.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .state import State
from .storage.base import BaseStorage, StorageKey


class FSMContext:
    """UZ: Handlerga `state` argumenti sifatida keladi.
    RU: Передаётся в handler как аргумент `state`.
    EN: Passed to handlers as the `state` argument.
    """

    __slots__ = ("key", "storage")

    def __init__(self, storage: BaseStorage, key: StorageKey) -> None:
        self.storage = storage
        self.key = key

    async def get_state(self) -> str | None:
        return await self.storage.get_state(self.key)

    async def set_state(self, state: State | str | None = None) -> None:
        value = state.state if isinstance(state, State) else state
        await self.storage.set_state(self.key, value)

    async def get_data(self) -> dict[str, Any]:
        return await self.storage.get_data(self.key)

    async def set_data(self, data: Mapping[str, Any] | None = None, **values: Any) -> None:
        """UZ: Ma'lumotni to'liq almashtiradi. RU: Полностью заменяет данные.
        EN: Replaces the data entirely.
        """
        await self.storage.set_data(self.key, {**(data or {}), **values})

    async def update_data(
        self, data: Mapping[str, Any] | None = None, **values: Any
    ) -> dict[str, Any]:
        """UZ: Ma'lumotga qo'shadi va yangilangan lug'atni qaytaradi.
        RU: Дополняет данные и возвращает обновлённый словарь.
        EN: Merges into the data and returns the updated dict.
        """
        return await self.storage.update_data(self.key, {**(data or {}), **values})

    async def clear(self) -> None:
        """UZ: Holat va ma'lumotni tozalaydi. RU: Очищает состояние и данные.
        EN: Clears both the state and the data.
        """
        await self.storage.set_state(self.key, None)
        await self.storage.set_data(self.key, {})

    #: UZ: `clear()` bilan bir xil. RU: То же, что `clear()`. EN: Same as `clear()`.
    finish = clear

    def __repr__(self) -> str:
        return f"<FSMContext {self.key.to_string()}>"


__all__ = ["FSMContext"]
