"""UZ: `MTProtoClient` — foydalanuvchi (yoki bot) akkaunti uchun mustaqil MTProto mijozi.
RU: `MTProtoClient` — независимый MTProto-клиент для пользовательского (или бот) аккаунта.
EN: `MTProtoClient` — a standalone MTProto client for user (or bot) accounts.

    client = MTProtoClient(API_ID, API_HASH, session="me")

    @client.on(events.NewMessage(pattern=r"^\\.ping$", outgoing=True))
    async def ping(event):
        await event.edit("pong")

    await client.start()                  # UZ/RU/EN: telefon, kod, 2FA / phone, code, 2FA
    await client.run_until_disconnected()
"""

from __future__ import annotations

import asyncio
import getpass
import inspect
import logging
import os
import platform
import re
import struct
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any, Literal, TypeVar

from .. import __version__
from .crypto import AuthKey, RSAPublicKey, compute_srp_answer
from .dc import DcOption, DcTable
from .entities import EntityCache, peer_id
from .errors import (
    FloodWaitError,
    MTProtoError,
    NetworkMigrateError,
    PhoneCodeInvalidError,
    PhoneMigrateError,
    SessionPasswordNeededError,
    TransportError,
    UnauthorizedError,
    UserMigrateError,
)
from .events import EventBuilder, Raw, StopPropagation
from .parse import parse_html
from .sender import MTProtoSender
from .session import SessionData, SessionStorage, resolve_session
from .tl import TLObject, functions, schema_layer, types
from .transport import AbridgedCodec, IntermediateCodec, TcpTransport, Transport
from .updates import UpdateProcessor, UpdateState

log = logging.getLogger("zafather.mtproto")

EventCallback = Callable[[Any], Any]
CallbackT = TypeVar("CallbackT", bound=EventCallback)
TransportFactory = Callable[[DcOption], Transport]
Prompt = str | Callable[[], str | Awaitable[str]] | None

_MIGRATIONS = (PhoneMigrateError, UserMigrateError, NetworkMigrateError)
_UPDATE_CONTAINERS = frozenset(
    {
        "updates",
        "updatesCombined",
        "updateShort",
        "updateShortMessage",
        "updateShortChatMessage",
        "updateShortSentMessage",
        "updatesTooLong",
    }
)
_USERNAME_RE = re.compile(r"^(?:@|(?:https?://)?(?:t\.me|telegram\.me)/)?([A-Za-z0-9_]{4,32})/?$")


async def _ask(source: Prompt, text: str, *, secret: bool = False) -> str:
    if isinstance(source, str):
        return source
    if source is not None:
        value = source()
        return str(await value) if inspect.isawaitable(value) else str(value)
    reader = getpass.getpass if secret else input
    return str(await asyncio.to_thread(reader, text))


def _random_id() -> int:
    return int(struct.unpack("<q", os.urandom(8))[0])


