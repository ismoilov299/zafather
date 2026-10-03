"""UZ: MTProto xatolari: RPC xatolari ierarxiyasi, transport va xavfsizlik xatolari.
RU: Ошибки MTProto: иерархия RPC-ошибок, ошибки транспорта и безопасности.
EN: MTProto errors: the RPC error hierarchy plus transport and security errors.

    try:
        await client.send_message("me", "salom")
    except FloodWaitError as exc:
        await asyncio.sleep(exc.seconds)
"""

from __future__ import annotations

import re
from typing import ClassVar

from ..exceptions import ZafatherError


class MTProtoError(ZafatherError):
    """UZ: MTProto qatlamining asosiy xatosi. RU: Базовая ошибка слоя MTProto.
    EN: Base error of the MTProto layer.
    """


class SecurityError(MTProtoError):
    """UZ: Xabar xavfsizlik tekshiruvidan o'tmadi (buzilgan yoki soxta).
    RU: Сообщение не прошло проверку безопасности (повреждено или подделано).
    EN: A message failed a security check (corrupted or forged).
    """


class TransportError(MTProtoError, ConnectionError):
    """UZ: Transport xatosi yoki server qaytargan transport kodi (masalan, -404).
    RU: Ошибка транспорта или транспортный код сервера (например, -404).
    EN: A transport failure or a transport code returned by the server (e.g. -404).
    """

    def __init__(self, message: str, code: int | None = None) -> None:
        self.code = code
        super().__init__(message)


class AuthKeyNotFoundError(TransportError):
    """UZ: Server bu avtorizatsiya kalitini tanimaydi (-404); yangisi yaratiladi.
    RU: Сервер не знает этот ключ авторизации (-404); будет создан новый.
    EN: The server does not know this authorization key (-404); a new one is created.
    """


class RPCError(MTProtoError):
    """UZ: Server `rpc_error` qaytardi. `code` — HTTP uslubidagi kod, `message` — nomi.
    RU: Сервер вернул `rpc_error`. `code` — код в стиле HTTP, `message` — имя ошибки.
    EN: The server returned `rpc_error`. `code` is HTTP-like, `message` the error name.
    """

    code: ClassVar[int | None] = None

    def __init__(self, error_code: int, message: str, request: str | None = None) -> None:
        self.error_code = error_code
        self.message = message
        self.request = request
        match = re.search(r"_(\d+)$", message)
        self.value: int | None = int(match.group(1)) if match else None
        location = f" (caused by {request})" if request else ""
        super().__init__(f"[{error_code}] {message}{location}")


class SeeOtherError(RPCError):
    code = 303


class BadRequestError(RPCError):
    code = 400


class UnauthorizedError(RPCError):
    code = 401


class ForbiddenError(RPCError):
    code = 403


class NotFoundError(RPCError):
    code = 404


class NotAcceptableError(RPCError):
    code = 406


class FloodError(RPCError):
    code = 420


class InternalServerError(RPCError):
    code = 500


class DCMigrateError(SeeOtherError):
    """UZ: Boshqa data-markazga o'tish kerak (`new_dc`). RU: Нужно перейти в другой DC
    (`new_dc`). EN: The request must be repeated on another data center (`new_dc`).
    """

    @property
    def new_dc(self) -> int:
        return int(self.value or 0)


class PhoneMigrateError(DCMigrateError):
    pass


class UserMigrateError(DCMigrateError):
    pass


class NetworkMigrateError(DCMigrateError):
    pass


class FileMigrateError(DCMigrateError):
    pass


class StatsMigrateError(DCMigrateError):
    pass


class FloodWaitError(FloodError):
    """UZ: `seconds` soniya kutish kerak. RU: Нужно подождать `seconds` секунд.
    EN: Wait `seconds` seconds before retrying.
    """

    @property
    def seconds(self) -> int:
        return int(self.value or 0)


class SlowModeWaitError(FloodWaitError):
    pass


class SessionPasswordNeededError(UnauthorizedError):
    """UZ: Akkauntda 2FA paroli bor. RU: На аккаунте включён пароль 2FA.
    EN: The account has a 2FA password.
    """


class AuthKeyUnregisteredError(UnauthorizedError):
    pass


class SessionRevokedError(UnauthorizedError):
    pass


