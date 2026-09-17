"""UZ: Redis-backed FSM storage.
RU: Storage на Redis для FSM.
EN: Redis-backed FSM storage.
"""
from __future__ import annotations

import json
from typing import Optional

from zafather.fsm import BaseStorage, StorageKey

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover
    redis = None


class RedisStorage(BaseStorage):
    """UZ: Redis asosidagi FSM storage. TTL bilan ishlaydi.
    RU: FSM storage на Redis с TTL.
    EN: Redis-backed FSM storage with TTL.
    """

    def __init__(self, url: str = "redis://localhost:6379/0", prefix: str = "zafather:", ttl: int = 86400):
        if redis is None:
            raise RuntimeError(
                "Redis support requires the optional dependency 'redis'. Install with: pip install redis"
            )
        self.url = url
        self.prefix = prefix
        self.ttl = ttl
        self.client = redis.from_url(url, decode_responses=True)

    def _state_key(self, key: StorageKey) -> str:
        return f"{self.prefix}state:{key[0]}:{key[1]}"

    def _data_key(self, key: StorageKey) -> str:
        return f"{self.prefix}data:{key[0]}:{key[1]}"

    async def get_state(self, key: StorageKey) -> Optional[str]:
        value = await self.client.get(self._state_key(key))
        return value or None

    async def set_state(self, key: StorageKey, state: Optional[str]) -> None:
        if state is None:
            await self.client.delete(self._state_key(key))
            return
        await self.client.set(self._state_key(key), state, ex=self.ttl)

    async def get_data(self, key: StorageKey) -> dict:
        value = await self.client.get(self._data_key(key))
        if not value:
            return {}
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}

    async def set_data(self, key: StorageKey, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        await self.client.set(self._data_key(key), payload, ex=self.ttl)

    async def close(self) -> None:
        await self.client.aclose()


__all__ = ["RedisStorage"]
