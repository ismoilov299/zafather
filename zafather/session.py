"""UZ: MTProto session holatini saqlash.
RU: Хранение состояния MTProto-сессии.
EN: MTProto session state persistence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Optional


class MTProtoSession:
    """UZ/RU/EN: Auth key va DC holatini atomic JSON faylga saqlaydi."""

    def __init__(self, path: str = "zafather_user.session.json") -> None:
        self.path = Path(path)
        self.auth_key: Optional[bytes] = None
        self.dc_id: Optional[int] = None
        self.server_salt: Optional[int] = None
        self.user_id: Optional[int] = None

    @property
    def auth_key_id(self) -> Optional[bytes]:
        if self.auth_key is None:
            return None
        return hashlib.sha1(self.auth_key).digest()[-8:]

    def load(self) -> "MTProtoSession":
        if not self.path.exists():
            return self
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            encoded_key = payload.get("auth_key")
            self.auth_key = base64.b64decode(encoded_key) if encoded_key else None
            self.dc_id = payload.get("dc_id")
            self.server_salt = payload.get("server_salt")
            self.user_id = payload.get("user_id")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.clear()
        return self

    def save(self) -> "MTProtoSession":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "auth_key": base64.b64encode(self.auth_key).decode("ascii") if self.auth_key else None,
            "dc_id": self.dc_id,
            "server_salt": self.server_salt,
            "user_id": self.user_id,
        }
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(temporary, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return self

    def clear(self) -> None:
        self.auth_key = None
        self.dc_id = None
        self.server_salt = None
        self.user_id = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


__all__ = ["MTProtoSession"]