class UserDeactivatedError(UnauthorizedError):
    pass


class AuthKeyDuplicatedError(NotAcceptableError):
    pass


class PhoneNumberInvalidError(BadRequestError):
    pass


class PhoneCodeInvalidError(BadRequestError):
    pass


class PhoneCodeExpiredError(BadRequestError):
    pass


class PhoneCodeEmptyError(BadRequestError):
    pass


class PhoneNumberUnoccupiedError(BadRequestError):
    pass


class PasswordHashInvalidError(BadRequestError):
    pass


class UsernameNotOccupiedError(BadRequestError):
    pass


class PeerIdInvalidError(BadRequestError):
    pass


class MessageNotModifiedError(BadRequestError):
    pass


_BY_NAME: dict[str, type[RPCError]] = {
    "PHONE_MIGRATE": PhoneMigrateError,
    "USER_MIGRATE": UserMigrateError,
    "NETWORK_MIGRATE": NetworkMigrateError,
    "FILE_MIGRATE": FileMigrateError,
    "STATS_MIGRATE": StatsMigrateError,
    "FLOOD_WAIT": FloodWaitError,
    "FLOOD_PREMIUM_WAIT": FloodWaitError,
    "SLOWMODE_WAIT": SlowModeWaitError,
    "SESSION_PASSWORD_NEEDED": SessionPasswordNeededError,
    "AUTH_KEY_UNREGISTERED": AuthKeyUnregisteredError,
    "SESSION_REVOKED": SessionRevokedError,
    "USER_DEACTIVATED": UserDeactivatedError,
    "USER_DEACTIVATED_BAN": UserDeactivatedError,
    "AUTH_KEY_DUPLICATED": AuthKeyDuplicatedError,
    "PHONE_NUMBER_INVALID": PhoneNumberInvalidError,
    "PHONE_CODE_INVALID": PhoneCodeInvalidError,
    "PHONE_CODE_EXPIRED": PhoneCodeExpiredError,
    "PHONE_CODE_EMPTY": PhoneCodeEmptyError,
    "PHONE_NUMBER_UNOCCUPIED": PhoneNumberUnoccupiedError,
    "PASSWORD_HASH_INVALID": PasswordHashInvalidError,
    "USERNAME_NOT_OCCUPIED": UsernameNotOccupiedError,
    "PEER_ID_INVALID": PeerIdInvalidError,
    "MESSAGE_NOT_MODIFIED": MessageNotModifiedError,
}

_BY_CODE: dict[int, type[RPCError]] = {
    303: SeeOtherError,
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    406: NotAcceptableError,
    420: FloodError,
}


def rpc_error(error_code: int, message: str, request: str | None = None) -> RPCError:
    """UZ: Kod va nomdan mos xato sinfini tanlaydi. RU: Подбирает класс ошибки по коду и имени.
    EN: Picks the matching error class from the code and message.
    """
    name = re.sub(r"_\d+$", "", message)
    error_class = _BY_NAME.get(name) or _BY_CODE.get(error_code)
    if error_class is None:
        error_class = InternalServerError if 500 <= error_code < 600 else RPCError
    return error_class(error_code, message, request)


__all__ = [
    "AuthKeyDuplicatedError",
    "AuthKeyNotFoundError",
    "AuthKeyUnregisteredError",
    "BadRequestError",
    "DCMigrateError",
    "FileMigrateError",
    "FloodError",
    "FloodWaitError",
    "ForbiddenError",
    "InternalServerError",
    "MTProtoError",
    "MessageNotModifiedError",
    "NetworkMigrateError",
    "NotAcceptableError",
    "NotFoundError",
    "PasswordHashInvalidError",
    "PeerIdInvalidError",
    "PhoneCodeEmptyError",
    "PhoneCodeExpiredError",
    "PhoneCodeInvalidError",
    "PhoneMigrateError",
    "PhoneNumberInvalidError",
    "PhoneNumberUnoccupiedError",
    "RPCError",
    "SecurityError",
    "SeeOtherError",
    "SessionPasswordNeededError",
    "SessionRevokedError",
    "SlowModeWaitError",
    "StatsMigrateError",
    "TransportError",
    "UnauthorizedError",
    "UserDeactivatedError",
    "UserMigrateError",
    "UsernameNotOccupiedError",
    "rpc_error",
]
