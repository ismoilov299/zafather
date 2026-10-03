"""UZ: Redis asosidagi FSM storage.
RU: Хранилище FSM на Redis.
EN: Redis-backed FSM storage.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ...exceptions import OptionalDependencyError
from .base import BaseStorage, StorageKey


class RedisStorage(BaseStorage):
    """UZ: Holatlarni Redis'da saqlaydi (`pip install "zafather[redis]"`).
    RU: Хранит состояния в Redis (`pip install "zafather[redis]"`).
    EN: Stores states in Redis (`pip install "zafather[redis]"`).

    UZ: `ttl` (soniya) — yozuvlarning yashash muddati; `None` — cheksiz.
    `client` orqali tayyor `redis.asyncio.Redis` obyektini berish mumkin.
    RU: `ttl` (секунды) — время жизни записей; `None` — без ограничения.
    Через `client` можно передать готовый `redis.asyncio.Redis`.
    EN: `ttl` (seconds) is the lifetime of entries; `None` means forever. An existing
    `redis.asyncio.Redis` can be passed via `client`.
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        *,
        prefix: str = "zafather",
        ttl: int | None = 86400,
        client: Any = None,
    ) -> None:
        if client is None:
            try:
                from redis import asyncio as redis_asyncio
            except ImportError as exc:
                raise OptionalDependencyError("redis", "redis") from exc
            client = redis_asyncio.from_url(url, decode_responses=True)
        self.client = client
        self.prefix = prefix.rstrip(":")
        self.ttl = ttl

    def _key(self, key: StorageKey, kind: str) -> str:
        return f"{self.prefix}:{kind}:{key.to_string()}"

    async def get_state(self, key: StorageKey) -> str | None:
        value = await self.client.get(self._key(key, "state"))
        return value or None

    async def set_state(self, key: StorageKey, state: str | None) -> None:
        redis_key = self._key(key, "state")
        if state is None:
            await self.client.delete(redis_key)
        else:
            await self.client.set(redis_key, state, ex=self.ttl)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        value = await self.client.get(self._key(key, "data"))
        if not value:
            return {}
        data = json.loads(value)
        return data if isinstance(data, dict) else {}

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        redis_key = self._key(key, "data")
        if data:
            await self.client.set(
                redis_key, json.dumps(dict(data), ensure_ascii=False), ex=self.ttl
            )
        else:
            await self.client.delete(redis_key)

    async def close(self) -> None:
        close = getattr(self.client, "aclose", None) or getattr(self.client, "close", None)
        if close is not None:
            await close()


__all__ = ["RedisStorage"]
