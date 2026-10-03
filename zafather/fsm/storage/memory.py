"""UZ: Xotirada saqlovchi FSM storage.
RU: Хранилище FSM в оперативной памяти.
EN: In-memory FSM storage.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .base import BaseStorage, StorageKey


class MemoryStorage(BaseStorage):
    """UZ: RAM'da saqlaydi; bot qayta ishga tushsa holatlar yo'qoladi.
    RU: Хранит в RAM; при перезапуске бота состояния теряются.
    EN: Keeps everything in RAM; states are lost when the bot restarts.
    """

    def __init__(self) -> None:
        self._states: dict[StorageKey, str] = {}
        self._data: dict[StorageKey, dict[str, Any]] = {}

    async def get_state(self, key: StorageKey) -> str | None:
        return self._states.get(key)

    async def set_state(self, key: StorageKey, state: str | None) -> None:
        if state is None:
            self._states.pop(key, None)
        else:
            self._states[key] = state

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        return copy.deepcopy(self._data.get(key, {}))

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        if data:
            self._data[key] = copy.deepcopy(dict(data))
        else:
            self._data.pop(key, None)


__all__ = ["MemoryStorage"]
