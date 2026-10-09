"""UZ: Sessiya saqlash usullari: xotira, JSON fayl va satr (string).
RU: Способы хранения сессии: память, JSON-файл и строка.
EN: Session storages: memory, a JSON file and a portable string.
"""

from __future__ import annotations

import base64
import contextlib
import copy
import json
import logging
import os
import zlib
from pathlib import Path

from .base import SessionData, SessionStorage

log = logging.getLogger("zafather.mtproto.session")


class MemorySession(SessionStorage):
    """UZ: Faqat xotirada (jarayon tugasa yo'qoladi). RU: Только в памяти (теряется при выходе).
    EN: Memory only (lost when the process exits).
    """

    def __init__(self, data: SessionData | None = None) -> None:
        self._data = data or SessionData()

    def load(self) -> SessionData:
        return copy.deepcopy(self._data)

    def save(self, data: SessionData) -> None:
        self._data = copy.deepcopy(data)

    def delete(self) -> None:
        self._data = SessionData()


class FileSession(SessionStorage):
    """UZ: JSON faylga atomik yozadi, fayl huquqlari `0600`.
    RU: Атомарно пишет в JSON-файл с правами `0600`.
    EN: Writes a JSON file atomically with `0600` permissions.

    UZ: Kengaytmasiz nomga `.session.json` qo'shiladi (`"me"` -> `me.session.json`).
    RU: К имени без расширения добавляется `.session.json` (`"me"` -> `me.session.json`).
    EN: A name without an extension gets `.session.json` (`"me"` -> `me.session.json`).
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        target = Path(path)
        self.path = target if target.suffix else target.with_name(target.name + ".session.json")

    def load(self) -> SessionData:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return SessionData()
        except (OSError, ValueError) as exc:
            log.warning("Ignoring unreadable session file %s: %s", self.path, exc)
            return SessionData()
        if not isinstance(raw, dict):
            return SessionData()
        if "auth_keys" not in raw and raw.get("auth_key"):
            raw["auth_keys"] = {str(raw.get("dc_id") or 2): raw["auth_key"]}
        return SessionData.from_dict(raw)

    def save(self, data: SessionData) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data.to_dict(), stream)
        os.replace(temporary, self.path)
        with contextlib.suppress(OSError):
            os.chmod(self.path, 0o600)

    def delete(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.path.unlink()


class StringSession(SessionStorage):
    """UZ: Sessiyani bitta satrga joylaydi (masalan, muhit o'zgaruvchisida saqlash uchun).
    RU: Упаковывает сессию в одну строку (например, для переменной окружения).
    EN: Packs the session into a single string (for example an environment variable).

        session = StringSession(os.getenv("SESSION"))
        ...
        print(session.value)   # UZ/RU/EN: nusxa oling / скопируйте / copy it
    """

    PREFIX = "1"

    def __init__(self, value: str | None = None) -> None:
        self.value = value or ""

    @classmethod
    def encode(cls, data: SessionData) -> str:
        """UZ: Sessiyani satrga aylantiradi (entity keshisiz). RU: Превращает сессию в строку
        (без кэша сущностей). EN: Turns a session into a string (without the entity cache).
        """
        payload = json.dumps(data.to_dict(include_entities=False), separators=(",", ":"))
        packed = base64.urlsafe_b64encode(zlib.compress(payload.encode("utf-8"))).decode("ascii")
        return cls.PREFIX + packed

    @classmethod
    def decode(cls, value: str) -> SessionData:
        """UZ: Satrdan sessiyani tiklaydi. RU: Восстанавливает сессию из строки.
        EN: Restores a session from a string.
        """
        if not value.startswith(cls.PREFIX):
            raise ValueError("Unsupported session string version")
        raw = zlib.decompress(base64.urlsafe_b64decode(value[len(cls.PREFIX) :].encode("ascii")))
        return SessionData.from_dict(json.loads(raw))

    def load(self) -> SessionData:
        return self.decode(self.value) if self.value else SessionData()

    def save(self, data: SessionData) -> None:
        self.value = self.encode(data)

    def delete(self) -> None:
        self.value = ""


def resolve_session(session: str | os.PathLike[str] | SessionStorage | None) -> SessionStorage:
    """UZ: Satr/yo'l -> `FileSession`, `None` -> `MemorySession`.
    RU: Строка/путь -> `FileSession`, `None` -> `MemorySession`.
    EN: A string/path becomes a `FileSession`, `None` a `MemorySession`.
    """
    if session is None:
        return MemorySession()
    if isinstance(session, SessionStorage):
        return session
    return FileSession(session)


__all__ = ["FileSession", "MemorySession", "StringSession", "resolve_session"]
