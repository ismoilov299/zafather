"""UZ: Testlar uchun MTProto server: kalit almashinuvi, shifrlash va RPC javoblari.
RU: MTProto-сервер для тестов: обмен ключами, шифрование и ответы RPC.
EN: An MTProto server for tests: key exchange, encryption and RPC answers.

UZ: Server tomoni mijoz kodidan mustaqil formulalar bilan yozilgan (masalan, SRP uchun
S = (A * v^u)^b), shuning uchun mos javob mijoz matematikasini haqiqatan tekshiradi.
RU: Серверная сторона написана независимыми формулами (например, для SRP
S = (A * v^u)^b), поэтому совпадение реально проверяет математику клиента.
EN: The server side uses independent formulas (for SRP, S = (A * v^u)^b), so matching
results genuinely validate the client's math.
"""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import hashlib
import os
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from zafather.mtproto.crypto import (
    TELEGRAM_DH_PRIME,
    AuthKey,
    RSAPublicKey,
    aes_ige_decrypt,
    aes_ige_encrypt,
    password_hash,
)
from zafather.mtproto.tl import TLObject, TLReader, TLWriter, default_schema, default_serializer
from zafather.mtproto.transport import AbridgedCodec, IntermediateCodec

P, Q = 1229739323, 1402015859
G = 3
SERIALIZER = default_serializer()
SCHEMA = default_schema()


