"""UZ: Zafather xatolari ierarxiyasi.
RU: Иерархия исключений Zafather.
EN: Zafather exception hierarchy.

UZ: Barcha xatolar `ZafatherError` dan meros oladi, shuning uchun bitta
`except ZafatherError` bilan framework xatolarini ushlash mumkin.
RU: Все исключения наследуются от `ZafatherError`, поэтому ошибки фреймворка
можно перехватить одним `except ZafatherError`.
EN: Every exception derives from `ZafatherError`, so a single
`except ZafatherError` catches all framework errors.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar


class ZafatherError(Exception):
    """UZ: Framework xatolarining asosiy sinfi.
    RU: Базовый класс ошибок фреймворка.
    EN: Base class for framework errors.
    """


class OptionalDependencyError(ZafatherError, ImportError):
    """UZ: Ixtiyoriy bog'liqlik o'rnatilmagan (masalan, `cryptography` yoki `redis`).
    RU: Не установлена опциональная зависимость (например, `cryptography` или `redis`).
    EN: An optional dependency is missing (for example `cryptography` or `redis`).
    """

    def __init__(self, package: str, extra: str) -> None:
        self.package = package
        self.extra = extra
        super().__init__(f"'{package}' is required: pip install \"zafather[{extra}]\"")


class NetworkError(ZafatherError):
    """UZ: Tarmoq xatosi: ulanish uzildi, vaqt tugadi yoki javob buzilgan.
    RU: Сетевая ошибка: разрыв соединения, таймаут или повреждённый ответ.
    EN: Network failure: connection reset, timeout or malformed response.

    UZ: `request_sent=False` — so'rov serverga yetib bormagani aniq (masalan, ulanib
    bo'lmadi), shuning uchun uni xavfsiz qayta yuborish mumkin.
    RU: `request_sent=False` — запрос точно не дошёл до сервера (например, не удалось
    подключиться), поэтому его можно безопасно повторить.
    EN: `request_sent=False` means the request certainly never reached the server
    (for example the connection failed), so it is safe to resend.
    """

    def __init__(self, message: str, *, request_sent: bool = True) -> None:
        self.request_sent = request_sent
        super().__init__(message)


class TelegramAPIError(ZafatherError):
    """UZ: Bot API `ok=false` javobi. `code` — HTTP uslubidagi xato kodi.
    RU: Ответ Bot API с `ok=false`. `code` — код ошибки в стиле HTTP.
    EN: A Bot API response with `ok=false`. `code` is an HTTP-style error code.
    """

    status_code: ClassVar[int | None] = None

    def __init__(
        self,
        method: str,
        code: int,
        description: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        self.method = method
        self.code = code
        self.description = description
        self.parameters: dict[str, Any] = dict(parameters or {})
        super().__init__(f"[{code}] {method}: {description}")

    @property
    def retry_after(self) -> int | None:
        """UZ: Kutish vaqti (soniya), bo'lsa. RU: Время ожидания (секунды), если есть.
        EN: Seconds to wait, when the server sent `retry_after`.
        """
        value = self.parameters.get("retry_after")
        return int(value) if isinstance(value, (int, float)) else None

    @property
    def migrate_to_chat_id(self) -> int | None:
        """UZ: Superguruhning yangi ID'si. RU: Новый ID супергруппы.
        EN: The new supergroup ID, when the server sent it.
        """
        value = self.parameters.get("migrate_to_chat_id")
        return int(value) if isinstance(value, int) else None


class BadRequest(TelegramAPIError):
    """UZ: 400 — noto'g'ri so'rov. RU: 400 — неверный запрос. EN: 400 — bad request."""

    status_code = 400


class MigrateToChat(BadRequest):
    """UZ: Guruh superguruhga aylandi — `migrate_to_chat_id` ga yozing.
    RU: Группа стала супергруппой — используйте `migrate_to_chat_id`.
    EN: The group was upgraded to a supergroup — use `migrate_to_chat_id`.
    """


class Unauthorized(TelegramAPIError):
    """UZ: 401 — token noto'g'ri. RU: 401 — неверный токен. EN: 401 — invalid token."""

    status_code = 401


class Forbidden(TelegramAPIError):
    """UZ: 403 — ruxsat yo'q (masalan, bot bloklangan).
    RU: 403 — доступ запрещён (например, бот заблокирован).
    EN: 403 — forbidden (for example, the bot was blocked).
    """

    status_code = 403


class NotFound(TelegramAPIError):
    """UZ: 404 — topilmadi. RU: 404 — не найдено. EN: 404 — not found."""

    status_code = 404


class Conflict(TelegramAPIError):
    """UZ: 409 — boshqa polling yoki webhook faol.
    RU: 409 — активен другой polling или webhook.
    EN: 409 — another polling instance or a webhook is active.
    """

    status_code = 409


class EntityTooLarge(TelegramAPIError):
    """UZ: 413 — fayl juda katta. RU: 413 — файл слишком большой. EN: 413 — file too large."""

    status_code = 413


class RetryAfter(TelegramAPIError):
    """UZ: 429 — flood limit; `retry_after` soniya kutish kerak.
    RU: 429 — flood limit; нужно подождать `retry_after` секунд.
    EN: 429 — flood limit; wait `retry_after` seconds.
    """

    status_code = 429


class ServerError(TelegramAPIError):
    """UZ: 5xx — Telegram server xatosi. RU: 5xx — ошибка сервера Telegram.
    EN: 5xx — Telegram server error.
    """


_ERRORS_BY_CODE: Mapping[int, type[TelegramAPIError]] = {
    cls.status_code: cls
    for cls in (BadRequest, Unauthorized, Forbidden, NotFound, Conflict, EntityTooLarge, RetryAfter)
    if cls.status_code is not None
}


def api_error_from_response(method: str, response: Mapping[str, Any]) -> TelegramAPIError:
    """UZ: Bot API xato javobidan mos xato sinfini yaratadi.
    RU: Создаёт подходящее исключение из ответа Bot API с ошибкой.
    EN: Builds the matching exception from a failed Bot API response.
    """
    code = int(response.get("error_code") or 0)
    description = str(response.get("description") or "")
    parameters = response.get("parameters") or {}
    if code >= 500:
        error_class: type[TelegramAPIError] = ServerError
    elif code == 400 and "migrate_to_chat_id" in parameters:
        error_class = MigrateToChat
    else:
        error_class = _ERRORS_BY_CODE.get(code, TelegramAPIError)
    return error_class(method, code, description, parameters)


#: UZ: Eski nom (0.4.x) — `TelegramAPIError` bilan bir xil.
#: RU: Старое имя (0.4.x) — то же самое, что `TelegramAPIError`.
#: EN: Legacy name (0.4.x) — identical to `TelegramAPIError`.
TelegramError = TelegramAPIError

__all__ = [
    "BadRequest",
    "Conflict",
    "EntityTooLarge",
    "Forbidden",
    "MigrateToChat",
    "NetworkError",
    "NotFound",
    "OptionalDependencyError",
    "RetryAfter",
    "ServerError",
    "TelegramAPIError",
    "TelegramError",
    "Unauthorized",
    "ZafatherError",
    "api_error_from_response",
]
