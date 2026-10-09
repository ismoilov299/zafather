"""UZ: Foydalanuvchi, guruh va kanallar keshi hamda peer ID yordamchilari.
RU: Кеш пользователей, групп и каналов и помощники для ID пиров.
EN: A cache of users, groups and channels plus peer ID helpers.

UZ: "Belgilangan" ID: foydalanuvchi — `id`, guruh — `-id`, kanal — `-100...id`.
RU: «Помеченный» ID: пользователь — `id`, группа — `-id`, канал — `-100...id`.
EN: A "marked" ID: user — `id`, group — `-id`, channel — `-100...id`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .tl import TLObject, types

USER, CHAT, CHANNEL = "user", "chat", "channel"
_CHANNEL_OFFSET = 1_000_000_000_000

_USER_TYPES = ("user", "userEmpty")
_CHAT_TYPES = ("chat", "chatEmpty", "chatForbidden")
_CHANNEL_TYPES = ("channel", "channelForbidden")


def marked_id(kind: str, raw_id: int) -> int:
    """UZ: Xom ID'dan belgilangan ID. RU: Помеченный ID из исходного. EN: Marks a raw ID."""
    if kind == USER:
        return raw_id
    if kind == CHAT:
        return -raw_id
    if kind == CHANNEL:
        return -(_CHANNEL_OFFSET + raw_id)
    raise ValueError(f"Unknown peer kind {kind!r}")


def unmark(peer: int) -> tuple[str, int]:
    """UZ: Belgilangan ID -> (tur, xom ID). RU: Помеченный ID -> (тип, исходный ID).
    EN: A marked ID -> (kind, raw ID).
    """
    if peer >= 0:
        return USER, peer
    if peer <= -_CHANNEL_OFFSET:
        return CHANNEL, -peer - _CHANNEL_OFFSET
    return CHAT, -peer


def peer_id(peer: Any) -> int:
    """UZ: `peerUser`, `inputPeerChannel`, `user`, `channel` ... -> belgilangan ID.
    RU: `peerUser`, `inputPeerChannel`, `user`, `channel` ... -> помеченный ID.
    EN: `peerUser`, `inputPeerChannel`, `user`, `channel` ... -> a marked ID.
    """
    if isinstance(peer, int):
        return peer
    if not isinstance(peer, TLObject):
        raise TypeError(f"Cannot get a peer ID from {peer!r}")
    values = peer.values
    if "user_id" in values:
        return marked_id(USER, values["user_id"])
    if "channel_id" in values:
        return marked_id(CHANNEL, values["channel_id"])
    if "chat_id" in values:
        return marked_id(CHAT, values["chat_id"])
    name = peer.tl_name
    if name in _USER_TYPES:
        return marked_id(USER, values["id"])
    if name in _CHAT_TYPES:
        return marked_id(CHAT, values["id"])
    if name in _CHANNEL_TYPES:
        return marked_id(CHANNEL, values["id"])
    raise TypeError(f"{name} is not a peer")


@dataclass
class CachedEntity:
    """UZ: Keshdagi yozuv. RU: Запись кеша. EN: A cache entry."""

    kind: str
    id: int
    access_hash: int | None = None
    username: str | None = None
    min: bool = False

    @property
    def marked_id(self) -> int:
        """UZ: Belgilangan ID. RU: Помеченный ID. EN: The marked ID."""
        return marked_id(self.kind, self.id)

    def to_list(self) -> list[Any]:
        """UZ: Sessiyada saqlash shakli. RU: Форма для хранения в сессии.
        EN: The form stored in the session.
        """
        return [self.kind, self.access_hash, self.username]


class EntityCache:
    """UZ: `access_hash` larni eslab qoladi — ular so'rovlarda peer ko'rsatish uchun kerak.
    RU: Запоминает `access_hash` — они нужны, чтобы указывать пиров в запросах.
    EN: Remembers `access_hash` values, which requests need to address peers.
    """

    def __init__(self, stored: dict[int, list[Any]] | None = None) -> None:
        self._entities: dict[int, CachedEntity] = {}
        for marked, (kind, access_hash, username) in (stored or {}).items():
            _, raw_id = unmark(marked)
            self._entities[marked] = CachedEntity(kind, raw_id, access_hash, username)

    def add(self, entities: Iterable[Any]) -> None:
        """UZ: `user`/`chat`/`channel` obyektlarini keshlaydi. RU: Кеширует объекты.
        EN: Caches `user`/`chat`/`channel` objects.
        """
        for entity in entities:
            if isinstance(entity, TLObject):
                self._add_one(entity)

    def _add_one(self, entity: TLObject) -> None:
        name = entity.tl_name
        if name in _USER_TYPES:
            kind = USER
        elif name in _CHANNEL_TYPES:
            kind = CHANNEL
        elif name in _CHAT_TYPES:
            kind = CHAT
        else:
            return
        values = entity.values
        is_min = bool(values.get("min"))
        cached = CachedEntity(
            kind, values["id"], values.get("access_hash"), values.get("username"), is_min
        )
        existing = self._entities.get(cached.marked_id)
        if existing is not None and is_min and not existing.min:
            existing.username = cached.username or existing.username
            return
        self._entities[cached.marked_id] = cached

    def get(self, peer: int) -> CachedEntity | None:
        """UZ: Belgilangan ID bo'yicha. RU: По помеченному ID. EN: Looks up a marked ID."""
        return self._entities.get(peer)

    def by_username(self, username: str) -> CachedEntity | None:
        """UZ: Username bo'yicha (`@` va registr ahamiyatsiz). RU: По username (`@` и регистр
        не важны). EN: Looks up a username (`@` and case are ignored).
        """
        wanted = username.lstrip("@").lower()
        return next(
            (e for e in self._entities.values() if e.username and e.username.lower() == wanted),
            None,
        )

    def input_peer(self, peer: int) -> TLObject | None:
        """UZ: Belgilangan ID uchun `InputPeer` (hash noma'lum bo'lsa `None`).
        RU: `InputPeer` для помеченного ID (`None`, если hash неизвестен).
        EN: An `InputPeer` for a marked ID (`None` when the hash is unknown).
        """
        kind, raw_id = unmark(peer)
        if kind == CHAT:
            return types.inputPeerChat(chat_id=raw_id)
        entity = self._entities.get(peer)
        if entity is None or entity.access_hash is None:
            return None
        if kind == USER:
            return types.inputPeerUser(user_id=raw_id, access_hash=entity.access_hash)
        return types.inputPeerChannel(channel_id=raw_id, access_hash=entity.access_hash)

    def input_user(self, user_id: int) -> TLObject | None:
        """UZ: `inputUser` (access_hash ma'lum bo'lsa). RU: `inputUser` (если известен
        access_hash). EN: An `inputUser` when the access hash is known.
        """
        entity = self._entities.get(user_id)
        if entity is None or entity.access_hash is None:
            return None
        return types.inputUser(user_id=user_id, access_hash=entity.access_hash)

    def export(self) -> dict[int, list[Any]]:
        """UZ: Sessiyaga yoziladigan to'liq (min bo'lmagan) yozuvlar. RU: Полные (не min)
        записи для сессии. EN: The complete (non-min) entries written to the session.
        """
        return {
            marked: entity.to_list() for marked, entity in self._entities.items() if not entity.min
        }

    def __len__(self) -> int:
        return len(self._entities)

    def __contains__(self, peer: object) -> bool:
        return peer in self._entities


__all__ = [
    "CHANNEL",
    "CHAT",
    "USER",
    "CachedEntity",
    "EntityCache",
    "marked_id",
    "peer_id",
    "unmark",
]
