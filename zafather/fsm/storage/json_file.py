"""UZ: JSON faylga yozadigan FSM storage.
RU: Хранилище FSM с записью в JSON-файл.
EN: FSM storage persisted to a JSON file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .base import StorageKey
from .memory import MemoryStorage

log = logging.getLogger("zafather.fsm")

_FORMAT_VERSION = 2
_LegacyKey = tuple[int, int]


class JSONStorage(MemoryStorage):
    """UZ: Holatlarni JSON faylga atomik yozadi (kichik botlar uchun).
    RU: Атомарно записывает состояния в JSON-файл (для небольших ботов).
    EN: Atomically persists states to a JSON file (for small bots).

    UZ: 0.4.x formatidagi (`chat:user` kalitli) fayl ham o'qiladi: eski yozuv birinchi
    murojaatda yangi kalitga ko'chiriladi.
    RU: Файл формата 0.4.x (ключи `chat:user`) тоже читается: старая запись переносится
    на новый ключ при первом обращении.
    EN: Files in the 0.4.x format (`chat:user` keys) are still read: a legacy entry is
    moved to the new key on first access.
    """

    def __init__(self, path: str | os.PathLike[str] = "zafather_state.json") -> None:
        super().__init__()
        self.path = Path(path)
        self._lock = asyncio.Lock()
        self._legacy_states: dict[_LegacyKey, str] = {}
        self._legacy_data: dict[_LegacyKey, dict[str, Any]] = {}
        self._load()

    # --- UZ: o'qish / RU: чтение / EN: loading -------------------------------------------------
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            log.warning("Cannot read FSM state file %s: %s", self.path, exc)
            return
        if raw.get("version") == _FORMAT_VERSION:
            self._states = {StorageKey.from_string(k): v for k, v in raw.get("states", {}).items()}
            self._data = {StorageKey.from_string(k): v for k, v in raw.get("data", {}).items()}
        else:
            self._legacy_states = {_legacy_key(k): v for k, v in raw.get("states", {}).items()}
            self._legacy_data = {_legacy_key(k): v for k, v in raw.get("data", {}).items()}

    def _adopt_legacy(self, key: StorageKey) -> None:
        legacy_key = (key.chat_id, key.user_id)
        if legacy_key in self._legacy_states:
            self._states.setdefault(key, self._legacy_states.pop(legacy_key))
        if legacy_key in self._legacy_data:
            self._data.setdefault(key, self._legacy_data.pop(legacy_key))

    # --- UZ: yozish / RU: запись / EN: saving -------------------------------------------------
    def _snapshot(self) -> dict[str, Any]:
        return {
            "version": _FORMAT_VERSION,
            "states": {key.to_string(): value for key, value in self._states.items()},
            "data": {key.to_string(): value for key, value in self._data.items()},
        }

    def _write(self, snapshot: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self.path)

    async def _flush(self) -> None:
        await asyncio.to_thread(self._write, self._snapshot())

    # --- UZ: BaseStorage / RU: BaseStorage / EN: BaseStorage ------------------------------
    async def get_state(self, key: StorageKey) -> str | None:
        self._adopt_legacy(key)
        return await super().get_state(key)

    async def set_state(self, key: StorageKey, state: str | None) -> None:
        async with self._lock:
            self._adopt_legacy(key)
            await super().set_state(key, state)
            await self._flush()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        self._adopt_legacy(key)
        return await super().get_data(key)

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        async with self._lock:
            self._adopt_legacy(key)
            await super().set_data(key, data)
            await self._flush()


def _legacy_key(value: str) -> _LegacyKey:
    chat_id, user_id = (int(part) for part in value.split(":"))
    return chat_id, user_id


__all__ = ["JSONStorage"]
