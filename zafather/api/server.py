"""UZ: Bot API server manzillari.
RU: Адреса сервера Bot API.
EN: Bot API server addresses.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramAPIServer:
    """UZ: Bot API server manzili (rasmiy, lokal yoki test muhit).
    RU: Адрес сервера Bot API (официальный, локальный или тестовая среда).
    EN: Bot API server address (official, local or the test environment).

    UZ: `is_local=True` — o'z Bot API serveringiz (`--local` rejimi): fayl yo'llari
    lokal fayl tizimiga ishora qiladi.
    RU: `is_local=True` — собственный сервер Bot API (режим `--local`): пути файлов
    указывают на локальную файловую систему.
    EN: `is_local=True` means a self-hosted Bot API server (`--local` mode): file
    paths point to the local file system.
    """

    base: str = "https://api.telegram.org"
    is_local: bool = False
    test_environment: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "base", self.base.rstrip("/"))

    @property
    def _environment(self) -> str:
        return "/test" if self.test_environment else ""

    def method_url(self, token: str, method: str) -> str:
        return f"{self.base}/bot{token}{self._environment}/{method}"

    def file_url(self, token: str, file_path: str) -> str:
        return f"{self.base}/file/bot{token}{self._environment}/{file_path.lstrip('/')}"


#: UZ: Rasmiy server. RU: Официальный сервер. EN: The official server.
PRODUCTION = TelegramAPIServer()

__all__ = ["PRODUCTION", "TelegramAPIServer"]
