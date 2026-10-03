"""UZ: Zafather MTProto qatlami — userbot va past darajadagi Telegram API mijozi.
RU: Слой MTProto Zafather — userbot и низкоуровневый клиент Telegram API.
EN: The Zafather MTProto layer — userbots and a low-level Telegram API client.

UZ: `pip install "zafather[userbot]"` (AES uchun `cryptography`) kerak.
RU: Требуется `pip install "zafather[userbot]"` (`cryptography` для AES).
EN: Requires `pip install "zafather[userbot]"` (`cryptography` for AES).

::

    from zafather.mtproto import MTProtoClient, events, functions, types

    client = MTProtoClient(API_ID, API_HASH, session="me")
    await client.start()
    await client.send_message("me", "<b>Salom</b>", parse_mode="html")
    config = await client.invoke(functions.help.getConfig())
"""

from . import events
from .client import MTProtoClient
from .crypto import AuthKey, RSAPublicKey
from .dc import DcOption
from .entities import EntityCache, marked_id, peer_id, unmark
from .errors import (
    AuthKeyUnregisteredError,
    BadRequestError,
    DCMigrateError,
    FloodWaitError,
    MTProtoError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    RPCError,
    SecurityError,
    SessionPasswordNeededError,
    TransportError,
    UnauthorizedError,
)
from .events import (
    CallbackQuery,
    EventBuilder,
    Events,
    MessageDeleted,
    MessageEdited,
    NewMessage,
    Raw,
)
from .parse import parse_html
from .session import FileSession, MemorySession, SessionData, SessionStorage, StringSession
from .tl import TLObject, TLReader, TLSchema, TLSerializer, TLWriter, functions, schema_layer, types
from .transport import AbridgedCodec, IntermediateCodec, TcpTransport, Transport

__all__ = [
    "AbridgedCodec",
    "AuthKey",
    "AuthKeyUnregisteredError",
    "BadRequestError",
    "CallbackQuery",
    "DCMigrateError",
    "DcOption",
    "EntityCache",
    "EventBuilder",
    "Events",
    "FileSession",
    "FloodWaitError",
    "IntermediateCodec",
    "MTProtoClient",
    "MTProtoError",
    "MemorySession",
    "MessageDeleted",
    "MessageEdited",
    "NewMessage",
    "PasswordHashInvalidError",
    "PhoneCodeExpiredError",
    "PhoneCodeInvalidError",
    "PhoneNumberInvalidError",
    "RPCError",
    "RSAPublicKey",
    "Raw",
    "SecurityError",
    "SessionData",
    "SessionPasswordNeededError",
    "SessionStorage",
    "StringSession",
    "TLObject",
    "TLReader",
    "TLSchema",
    "TLSerializer",
    "TLWriter",
    "TcpTransport",
    "Transport",
    "TransportError",
    "UnauthorizedError",
    "events",
    "functions",
    "marked_id",
    "parse_html",
    "peer_id",
    "schema_layer",
    "types",
    "unmark",
]
