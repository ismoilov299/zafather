"""UZ: Userbot sessiyasi: avtorizatsiya kalitlari, DC, foydalanuvchi va kesh.
RU: Сессия userbot: ключи авторизации, DC, пользователь и кеш.
EN: A userbot session: authorization keys, DC, user and cache.

UZ: Sessiya fayli akkauntga to'liq kirish beradi — uni maxfiy saqlang.
RU: Файл сессии даёт полный доступ к аккаунту — храните его в секрете.
EN: A session grants full access to the account — keep it secret.
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

#: UZ: Yangi sessiya uchun boshlang'ich DC. RU: Начальный DC новой сессии.
#: EN: The initial DC of a new session.
DEFAULT_DC = 2


@dataclass
class SessionData:
    """UZ: Sessiya holati. RU: Состояние сессии. EN: Session state."""

    dc_id: int = DEFAULT_DC
    test_mode: bool = False
    auth_keys: dict[int, bytes] = field(default_factory=dict)
    user_id: int | None = None
    is_bot: bool = False
    update_state: dict[str, int] = field(default_factory=dict)
    entities: dict[int, list[Any]] = field(default_factory=dict)

    @property
    def auth_key(self) -> bytes | None:
        return self.auth_keys.get(self.dc_id)

    def to_dict(self, *, include_entities: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "version": 1,
            "dc_id": self.dc_id,
            "test_mode": self.test_mode,
            "auth_keys": {
                str(dc): base64.b64encode(key).decode("ascii") for dc, key in self.auth_keys.items()
            },
            "user_id": self.user_id,
            "is_bot": self.is_bot,
            "update_state": dict(self.update_state),
        }
        if include_entities:
            data["entities"] = {str(peer): value for peer, value in self.entities.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionData:
        return cls(
            dc_id=int(data.get("dc_id") or DEFAULT_DC),
            test_mode=bool(data.get("test_mode", False)),
            auth_keys={
                int(dc): base64.b64decode(key) for dc, key in (data.get("auth_keys") or {}).items()
            },
            user_id=data.get("user_id"),
            is_bot=bool(data.get("is_bot", False)),
            update_state={k: int(v) for k, v in (data.get("update_state") or {}).items()},
            entities={int(peer): list(v) for peer, v in (data.get("entities") or {}).items()},
        )


class SessionStorage(ABC):
    """UZ: Sessiyani saqlash interfeysi. RU: Интерфейс хранения сессии.
    EN: Session persistence interface.
    """

    @abstractmethod
    def load(self) -> SessionData:
        """UZ: Sessiyani o'qiydi (yo'q bo'lsa — yangisi). RU: Читает сессию (или новую).
        EN: Loads the session (or returns a fresh one).
        """

    @abstractmethod
    def save(self, data: SessionData) -> None:
        """UZ: Sessiyani saqlaydi. RU: Сохраняет сессию. EN: Persists the session."""

    def delete(self) -> None:  # noqa: B027
        """UZ: Sessiyani o'chiradi. RU: Удаляет сессию. EN: Deletes the session."""


__all__ = ["DEFAULT_DC", "SessionData", "SessionStorage"]