class MTProtoClient:
    """UZ: Telegram MTProto mijozi: ulanish, avtorizatsiya, so'rovlar va eventlar.
    RU: MTProto-клиент Telegram: подключение, авторизация, запросы и события.
    EN: A Telegram MTProto client: connection, authorization, requests and events.

    UZ: `api_id`/`api_hash` my.telegram.org saytidan olinadi. `session` — fayl yo'li,
    `SessionStorage` yoki `None` (faqat xotirada). `flood_sleep_threshold` dan qisqa
    FLOOD_WAIT avtomatik kutiladi.
    RU: `api_id`/`api_hash` берутся на my.telegram.org. `session` — путь к файлу,
    `SessionStorage` или `None` (только память). FLOOD_WAIT короче
    `flood_sleep_threshold` ожидается автоматически.
    EN: Get `api_id`/`api_hash` from my.telegram.org. `session` is a file path, a
    `SessionStorage` or `None` (memory only). FLOOD_WAITs shorter than
    `flood_sleep_threshold` are slept through automatically.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session: str | os.PathLike[str] | SessionStorage | None = "zafather_user",
        *,
        test_mode: bool = False,
        device_model: str | None = None,
        system_version: str | None = None,
        app_version: str = __version__,
        lang_code: str = "en",
        system_lang_code: str = "en",
        connection: Literal["abridged", "intermediate"] = "abridged",
        transport_factory: TransportFactory | None = None,
        dc_overrides: Mapping[int, DcOption] | None = None,
        rsa_keys: Iterable[RSAPublicKey] | None = None,
        request_timeout: float = 30.0,
        flood_sleep_threshold: int = 60,
        receive_updates: bool = True,
        ping_interval: float = 60.0,
        reconnect_retries: int = 5,
        reconnect_delay: float = 1.0,
    ) -> None:
        if not isinstance(api_id, int) or isinstance(api_id, bool) or api_id <= 0:
            raise ValueError("api_id must be a positive integer")
        if not isinstance(api_hash, str) or not api_hash.strip():
            raise ValueError("api_hash must not be empty")
        self.api_id = api_id
        self.api_hash = api_hash
        self.storage = resolve_session(session)
        self._data: SessionData = self.storage.load()
        if self._data.auth_keys and self._data.test_mode != test_mode:
            raise ValueError("This session belongs to the other environment (test/production)")
        self._data.test_mode = test_mode
        self.test_mode = test_mode
        self.device_model = device_model or platform.machine() or "PC"
        self.system_version = system_version or f"{platform.system()} {platform.release()}".strip()
        self.app_version = app_version
        self.lang_code = lang_code
        self.system_lang_code = system_lang_code
        self.connection = connection
        self.request_timeout = request_timeout
        self.flood_sleep_threshold = flood_sleep_threshold
        self.receive_updates = receive_updates
        self.ping_interval = ping_interval
        self.reconnect_retries = reconnect_retries
        self.reconnect_delay = reconnect_delay
        self._transport_factory = transport_factory or self._default_transport
        self._rsa_keys = tuple(rsa_keys) if rsa_keys is not None else None
        self._dcs = DcTable(test_mode, dict(dc_overrides or {}))
        self._entities = EntityCache(self._data.entities)
        self._updates = UpdateProcessor(
            self.invoke,
            self._dispatch,
            self._entities.add,
            state=UpdateState.from_dict(self._data.update_state),
            self_id=lambda: self._data.user_id,
            known_user=lambda user_id: self._entities.input_peer(user_id) is not None,
        )
        self._handlers: list[tuple[EventBuilder, EventCallback]] = []
        self._sender: MTProtoSender | None = None
        self._me: TLObject | None = None
        self._phone_code_hashes: dict[str, str] = {}
        self._update_tasks: set[asyncio.Task[None]] = set()
        self._closed: asyncio.Event | None = None
        self._lost_connection = False

    # --- UZ: ulanish / RU: подключение / EN: connection --------------------------------------
    def _default_transport(self, option: DcOption) -> Transport:
        codec = IntermediateCodec() if self.connection == "intermediate" else AbridgedCodec()
        return TcpTransport(option.host, option.port, codec=codec)

    @property
    def connected(self) -> bool:
        """UZ: Server bilan ulanish ochiqmi. RU: Открыто ли соединение с сервером.
        EN: Whether the connection to the server is open.
        """
        return self._sender is not None and self._sender.connected

    @property
    def dc_id(self) -> int:
        """UZ: Joriy data-markaz. RU: Текущий дата-центр. EN: The current data center."""
        return self._data.dc_id

    @property
    def self_id(self) -> int | None:
        """UZ: Kirgan akkaunt ID si (kirilmagan bo'lsa None). RU: ID вошедшего аккаунта
        (None до входа). EN: The logged-in account ID (None before logging in).
        """
        return self._data.user_id

    @property
    def session(self) -> SessionData:
        """UZ: Sessiya ma'lumotlari (kalitlar, DC, holat). RU: Данные сессии (ключи, DC,
        состояние). EN: The session data (keys, DC and update state).
        """
        return self._data

    def _create_sender(self, dc_id: int) -> MTProtoSender:
        option = self._dcs.get(dc_id)
        key = self._data.auth_keys.get(dc_id)
        return MTProtoSender(
            lambda: self._transport_factory(option),
            dc_id=dc_id,
            test_mode=self.test_mode,
            auth_key=AuthKey(key) if key else None,
            rsa_keys=self._rsa_keys,
            on_auth_key=lambda auth_key: self._store_auth_key(dc_id, auth_key),
            on_update=self._on_raw_update,
            on_reconnect=self._on_reconnected,
            on_closed=self._on_connection_lost,
            request_timeout=self.request_timeout,
            ping_interval=self.ping_interval,
            reconnect_retries=self.reconnect_retries,
            reconnect_delay=self.reconnect_delay,
        )

    async def connect(self) -> None:
        """UZ: Joriy DC ga ulanadi (kerak bo'lsa avtorizatsiya kaliti yaratiladi).
        RU: Подключается к текущему DC (при необходимости создаётся ключ авторизации).
        EN: Connects to the current DC (creating an authorization key if needed).
        """
        if self.connected:
            return
        if self._sender is not None:
            # UZ: Ulanishi yo'qolgan eski jo'natuvchini to'liq yopamiz.
            # RU: Полностью закрываем старый отправитель, потерявший соединение.
            # EN: Fully close the previous sender that lost its connection.
            await self._sender.disconnect()
        recovering = self._lost_connection
        self._closed = asyncio.Event()
        self._lost_connection = False
        self._sender = self._create_sender(self._data.dc_id)
        await self._sender.connect()
        await self._init_connection()
        if recovering:
            self._resume_updates()

    async def _on_reconnected(self) -> None:
        await self._init_connection()
        self._resume_updates()

    def _resume_updates(self) -> None:
        # UZ: Uzilish paytida kelgan update'larni olish uchun `getDifference`.
        # RU: `getDifference`, чтобы получить update, пришедшие во время обрыва.
        # EN: `getDifference` to fetch the updates that arrived while we were offline.
        if self.receive_updates and self._data.user_id is not None and self._updates.state.pts:
            self._updates.request_catch_up()

    async def _init_connection(self) -> None:
        sender = self._require_sender()
        query = functions.invokeWithLayer(
            layer=schema_layer(),
            query=functions.initConnection(
                api_id=self.api_id,
                device_model=self.device_model,
                system_version=self.system_version,
                app_version=self.app_version,
                system_lang_code=self.system_lang_code,
                lang_pack="",
                lang_code=self.lang_code,
                query=functions.help.getConfig(),
            ),
        )
        self._dcs.update_from_config(await sender.send(query))

    def _store_auth_key(self, dc_id: int, auth_key: AuthKey | None) -> None:
        if auth_key is None:
            self._data.auth_keys.pop(dc_id, None)
        else:
            self._data.auth_keys[dc_id] = auth_key.key
        self.save()

    def _on_connection_lost(self) -> None:
        self._lost_connection = True
        if self._closed is not None:
            self._closed.set()

    async def disconnect(self) -> None:
        """UZ: Ulanishni yopadi va sessiyani saqlaydi. RU: Закрывает соединение и сохраняет
        сессию. EN: Closes the connection and saves the session.
        """
        await self._updates.close()
        tasks = list(self._update_tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self._sender is not None:
            await self._sender.disconnect()
            self._sender = None
        self.save()
        if self._closed is not None:
            self._closed.set()

    def save(self) -> None:
        """UZ: Sessiyani saqlaydi. RU: Сохраняет сессию. EN: Persists the session."""
        self._data.entities = self._entities.export()
        self._data.update_state = self._updates.state.to_dict()
        self.storage.save(self._data)

    async def run_until_disconnected(self) -> None:
        """UZ: `disconnect()` gacha kutadi; ulanish butunlay yo'qolsa `TransportError`.
        RU: Ждёт до `disconnect()`; при полной потере соединения — `TransportError`.
        EN: Waits until `disconnect()`; raises `TransportError` if the connection is lost.
        """
        if self._closed is None:
            raise TransportError("The client is not connected")
        await self._closed.wait()
        if self._lost_connection:
            raise TransportError("Connection to Telegram was lost")

    def _require_sender(self) -> MTProtoSender:
        if self._sender is None:
            raise TransportError("The client is not connected; call connect() first")
        return self._sender

    async def _switch_dc(self, dc_id: int) -> None:
        log.info("Switching from DC %s to DC %s", self._data.dc_id, dc_id)
        if self._sender is not None:
            await self._sender.disconnect()
        self._data.dc_id = dc_id
        self.save()
        self._sender = self._create_sender(dc_id)
        await self._sender.connect()
        await self._init_connection()

    # --- UZ: so'rovlar / RU: запросы / EN: requests --------------------------------------------
    async def invoke(self, request: TLObject, *, timeout: float | None = None) -> Any:
        """UZ: Istalgan TL funksiyani chaqiradi (DC migratsiyasi va qisqa FLOOD_WAIT avtomatik).
        RU: Вызывает любую TL-функцию (миграция DC и короткий FLOOD_WAIT — автоматически).
        EN: Invokes any TL function (DC migration and short FLOOD_WAITs are automatic).
        """
        if not isinstance(request, TLObject) or not request.is_function:
            raise TypeError("invoke() expects a TL function such as functions.help.getConfig()")
        last_error: BaseException | None = None
        for _ in range(5):
            try:
                result = await self._require_sender().send(request, timeout=timeout)
            except _MIGRATIONS as error:
                last_error = error
                await self._switch_dc(error.new_dc)
                continue
            except FloodWaitError as error:
                if error.seconds > self.flood_sleep_threshold:
                    raise
                last_error = error
                log.info("Sleeping %ss because of FLOOD_WAIT", error.seconds)
                await asyncio.sleep(error.seconds)
                continue
            await self._absorb(result)
            return result
        assert last_error is not None
        raise last_error

    __call__ = invoke

    async def _absorb(self, result: Any) -> None:
        if isinstance(result, list):
            self._entities.add(result)
            return
        if not isinstance(result, TLObject):
            return
        values = result.values
        for key in ("users", "chats"):
            if isinstance(values.get(key), list):
                self._entities.add(values[key])
        if isinstance(values.get("user"), TLObject):
            self._entities.add([values["user"]])
        if result.tl_name in _UPDATE_CONTAINERS:
            await self._updates.feed(result, emit=False)

    # --- UZ: avtorizatsiya / RU: авторизация / EN: authorization -----------------------------
    async def is_user_authorized(self) -> bool:
        """UZ: Sessiya tizimga kirganmi. RU: Авторизована ли сессия. EN: Whether the session
        is logged in.
        """
        try:
            state = await self.invoke(functions.updates.getState())
        except UnauthorizedError:
            return False
        if not self._updates.state.pts:
            self._updates.state.apply(state)
        return True

    async def send_code(self, phone: str) -> TLObject:
        """UZ: Tasdiqlash kodini yuboradi. RU: Отправляет код подтверждения.
        EN: Sends the login code.
        """
        sent = await self.invoke(
            functions.auth.sendCode(
                phone_number=phone,
                api_id=self.api_id,
                api_hash=self.api_hash,
                settings=types.codeSettings(),
            )
        )
        if sent.tl_name == "auth.sentCode":
            self._phone_code_hashes[phone] = sent.phone_code_hash
        return sent

    async def sign_in(
        self, phone: str, code: str, *, phone_code_hash: str | None = None
    ) -> TLObject:
        """UZ: Kod bilan kiradi; 2FA bo'lsa `SessionPasswordNeededError`.
        RU: Входит по коду; при 2FA — `SessionPasswordNeededError`.
        EN: Signs in with the code; raises `SessionPasswordNeededError` when 2FA is on.
        """
        code_hash = phone_code_hash or self._phone_code_hashes.get(phone)
        if code_hash is None:
            raise ValueError("Call send_code() before sign_in()")
        result = await self.invoke(
            functions.auth.signIn(
                phone_number=phone, phone_code_hash=code_hash, phone_code=str(code)
            )
        )
        return await self._complete_login(result)

    async def check_password(self, password: str) -> TLObject:
        """UZ: 2FA parolini SRP orqali tekshiradi (parol serverga yuborilmaydi).
        RU: Проверяет пароль 2FA через SRP (пароль не отправляется на сервер).
        EN: Verifies the 2FA password with SRP (the password never leaves the device).
        """
        info = await self.invoke(functions.account.getPassword())
        algo = info.current_algo
        if not info.has_password or algo is None:
            raise MTProtoError("Two-step verification is not enabled for this account")
        answer = compute_srp_answer(
            password, salt1=algo.salt1, salt2=algo.salt2, g=algo.g, p=algo.p, srp_b=info.srp_B
        )
        check = types.inputCheckPasswordSRP(srp_id=info.srp_id, A=answer.a_bytes, M1=answer.m1)
        return await self._complete_login(
            await self.invoke(functions.auth.checkPassword(password=check))
        )

    async def sign_in_bot(self, token: str) -> TLObject:
        """UZ: Bot tokeni bilan kiradi. RU: Входит по токену бота. EN: Logs in with a bot token."""
        result = await self.invoke(
            functions.auth.importBotAuthorization(
                flags=0, api_id=self.api_id, api_hash=self.api_hash, bot_auth_token=token
            )
        )
        user = await self._complete_login(result)
        self._data.is_bot = True
        self.save()
        return user

    async def _complete_login(self, result: TLObject) -> TLObject:
        if result.tl_name == "auth.authorizationSignUpRequired":
            raise MTProtoError("This phone number is not registered; sign up in an official app")
        user = result.user
        self._me = user
        self._data.user_id = user.id
        self._entities.add([user])
        self.save()
        if self.receive_updates:
            await self._updates.initialize()
        return user

    async def start(
        self,
        phone: Prompt = None,
        *,
        code_callback: Prompt = None,
        password: Prompt = None,
        bot_token: str | None = None,
        catch_up: bool = False,
    ) -> MTProtoClient:
        """UZ: Ulanadi va kerak bo'lsa interaktiv kiradi (telefon, kod, 2FA yoki bot token).
        RU: Подключается и при необходимости интерактивно входит (телефон, код, 2FA или токен).
        EN: Connects and, if needed, logs in interactively (phone, code, 2FA or bot token).

        UZ: `catch_up=True` — oflayn paytdagi update'lar ham qayta ishlanadi.
        RU: `catch_up=True` — обрабатываются и update, пропущенные офлайн.
        EN: `catch_up=True` also processes updates missed while offline.
        """
        await self.connect()
        if await self.is_user_authorized():
            if catch_up:
                await self._updates.catch_up()
            return self
        if bot_token:
            await self.sign_in_bot(bot_token)
            return self
        phone_number = await _ask(phone, "Telefon raqam / Номер телефона / Phone number: ")
        await self.send_code(phone_number)
        await self._sign_in_interactively(phone_number, code_callback, password)
        return self

    async def _sign_in_interactively(
        self, phone: str, code_callback: Prompt, password: Prompt
    ) -> None:
        attempts = 3
        for attempt in range(1, attempts + 1):
            code = await _ask(code_callback, "Kod / Код / Code: ")
            try:
                await self.sign_in(phone, code)
                return
            except SessionPasswordNeededError:
                secret = await _ask(password, "2FA parol / пароль / password: ", secret=True)
                await self.check_password(secret)
                return
            except PhoneCodeInvalidError:
                if attempt == attempts:
                    raise

    async def log_out(self) -> bool:
        """UZ: Sessiyani tugatadi va saqlangan ma'lumotni o'chiradi.
        RU: Завершает сессию и удаляет сохранённые данные.
        EN: Terminates the session and deletes stored data.
        """
        try:
            await self.invoke(functions.auth.logOut())
        finally:
            await self.disconnect()
            self.storage.delete()
            self._data = SessionData(test_mode=self.test_mode)
        return True

    async def get_me(self) -> TLObject:
        """UZ: Joriy akkaunt (`user`). RU: Текущий аккаунт (`user`). EN: The current account."""
        if self._me is None:
            users = await self.invoke(functions.users.getUsers(id=[types.inputUserSelf()]))
            self._me = users[0]
            self._data.user_id = self._me.id
        return self._me

    # --- UZ: entity'lar / RU: сущности / EN: entities ------------------------------------------
    async def get_input_entity(self, entity: int | str | TLObject) -> TLObject:
        """UZ: `"me"`, `@username`, `t.me/...`, belgilangan ID yoki obyekt -> `InputPeer`.
        RU: `"me"`, `@username`, `t.me/...`, помеченный ID или объект -> `InputPeer`.
        EN: `"me"`, `@username`, `t.me/...`, a marked ID or an object -> `InputPeer`.
        """
        if isinstance(entity, TLObject):
            if entity.tl_name.startswith("inputPeer"):
                return entity
            self._entities.add([entity])
            return await self.get_input_entity(peer_id(entity))
        if isinstance(entity, str):
            return await self._resolve_string(entity)
        if entity == self.self_id:
            return types.inputPeerSelf()
        input_peer = self._entities.input_peer(entity)
        if input_peer is None:
            raise ValueError(f"Unknown peer {entity}: send it a message first or use a username")
        return input_peer

    async def _resolve_string(self, value: str) -> TLObject:
        if value.lower() in ("me", "self"):
            return types.inputPeerSelf()
        match = _USERNAME_RE.match(value.strip())
        if match is None:
            raise ValueError(f"Cannot resolve {value!r}: expected a username or a t.me link")
        username = match.group(1)
        cached = self._entities.by_username(username)
        if cached is not None:
            input_peer = self._entities.input_peer(cached.marked_id)
            if input_peer is not None:
                return input_peer
        resolved = await self.invoke(functions.contacts.resolveUsername(username=username))
        return await self.get_input_entity(peer_id(resolved.peer))

    async def get_entity(self, entity: int | str | TLObject) -> TLObject:
        """UZ: To'liq `user`/`chat`/`channel` obyekti. RU: Полный объект `user`/`chat`/`channel`.
        EN: The full `user`/`chat`/`channel` object.
        """
        input_peer = await self.get_input_entity(entity)
        name = input_peer.tl_name
        if name == "inputPeerSelf":
            return await self.get_me()
        if name == "inputPeerUser":
            user = types.inputUser(user_id=input_peer.user_id, access_hash=input_peer.access_hash)
            return (await self.invoke(functions.users.getUsers(id=[user])))[0]
        if name == "inputPeerChat":
            return (await self.invoke(functions.messages.getChats(id=[input_peer.chat_id]))).chats[
                0
            ]
        channel = types.inputChannel(
            channel_id=input_peer.channel_id, access_hash=input_peer.access_hash
        )
        return (await self.invoke(functions.channels.getChannels(id=[channel]))).chats[0]

    def _peer_of(self, input_peer: TLObject) -> TLObject:
        name = input_peer.tl_name
        if name == "inputPeerSelf":
            return types.peerUser(user_id=self.self_id or 0)
        if name == "inputPeerUser":
            return types.peerUser(user_id=input_peer.user_id)
        if name == "inputPeerChat":
            return types.peerChat(chat_id=input_peer.chat_id)
        return types.peerChannel(channel_id=input_peer.channel_id)

    # --- UZ: xabarlar / RU: сообщения / EN: messages -----------------------------------------
    @staticmethod
    def _format(
        text: str, parse_mode: str | None, entities: list[TLObject] | None
    ) -> tuple[str, list[TLObject]]:
        if entities is not None:
            return text, entities
        if parse_mode is None:
            return text, []
        if parse_mode.lower() == "html":
            return parse_html(text)
        raise ValueError(f"Unsupported parse_mode {parse_mode!r}; use 'html' or None")

    async def send_message(
        self,
        entity: int | str | TLObject,
        text: str,
        *,
        reply_to: int | None = None,
        parse_mode: str | None = None,
        entities: list[TLObject] | None = None,
        link_preview: bool = True,
        silent: bool = False,
    ) -> TLObject:
        """UZ: Matnli xabar yuboradi va yuborilgan `message` ni qaytaradi.
        RU: Отправляет текстовое сообщение и возвращает отправленный `message`.
        EN: Sends a text message and returns the sent `message`.
        """
        peer = await self.get_input_entity(entity)
        message, message_entities = self._format(text, parse_mode, entities)
        random_id = _random_id()
        result = await self.invoke(
            functions.messages.sendMessage(
                peer=peer,
                message=message,
                random_id=random_id,
                no_webpage=not link_preview,
                silent=silent,
                reply_to=types.inputReplyToMessage(reply_to_msg_id=reply_to) if reply_to else None,
                entities=message_entities or None,
            )
        )
        if result.tl_name == "updateShortSentMessage":
            optional = {
                "from_id": types.peerUser(user_id=self.self_id) if self.self_id else None,
                "entities": result.entities or message_entities or None,
                "media": result.media,
                "reply_to": (
                    types.messageReplyHeader(reply_to_msg_id=reply_to) if reply_to else None
                ),
            }
            return types.message(
                id=result.id,
                peer_id=self._peer_of(peer),
                date=result.date,
                message=message,
                out=True,
                **{key: value for key, value in optional.items() if value is not None},
            )
        return self._message_from_updates(result, random_id=random_id)

    @staticmethod
    def _message_from_updates(
        result: TLObject, *, random_id: int | None = None, message_id: int | None = None
    ) -> TLObject:
        updates = list(result.values.get("updates") or [])
        if "update" in result.values:
            updates.append(result.update)
        if message_id is None:
            message_id = next(
                (
                    u.id
                    for u in updates
                    if u.tl_name == "updateMessageID" and u.random_id == random_id
                ),
                None,
            )
        for update in updates:
            message = update.values.get("message")
            if isinstance(message, TLObject) and (message_id is None or message.id == message_id):
                return message
        raise MTProtoError(f"The server did not return the message ({result.tl_name})")

    async def edit_message(
        self,
        entity: int | str | TLObject,
        message_id: int,
        text: str,
        *,
        parse_mode: str | None = None,
        entities: list[TLObject] | None = None,
        link_preview: bool = True,
    ) -> TLObject:
        """UZ: Xabarni tahrirlaydi. RU: Редактирует сообщение. EN: Edits a message."""
        peer = await self.get_input_entity(entity)
        message, message_entities = self._format(text, parse_mode, entities)
        result = await self.invoke(
            functions.messages.editMessage(
                peer=peer,
                id=message_id,
                message=message,
                no_webpage=not link_preview,
                entities=message_entities or None,
            )
        )
        return self._message_from_updates(result, message_id=message_id)

    async def delete_messages(
        self, entity: int | str | TLObject, message_ids: Iterable[int], *, revoke: bool = True
    ) -> TLObject:
        """UZ: Xabarlarni o'chiradi. RU: Удаляет сообщения. EN: Deletes messages."""
        peer = await self.get_input_entity(entity)
        ids = list(message_ids)
        if peer.tl_name == "inputPeerChannel":
            channel = types.inputChannel(channel_id=peer.channel_id, access_hash=peer.access_hash)
            return await self.invoke(functions.channels.deleteMessages(channel=channel, id=ids))
        return await self.invoke(functions.messages.deleteMessages(id=ids, revoke=revoke))

    async def get_messages(
        self, entity: int | str | TLObject, limit: int = 20, *, offset_id: int = 0
    ) -> list[TLObject]:
        """UZ: Chat tarixidan oxirgi xabarlar. RU: Последние сообщения из истории чата.
        EN: The latest messages from a chat's history.
        """
        peer = await self.get_input_entity(entity)
        history = await self.invoke(
            functions.messages.getHistory(
                peer=peer,
                offset_id=offset_id,
                offset_date=0,
                add_offset=0,
                limit=limit,
                max_id=0,
                min_id=0,
                hash=0,
            )
        )
        return [message for message in history.messages if message.tl_name != "messageEmpty"]

    # --- UZ: eventlar / RU: события / EN: events ------------------------------------------------
    def on(self, builder: EventBuilder | type[EventBuilder]) -> Callable[[CallbackT], CallbackT]:
        """UZ: Event handleri dekoratori. RU: Декоратор обработчика событий.
        EN: An event handler decorator.
        """
        instance = builder() if isinstance(builder, type) else builder

        def decorator(callback: CallbackT) -> CallbackT:
            self._handlers.append((instance, callback))
            return callback

        return decorator

    def add_event_handler(
        self, callback: EventCallback, builder: EventBuilder | type[EventBuilder] | None = None
    ) -> None:
        """UZ: Handlerni dekoratorsiz qo'shadi (`builder` yo'q bo'lsa — barcha xom update'lar).
        RU: Добавляет обработчик без декоратора (без `builder` — все сырые update).
        EN: Adds a handler without a decorator (no `builder` means every raw update).
        """
        self.on(builder or Raw)(callback)

    def remove_event_handler(
        self, callback: EventCallback, builder: EventBuilder | type[EventBuilder] | None = None
    ) -> int:
        """UZ: Handlerni o'chiradi va o'chirilganlar sonini qaytaradi; `builder` — obyekt
        yoki aniq sinf bo'yicha cheklash.
        RU: Удаляет обработчик и возвращает число удалённых; `builder` — ограничение по
        объекту или точному классу.
        EN: Removes a handler and returns how many were removed; `builder` narrows it to
        that builder object or exact class.
        """

        def matches(registered: EventBuilder) -> bool:
            if builder is None:
                return True
            if isinstance(builder, type):
                return type(registered) is builder
            return registered is builder

        before = len(self._handlers)
        self._handlers = [
            (registered, handler)
            for registered, handler in self._handlers
            if handler is not callback or not matches(registered)
        ]
        return before - len(self._handlers)

    def list_event_handlers(self) -> list[tuple[EventBuilder, EventCallback]]:
        """UZ: Ro'yxatdagi `(builder, callback)` juftliklari. RU: Зарегистрированные пары
        `(builder, callback)`. EN: The registered `(builder, callback)` pairs.
        """
        return list(self._handlers)

    def _on_raw_update(self, update: TLObject) -> None:
        if not self.receive_updates:
            return
        task = asyncio.ensure_future(self._feed(update))
        self._update_tasks.add(task)
        task.add_done_callback(self._update_tasks.discard)

    async def _feed(self, update: TLObject) -> None:
        try:
            await self._updates.feed(update)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Failed to process %s", update.tl_name)

    async def _dispatch(self, update: TLObject) -> None:
        for builder, callback in list(self._handlers):
            event = builder.build(update, self)
            if event is None or not builder.filter(event):
                continue
            try:
                result = callback(event)
                if inspect.isawaitable(result):
                    await result
            except StopPropagation:
                return
            except Exception:
                log.exception("Event handler %s failed", getattr(callback, "__name__", callback))

    # --- UZ: kontekst menejeri / RU: контекстный менеджер / EN: context manager --------------
    async def __aenter__(self) -> MTProtoClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.disconnect()

    def __repr__(self) -> str:
        return f"<MTProtoClient dc={self._data.dc_id} user={self._data.user_id}>"


__all__ = ["MTProtoClient", "TransportFactory"]