class RPCFailure(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def zero_value(type_: Any, depth: int = 0) -> Any:
    name = type_.name
    if name in ("int", "long"):
        return 0
    if name == "double":
        return 0.0
    if name == "string":
        return ""
    if name == "bytes":
        return b""
    if name == "int128":
        return bytes(16)
    if name == "int256":
        return bytes(32)
    if name == "Bool":
        return False
    if type_.is_vector:
        return []
    if depth > 4:
        raise RuntimeError(f"Cannot build a zero value for {type_}")
    candidates = [d for d in SCHEMA.constructors.values() if d.result.name == name]
    definition = min(candidates, key=lambda d: sum(p.required for p in d.params))
    return build(definition.name, _depth=depth + 1)


def build(name: str, _depth: int = 0, **values: Any) -> TLObject:
    """UZ/RU/EN: Fills required fields with zero values."""
    definition = SCHEMA.constructor(name)
    filled = {
        param.name: zero_value(param.type, _depth)
        for param in definition.params
        if param.required and param.name not in values
    }
    filled.update(values)
    return TLObject(definition, filled)


def tl_int(value: int) -> bytes:
    return value.to_bytes((value.bit_length() + 7) // 8, "big")


@dataclass
class Account:
    user_id: int = 1000
    phone: str = "998901234567"
    code: str = "12345"
    password: str | None = None
    first_name: str = "Ali"
    username: str = "ali"
    is_bot: bool = False

    def user(self) -> TLObject:
        return build(
            "user",
            id=self.user_id,
            access_hash=777,
            first_name=self.first_name,
            username=self.username,
            phone=self.phone,
            bot=self.is_bot,
            bot_info_version=1 if self.is_bot else None,
            self=True,
        )


@dataclass
class SRPState:
    salt1: bytes
    salt2: bytes
    b: int
    srp_id: int
    srp_b: int


@dataclass
class Connection:
    writer: asyncio.StreamWriter
    codec: Any
    auth_key: AuthKey | None = None
    session_id: int | None = None
    sequence: int = 0
    handshake: dict[str, Any] = field(default_factory=dict)


class FakeTelegramServer:
    """UZ/RU/EN: An in-process MTProto server bound to 127.0.0.1."""

    def __init__(self, rsa_key: Any, account: Account | None = None, *, dc_id: int = 2) -> None:
        numbers = rsa_key.private_numbers()
        self.private_d = numbers.d
        self.public = RSAPublicKey(numbers.public_numbers.n, numbers.public_numbers.e)
        self.account = account or Account()
        self.dc_id = dc_id
        self.key_dcs: dict[bytes, int] = {}
        self.salt = struct.unpack("<q", os.urandom(8))[0]
        self.auth_keys: dict[bytes, AuthKey] = {}
        self.authorized: set[bytes] = set()
        self.requests: list[TLObject] = []
        self.handlers: dict[str, Callable[[Connection, TLObject], Any]] = {}
        self.connections: list[Connection] = []
        self.pts = 1
        self.next_message_id = 1
        self.history: list[tuple[int, TLObject, TLObject]] = []
        self.srp: SRPState | None = None
        self.send_bad_salt_once = False
        self.gzip_results = False
        self.migrate_to: int | None = None
        self.port = 0
        self._server: asyncio.AbstractServer | None = None
        self._msg_counter = 0
        self._register_defaults()

    # --- lifecycle ---------------------------------------------------------------------
    async def start(self) -> None:
        self._server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for connection in self.connections:
            connection.writer.close()
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()

    def drop_connections(self) -> None:
        for connection in self.connections:
            connection.writer.close()
        self.connections.clear()

    # --- framing -----------------------------------------------------------------------
    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        tag = await reader.readexactly(1)
        if tag == b"\xef":
            codec: Any = AbridgedCodec()
        else:
            await reader.readexactly(3)
            codec = IntermediateCodec()
        connection = Connection(writer, codec)
        self.connections.append(connection)
        try:
            while True:
                packet = await codec.read_frame(reader)
                await self._dispatch(connection, packet)
        except (asyncio.IncompleteReadError, ConnectionError):
            return
        finally:
            with contextlib.suppress(ValueError):
                self.connections.remove(connection)

    async def _write(self, connection: Connection, packet: bytes) -> None:
        connection.writer.write(connection.codec.encode(packet))
        await connection.writer.drain()

    async def _dispatch(self, connection: Connection, packet: bytes) -> None:
        auth_key_id = packet[:8]
        if auth_key_id == bytes(8):
            await self._plain(connection, packet)
            return
        auth_key = self.auth_keys.get(auth_key_id)
        if auth_key is None:
            await self._write(connection, struct.pack("<i", -404))
            return
        connection.auth_key = auth_key
        plaintext = auth_key.decrypt(packet, from_client=True)
        salt, session_id, msg_id, _seq_no, length = struct.unpack_from("<qqqii", plaintext)
        body = plaintext[32 : 32 + length]
        if connection.session_id != session_id:
            connection.session_id = session_id
            connection.sequence = 0
            await self._send(
                connection,
                build(
                    "new_session_created", first_msg_id=msg_id, unique_id=1, server_salt=self.salt
                ),
            )
        if self.send_bad_salt_once and salt != 0:
            self.send_bad_salt_once = False
            self.salt = struct.unpack("<q", os.urandom(8))[0]
            notice = build(
                "bad_server_salt",
                bad_msg_id=msg_id,
                bad_msg_seqno=0,
                error_code=48,
                new_server_salt=self.salt,
            )
            await self._send(connection, notice, content=False)
            return
        request = (
            SERIALIZER.deserialize(body) if body[:4] != struct.pack("<I", 0x62D6B459) else None
        )
        if request is None:
            return
        await self._rpc(connection, msg_id, request)

    # --- encrypted replies -------------------------------------------------------------
    def _server_msg_id(self, response: bool) -> int:
        self._msg_counter += 1
        return (int(time.time()) << 32) | (self._msg_counter << 2) | (1 if response else 3)

    async def _send_raw(self, connection: Connection, body: bytes, *, content: bool = True) -> int:
        assert connection.auth_key is not None and connection.session_id is not None
        seq_no = connection.sequence * 2 + (1 if content else 0)
        if content:
            connection.sequence += 1
        msg_id = self._server_msg_id(response=True)
        header = struct.pack("<qqqii", self.salt, connection.session_id, msg_id, seq_no, len(body))
        data = header + body
        data += os.urandom(-(len(data) + 12) % 16 + 12)
        await self._write(connection, connection.auth_key.encrypt(data, from_client=False))
        return msg_id

    async def _send(self, connection: Connection, obj: TLObject, *, content: bool = True) -> int:
        return await self._send_raw(connection, SERIALIZER.serialize(obj), content=content)

    async def push(self, update: TLObject) -> None:
        """Sends an update to every authorized connection."""
        for connection in list(self.connections):
            if connection.auth_key is not None and connection.session_id is not None:
                await self._send(connection, update)

    async def push_incoming(
        self, text: str, *, user_id: int = 2000, short: bool = True
    ) -> TLObject:
        """Simulates a private message from another user."""
        return await self.push_message(text, user_id=user_id, short=short)

    async def push_outgoing(
        self, text: str, *, user_id: int = 2000, short: bool = True
    ) -> TLObject:
        """Simulates a message the account sent to `user_id` from another device."""
        return await self.push_message(text, user_id=user_id, short=short, out=True)

    async def push_message(
        self, text: str, *, user_id: int = 2000, short: bool = True, out: bool = False
    ) -> TLObject:
        """Pushes a private-chat message update, keeping pts and history consistent."""
        self.pts += 1
        message = build(
            "message",
            id=self.next_message_id,
            peer_id=build("peerUser", user_id=user_id),
            from_id=build("peerUser", user_id=self.account.user_id) if out else None,
            date=int(time.time()),
            message=text,
            out=out,
        )
        self.next_message_id += 1
        sender = build("user", id=user_id, access_hash=555, first_name="Vali", username="vali")
        self.history.append((self.pts, message, sender))
        if short:
            update = build(
                "updateShortMessage",
                out=out,
                id=message.id,
                user_id=user_id,
                message=text,
                pts=self.pts,
                pts_count=1,
                date=message.date,
            )
        else:
            new_message = build("updateNewMessage", message=message, pts=self.pts, pts_count=1)
            update = build(
                "updates", updates=[new_message], users=[sender], chats=[], date=0, seq=0
            )
        await self.push(update)
        return message

    async def _rpc(self, connection: Connection, msg_id: int, request: TLObject) -> None:
        self.requests.append(request)
        inner = request
        while isinstance(inner.values.get("query"), TLObject):
            inner = inner.values["query"]
        if inner.tl_name == "ping_delay_disconnect" or inner.tl_name == "ping":
            await self._send(
                connection, build("pong", msg_id=msg_id, ping_id=inner.ping_id), content=False
            )
            return
        handler = self.handlers.get(inner.tl_name)
        try:
            if handler is None:
                raise RPCFailure(400, "METHOD_NOT_IMPLEMENTED_IN_FAKE")
            result = handler(connection, inner)
            if asyncio.iscoroutine(result):
                result = await result
            payload = _serialize_result(result)
        except RPCFailure as failure:
            payload = SERIALIZER.serialize(
                build("rpc_error", error_code=failure.code, error_message=failure.message)
            )
        if self.gzip_results:
            payload = TLWriter().uint32(0x3072CFA1).bytes(gzip.compress(payload)).to_bytes()
        body = struct.pack("<Iq", 0xF35C6D01, msg_id) + payload
        if self.gzip_results:
            container = TLWriter().uint32(0x73F1F8DC).int32(1)
            inner_msg_id = self._server_msg_id(response=True)
            container.int64(inner_msg_id).int32(connection.sequence * 2 + 1).int32(len(body)).raw(
                body
            )
            connection.sequence += 1
            await self._send_raw(connection, container.to_bytes(), content=False)
        else:
            await self._send_raw(connection, body)

    # --- plain handshake ---------------------------------------------------------------
    async def _plain(self, connection: Connection, packet: bytes) -> None:
        body = packet[20:]
        request = SERIALIZER.deserialize(body)
        handshake = connection.handshake
        if request.tl_name == "req_pq_multi":
            handshake["nonce"] = request.nonce
            handshake["server_nonce"] = os.urandom(16)
            reply = build(
                "resPQ",
                nonce=request.nonce,
                server_nonce=handshake["server_nonce"],
                pq=tl_int(P * Q),
                server_public_key_fingerprints=[12345, self.public.fingerprint],
            )
        elif request.tl_name == "req_DH_params":
            reply = self._req_dh_params(handshake, request)
        elif request.tl_name == "set_client_DH_params":
            reply = self._set_client_dh(handshake, request)
        else:
            raise AssertionError(request.tl_name)
        data = SERIALIZER.serialize(reply)
        msg_id = self._server_msg_id(response=True)
        await self._write(connection, struct.pack("<qqi", 0, msg_id, len(data)) + data)

    def _req_dh_params(self, handshake: dict[str, Any], request: TLObject) -> TLObject:
        assert request.nonce == handshake["nonce"]
        assert request.public_key_fingerprint == self.public.fingerprint
        assert int.from_bytes(request.p, "big") == P and int.from_bytes(request.q, "big") == Q
        cipher = int.from_bytes(request.encrypted_data, "big")
        key_aes_encrypted = pow(cipher, self.private_d, self.public.n).to_bytes(256, "big")
        temp_key_xor, aes_encrypted = key_aes_encrypted[:32], key_aes_encrypted[32:]
        temp_key = bytes(
            a ^ b for a, b in zip(temp_key_xor, hashlib.sha256(aes_encrypted).digest(), strict=True)
        )
        data_with_hash = aes_ige_decrypt(aes_encrypted, temp_key, bytes(32))
        data_with_padding = data_with_hash[:192][::-1]
        assert hashlib.sha256(temp_key + data_with_padding).digest() == data_with_hash[192:]
        inner = SERIALIZER.read(
            TLReader(data_with_padding), SCHEMA.constructor("p_q_inner_data_dc").result
        )
        assert inner.tl_name == "p_q_inner_data_dc" and inner.dc in (self.dc_id, 4)
        handshake["dc"] = inner.dc
        assert inner.nonce == handshake["nonce"] and inner.server_nonce == handshake["server_nonce"]
        new_nonce = inner.new_nonce
        handshake["new_nonce"] = new_nonce
        server_nonce = handshake["server_nonce"]
        hash1 = hashlib.sha1(new_nonce + server_nonce).digest()
        hash2 = hashlib.sha1(server_nonce + new_nonce).digest()
        hash3 = hashlib.sha1(new_nonce + new_nonce).digest()
        handshake["tmp_key"] = hash1 + hash2[:12]
        handshake["tmp_iv"] = hash2[12:20] + hash3 + new_nonce[:4]
        handshake["a"] = int.from_bytes(os.urandom(256), "big")
        g_a = pow(G, handshake["a"], TELEGRAM_DH_PRIME)
        answer = SERIALIZER.serialize(
            build(
                "server_DH_inner_data",
                nonce=handshake["nonce"],
                server_nonce=server_nonce,
                g=G,
                dh_prime=TELEGRAM_DH_PRIME.to_bytes(256, "big"),
                g_a=g_a.to_bytes(256, "big"),
                server_time=int(time.time()),
            )
        )
        with_hash = hashlib.sha1(answer).digest() + answer
        with_hash += os.urandom(-len(with_hash) % 16)
        encrypted = aes_ige_encrypt(with_hash, handshake["tmp_key"], handshake["tmp_iv"])
        return build(
            "server_DH_params_ok",
            nonce=handshake["nonce"],
            server_nonce=server_nonce,
            encrypted_answer=encrypted,
        )

    def _set_client_dh(self, handshake: dict[str, Any], request: TLObject) -> TLObject:
        decrypted = aes_ige_decrypt(
            request.encrypted_data, handshake["tmp_key"], handshake["tmp_iv"]
        )
        reader = TLReader(decrypted[20:])
        client_dh = SERIALIZER.read(reader, SCHEMA.constructor("client_DH_inner_data").result)
        assert hashlib.sha1(decrypted[20 : 20 + reader.position]).digest() == decrypted[:20]
        g_b = int.from_bytes(client_dh.g_b, "big")
        auth_key = AuthKey(pow(g_b, handshake["a"], TELEGRAM_DH_PRIME).to_bytes(256, "big"))
        self.auth_keys[auth_key.id] = auth_key
        self.key_dcs[auth_key.id] = handshake["dc"]
        new_nonce, server_nonce = handshake["new_nonce"], handshake["server_nonce"]
        self.salt = int.from_bytes(
            bytes(a ^ b for a, b in zip(new_nonce[:8], server_nonce[:8], strict=True)),
            "little",
            signed=True,
        )
        return build(
            "dh_gen_ok",
            nonce=handshake["nonce"],
            server_nonce=server_nonce,
            new_nonce_hash1=hashlib.sha1(new_nonce + b"\x01" + auth_key.aux_hash).digest()[4:20],
        )

    # --- RPC handlers ------------------------------------------------------------------
    def on(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.handlers[name] = handler
            return handler

        return decorator

    def _require_auth(self, connection: Connection) -> None:
        assert connection.auth_key is not None
        if connection.auth_key.id not in self.authorized:
            raise RPCFailure(401, "AUTH_KEY_UNREGISTERED")

    def _authorize(self, connection: Connection) -> TLObject:
        assert connection.auth_key is not None
        self.authorized.add(connection.auth_key.id)
        return build("auth.authorization", user=self.account.user())

    def _new_message(self, text: str, peer: TLObject, *, out: bool) -> TLObject:
        self.pts += 1
        message_id = self.next_message_id
        self.next_message_id += 1
        return build(
            "message",
            id=message_id,
            peer_id=peer,
            from_id=build("peerUser", user_id=self.account.user_id) if out else None,
            date=int(time.time()),
            message=text,
            out=out,
        )

    def _register_defaults(self) -> None:
        @self.on("help.getConfig")
        def config(connection: Connection, request: TLObject) -> TLObject:
            return build(
                "config",
                this_dc=self.dc_id,
                dc_options=[
                    build("dcOption", id=self.dc_id, ip_address="127.0.0.1", port=self.port),
                    build("dcOption", id=4, ip_address="127.0.0.1", port=self.port),
                ],
                date=int(time.time()),
                expires=int(time.time()) + 3600,
            )

        @self.on("updates.getState")
        def get_state(connection: Connection, request: TLObject) -> TLObject:
            self._require_auth(connection)
            return build("updates.state", pts=self.pts, qts=0, date=int(time.time()), seq=0)

        @self.on("users.getUsers")
        def get_users(connection: Connection, request: TLObject) -> list[TLObject]:
            self._require_auth(connection)
            return [self.account.user()]

        @self.on("auth.sendCode")
        def send_code(connection: Connection, request: TLObject) -> TLObject:
            assert connection.auth_key is not None
            if (
                self.migrate_to is not None
                and self.key_dcs[connection.auth_key.id] != self.migrate_to
            ):
                raise RPCFailure(303, f"PHONE_MIGRATE_{self.migrate_to}")
            if request.phone_number != self.account.phone:
                raise RPCFailure(400, "PHONE_NUMBER_INVALID")
            return build(
                "auth.sentCode",
                type=build("auth.sentCodeTypeApp", length=len(self.account.code)),
                phone_code_hash="code-hash",
            )

        @self.on("auth.signIn")
        def sign_in(connection: Connection, request: TLObject) -> TLObject:
            if request.phone_code_hash != "code-hash" or request.phone_code != self.account.code:
                raise RPCFailure(400, "PHONE_CODE_INVALID")
            if self.account.password is not None:
                raise RPCFailure(401, "SESSION_PASSWORD_NEEDED")
            return self._authorize(connection)

        @self.on("account.getPassword")
        def get_password(connection: Connection, request: TLObject) -> TLObject:
            assert self.account.password is not None
            salt1, salt2 = os.urandom(40), os.urandom(16)
            p_bytes = TELEGRAM_DH_PRIME.to_bytes(256, "big")
            x = int.from_bytes(password_hash(self.account.password, salt1, salt2), "big")
            v = pow(G, x, TELEGRAM_DH_PRIME)
            k = int.from_bytes(hashlib.sha256(p_bytes + G.to_bytes(256, "big")).digest(), "big")
            b = int.from_bytes(os.urandom(256), "big")
            srp_b = (k * v + pow(G, b, TELEGRAM_DH_PRIME)) % TELEGRAM_DH_PRIME
            self.srp = SRPState(salt1, salt2, b, 42, srp_b)
            algo = build(
                "passwordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow",
                salt1=salt1,
                salt2=salt2,
                g=G,
                p=p_bytes,
            )
            return build(
                "account.password",
                has_password=True,
                current_algo=algo,
                srp_B=srp_b.to_bytes(256, "big"),
                srp_id=42,
                new_algo=algo,
                new_secure_algo=build("securePasswordKdfAlgoUnknown"),
                secure_random=os.urandom(32),
            )

        @self.on("auth.checkPassword")
        def check_password(connection: Connection, request: TLObject) -> TLObject:
            assert self.srp is not None and self.account.password is not None
            srp = self.srp
            check = request.password
            p = TELEGRAM_DH_PRIME
            p_bytes, g_bytes = p.to_bytes(256, "big"), G.to_bytes(256, "big")
            x = int.from_bytes(password_hash(self.account.password, srp.salt1, srp.salt2), "big")
            v = pow(G, x, p)
            a_int = int.from_bytes(check.A, "big")
            b_bytes = srp.srp_b.to_bytes(256, "big")
            u = int.from_bytes(hashlib.sha256(check.A + b_bytes).digest(), "big")
            s = pow(a_int * pow(v, u, p) % p, srp.b, p)
            k_s = hashlib.sha256(s.to_bytes(256, "big")).digest()
            hashed = bytes(
                a ^ b
                for a, b in zip(
                    hashlib.sha256(p_bytes).digest(), hashlib.sha256(g_bytes).digest(), strict=True
                )
            )
            expected = hashlib.sha256(
                hashed
                + hashlib.sha256(srp.salt1).digest()
                + hashlib.sha256(srp.salt2).digest()
                + check.A
                + b_bytes
                + k_s
            ).digest()
            if check.srp_id != srp.srp_id or expected != check.M1:
                raise RPCFailure(400, "PASSWORD_HASH_INVALID")
            return self._authorize(connection)

        @self.on("auth.importBotAuthorization")
        def import_bot(connection: Connection, request: TLObject) -> TLObject:
            if request.bot_auth_token != "42:BOT":
                raise RPCFailure(400, "ACCESS_TOKEN_INVALID")
            self.account.is_bot = True
            return self._authorize(connection)

        @self.on("auth.logOut")
        def log_out(connection: Connection, request: TLObject) -> TLObject:
            assert connection.auth_key is not None
            self.authorized.discard(connection.auth_key.id)
            return build("auth.loggedOut")

        @self.on("messages.sendMessage")
        def send_message(connection: Connection, request: TLObject) -> TLObject:
            self._require_auth(connection)
            peer = request.peer
            if peer.tl_name == "inputPeerUser" and peer.access_hash != 555:
                raise RPCFailure(400, "PEER_ID_INVALID")
            message = self._new_message(
                request.message, build("peerUser", user_id=self.account.user_id), out=True
            )
            return build(
                "updateShortSentMessage",
                out=True,
                id=message.id,
                pts=self.pts,
                pts_count=1,
                date=message.date,
            )

        @self.on("messages.editMessage")
        def edit_message(connection: Connection, request: TLObject) -> TLObject:
            self._require_auth(connection)
            self.pts += 1
            message = build(
                "message",
                id=request.id,
                peer_id=build("peerUser", user_id=self.account.user_id),
                date=int(time.time()),
                message=request.message,
                out=True,
            )
            update = build("updateEditMessage", message=message, pts=self.pts, pts_count=1)
            return build("updates", updates=[update], users=[], chats=[], date=0, seq=0)

        @self.on("messages.deleteMessages")
        def delete_messages(connection: Connection, request: TLObject) -> TLObject:
            self.pts += 1
            return build("messages.affectedMessages", pts=self.pts, pts_count=len(request.id))

        @self.on("contacts.resolveUsername")
        def resolve_username(connection: Connection, request: TLObject) -> TLObject:
            if request.username != "vali":
                raise RPCFailure(400, "USERNAME_NOT_OCCUPIED")
            vali = build("user", id=2000, access_hash=555, first_name="Vali", username="vali")
            return build(
                "contacts.resolvedPeer",
                peer=build("peerUser", user_id=2000),
                chats=[],
                users=[vali],
            )

        @self.on("messages.getHistory")
        def get_history(connection: Connection, request: TLObject) -> TLObject:
            messages = [
                build(
                    "message",
                    id=index,
                    peer_id=build("peerUser", user_id=2000),
                    date=0,
                    message=f"m{index}",
                )
                for index in range(3, 0, -1)
            ]
            return build("messages.messages", messages=messages, chats=[], users=[])

        @self.on("updates.getDifference")
        def get_difference(connection: Connection, request: TLObject) -> TLObject:
            missed = [(message, user) for pts, message, user in self.history if pts > request.pts]
            if not missed:
                return build("updates.differenceEmpty", date=int(time.time()), seq=0)
            state = build("updates.state", pts=self.pts, qts=0, date=int(time.time()), seq=0)
            return build(
                "updates.difference",
                new_messages=[message for message, _ in missed],
                new_encrypted_messages=[],
                other_updates=[],
                chats=[],
                users=[user for _, user in missed],
                state=state,
            )

        @self.on("messages.setBotCallbackAnswer")
        def callback_answer(connection: Connection, request: TLObject) -> bool:
            return True


def _serialize_result(result: Any) -> bytes:
    if isinstance(result, bool):
        return struct.pack("<I", 0x997275B5 if result else 0xBC799737)
    if isinstance(result, list):
        writer = TLWriter().uint32(0x1CB5C415).int32(len(result))
        return writer.to_bytes() + b"".join(SERIALIZER.serialize(item) for item in result)
    return SERIALIZER.serialize(result)


__all__ = ["Account", "FakeTelegramServer", "RPCFailure", "build"]
