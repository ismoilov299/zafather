"""Zafather — FSM (holatlar mashinasi).

    class Form(StatesGroup):
        name = State()
        age = State()

    @bot.command("start")
    async def start(m: Message, state: FSMContext):
        await state.set_state(Form.name)
        await m.answer("Ismingiz?")
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


class State:
    """Bitta holat. `StatesGroup` ichida e'lon qilinadi."""

    def __init__(self, name: Optional[str] = None):
        self._name = name
        self._group: Optional[str] = None

    @property
    def state(self) -> str:
        if self._group:
            return f"{self._group}:{self._name}"
        return self._name or "state"

    def __set_name__(self, owner, name):
        if self._name is None:
            self._name = name

    def __str__(self) -> str:
        return self.state

    def __repr__(self) -> str:
        return f"<State {self.state}>"

    def __eq__(self, other) -> bool:
        if isinstance(other, State):
            return self.state == other.state
        if isinstance(other, str):
            return self.state == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.state)


class StatesGroupMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        states = []
        for key, value in namespace.items():
            if isinstance(value, State):
                value._group = name
                if value._name is None:
                    value._name = key
                states.append(value)
        cls.__states__ = tuple(states)
        return cls

    def __iter__(cls):
        return iter(cls.__states__)


class StatesGroup(metaclass=StatesGroupMeta):
    """Holatlar guruhi."""

    __states__: tuple = ()

    @classmethod
    def all(cls) -> tuple:
        return cls.__states__


StorageKey = Tuple[int, int]


class BaseStorage:
    async def get_state(self, key: StorageKey) -> Optional[str]:
        raise NotImplementedError

    async def set_state(self, key: StorageKey, state: Optional[str]) -> None:
        raise NotImplementedError

    async def get_data(self, key: StorageKey) -> dict:
        raise NotImplementedError

    async def set_data(self, key: StorageKey, data: dict) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        return None


class MemoryStorage(BaseStorage):
    """RAM'da saqlaydigan oddiy storage (bot qayta ishga tushsa o'chadi)."""

    def __init__(self) -> None:
        self._states: Dict[StorageKey, Optional[str]] = {}
        self._data: Dict[StorageKey, dict] = {}

    async def get_state(self, key: StorageKey) -> Optional[str]:
        return self._states.get(key)

    async def set_state(self, key: StorageKey, state: Optional[str]) -> None:
        if state is None:
            self._states.pop(key, None)
        else:
            self._states[key] = state

    async def get_data(self, key: StorageKey) -> dict:
        return dict(self._data.get(key, {}))

    async def set_data(self, key: StorageKey, data: dict) -> None:
        self._data[key] = dict(data)


class JSONStorage(MemoryStorage):
    """Diskka JSON qilib yozadigan storage (kichik botlar uchun yetarli)."""

    def __init__(self, path: str = "zafather_state.json") -> None:
        super().__init__()
        self.path = path
        self._load()

    def _load(self) -> None:
        import json
        import os

        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (ValueError, OSError):
            return
        self._states = {tuple(map(int, k.split(":"))): v for k, v in raw.get("states", {}).items()}
        self._data = {tuple(map(int, k.split(":"))): v for k, v in raw.get("data", {}).items()}

    def _dump(self) -> None:
        import json

        payload = {
            "states": {f"{k[0]}:{k[1]}": v for k, v in self._states.items()},
            "data": {f"{k[0]}:{k[1]}": v for k, v in self._data.items()},
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

    async def set_state(self, key: StorageKey, state: Optional[str]) -> None:
        await super().set_state(key, state)
        self._dump()

    async def set_data(self, key: StorageKey, data: dict) -> None:
        await super().set_data(key, data)
        self._dump()


class FSMContext:
    """Handler ichida `state` argumenti sifatida keladi."""

    def __init__(self, storage: BaseStorage, key: StorageKey):
        self.storage = storage
        self.key = key

    async def set_state(self, state) -> None:
        await self.storage.set_state(self.key, getattr(state, "state", state))

    async def get_state(self) -> Optional[str]:
        return await self.storage.get_state(self.key)

    async def get_data(self) -> dict:
        return await self.storage.get_data(self.key)

    async def set_data(self, **kwargs: Any) -> None:
        await self.storage.set_data(self.key, kwargs)

    async def update_data(self, **kwargs: Any) -> dict:
        data = await self.storage.get_data(self.key)
        data.update(kwargs)
        await self.storage.set_data(self.key, data)
        return data

    async def clear(self) -> None:
        await self.storage.set_state(self.key, None)
        await self.storage.set_data(self.key, {})

    async def finish(self) -> None:
        """clear() bilan bir xil — qulaylik uchun."""
        await self.clear()
