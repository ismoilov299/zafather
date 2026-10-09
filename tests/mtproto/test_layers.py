from __future__ import annotations

import asyncio
import os
import stat
import struct

import pytest

from zafather.mtproto import FileSession, MemorySession, SessionData, StringSession
from zafather.mtproto.crypto import AuthKey
from zafather.mtproto.entities import CHANNEL, CHAT, USER, EntityCache, marked_id, peer_id, unmark
from zafather.mtproto.errors import (
    AuthKeyNotFoundError,
    BadRequestError,
    FloodWaitError,
    InternalServerError,
    PhoneMigrateError,
    RPCError,
    SecurityError,
    SessionPasswordNeededError,
    SlowModeWaitError,
    TransportError,
    UnauthorizedError,
    rpc_error,
)
from zafather.mtproto.session import resolve_session
from zafather.mtproto.state import MessageIds, MTProtoState
from zafather.mtproto.tl import types
from zafather.mtproto.transport import (
    AbridgedCodec,
    IntermediateCodec,
    TcpTransport,
    check_transport_error,
)


# --- errors --------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("code", "message", "error_class", "value"),
    [
        (420, "FLOOD_WAIT_42", FloodWaitError, 42),
        (420, "SLOWMODE_WAIT_5", SlowModeWaitError, 5),
        (303, "PHONE_MIGRATE_4", PhoneMigrateError, 4),
        (401, "SESSION_PASSWORD_NEEDED", SessionPasswordNeededError, None),
        (400, "SOMETHING_NEW", BadRequestError, None),
        (401, "AUTH_WHATEVER", UnauthorizedError, None),
        (500, "INTERNAL", InternalServerError, None),
        (999, "ODD", RPCError, None),
    ],
)
def test_rpc_error_mapping(code: int, message: str, error_class: type, value: int | None) -> None:
    error = rpc_error(code, message, "messages.sendMessage")
    assert type(error) is error_class and error.value == value
    assert "messages.sendMessage" in str(error)


def test_error_helpers() -> None:
    assert rpc_error(420, "FLOOD_WAIT_7").seconds == 7
    assert rpc_error(303, "USER_MIGRATE_5").new_dc == 5
    with pytest.raises(AuthKeyNotFoundError):
        check_transport_error(struct.pack("<i", -404))
    with pytest.raises(TransportError):
        check_transport_error(struct.pack("<i", -429))
    check_transport_error(b"12345678")


# --- transport ------------------------------------------------------------------------------
async def _frames(codec, payloads: list[bytes]) -> list[bytes]:
    reader = asyncio.StreamReader()
    for payload in payloads:
        reader.feed_data(codec.encode(payload))
    return [await codec.read_frame(reader) for _ in payloads]


async def test_codecs_frame_payloads() -> None:
    small, large = b"x" * 8, os.urandom(4 * 200)
    assert await _frames(AbridgedCodec(), [small, large]) == [small, large]
    assert AbridgedCodec().encode(small)[0] == 2 and AbridgedCodec().encode(large)[0] == 0x7F
    assert await _frames(IntermediateCodec(), [small, b"abc"]) == [small, b"abc"]
    with pytest.raises(ValueError):
        AbridgedCodec().encode(b"abc")


async def test_tcp_transport_against_echo_server() -> None:
    async def echo(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        assert await reader.readexactly(1) == b"\xef"
        codec = AbridgedCodec()
        frame = await codec.read_frame(reader)
        writer.write(codec.encode(frame[::-1]))
        writer.write(codec.encode(struct.pack("<i", -404)))
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(echo, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    transport = TcpTransport("127.0.0.1", port)
    with pytest.raises(TransportError):
        await transport.send(b"1234")
    await transport.connect()
    await transport.connect()
    assert transport.connected
    await transport.send(b"abcd")
    assert await transport.receive() == b"dcba"
    with pytest.raises(AuthKeyNotFoundError):
        await transport.receive()
    with pytest.raises(TransportError):
        await transport.receive()
    await transport.close()
    assert not transport.connected and "TcpTransport" in repr(transport)
    server.close()
    await server.wait_closed()
    with pytest.raises(TransportError):
        await TcpTransport("127.0.0.1", port, connect_timeout=1).connect()


# --- sessions -------------------------------------------------------------------------------
def _sample() -> SessionData:
    return SessionData(
        dc_id=4,
        auth_keys={4: os.urandom(256)},
        user_id=7,
        is_bot=True,
        update_state={"pts": 5},
        entities={2000: ["user", 555, "vali"]},
    )


def test_file_session_round_trip_and_permissions(tmp_path) -> None:
    storage = FileSession(tmp_path / "me")
    assert storage.path.name == "me.session.json" and storage.load() == SessionData()
    data = _sample()
    storage.save(data)
    assert FileSession(storage.path).load() == data
    if os.name == "posix":
        assert stat.S_IMODE(storage.path.stat().st_mode) == 0o600
    assert not storage.path.with_name(storage.path.name + ".tmp").exists()
    storage.delete()
    storage.delete()
    assert not storage.path.exists()


def test_file_session_reads_legacy_format(tmp_path) -> None:
    import base64
    import json

    path = tmp_path / "old.session.json"
    key = os.urandom(256)
    path.write_text(
        json.dumps({"auth_key": base64.b64encode(key).decode(), "dc_id": 2, "user_id": 9})
    )
    loaded = FileSession(path).load()
    assert loaded.auth_key == key and loaded.user_id == 9
    path.write_text("{broken")
    assert FileSession(path).load() == SessionData()


def test_string_and_memory_sessions() -> None:
    data = _sample()
    string = StringSession()
    string.save(data)
    assert string.value.startswith("1")
    restored = StringSession(string.value).load()
    assert (
        restored.auth_keys == data.auth_keys and restored.user_id == 7 and restored.entities == {}
    )
    with pytest.raises(ValueError):
        StringSession("9abc").load()
    memory = MemorySession()
    memory.save(data)
    loaded = memory.load()
    loaded.user_id = 1
    assert memory.load().user_id == 7
    memory.delete()
    assert memory.load() == SessionData()
    assert isinstance(resolve_session(None), MemorySession)
    assert resolve_session(memory) is memory
    assert isinstance(resolve_session("name"), FileSession)


# --- message state --------------------------------------------------------------------------
def test_message_ids_are_monotonic_and_aligned() -> None:
    ids = MessageIds()
    values = [ids.next() for _ in range(100)]
    assert values == sorted(set(values)) and all(value % 4 == 0 for value in values)
    ids.synchronize((ids.next() >> 32) + 3600 << 32)
    assert ids.time_offset >= 3599


def test_state_pack_unpack() -> None:
    key = AuthKey(os.urandom(256))
    state = MTProtoState(key, salt=11)
    assert [state.next_seq_no(True), state.next_seq_no(False), state.next_seq_no(True)] == [1, 2, 3]
    state.shift_sequence(-100)
    assert state.next_seq_no(False) == 0
    packet = state.pack(state.ids.next(), 1, b"body")
    plaintext = key.decrypt(packet, from_client=True)
    assert struct.unpack_from("<qq", plaintext) == (11, state.session_id)

    def server_message(session_id: int, msg_id: int, body: bytes, padding: int = 12) -> bytes:
        data = struct.pack("<qqqii", 0, session_id, msg_id, 1, len(body)) + body
        data += os.urandom(padding + (-(len(data) + padding) % 16))
        return key.encrypt(data, from_client=False)

    incoming = state.unpack(server_message(state.session_id, 5, b"okay"))
    assert (incoming.msg_id, incoming.seq_no, incoming.body) == (5, 1, b"okay")
    with pytest.raises(SecurityError, match="session"):
        state.unpack(server_message(state.session_id + 1, 5, b"okay"))
    with pytest.raises(SecurityError, match="even"):
        state.unpack(server_message(state.session_id, 4, b"okay"))
    with pytest.raises(SecurityError, match="padding"):
        state.unpack(server_message(state.session_id, 5, b"okay", padding=2000))


# --- entities -------------------------------------------------------------------------------
def test_marked_ids() -> None:
    assert marked_id(USER, 5) == 5 and marked_id(CHAT, 5) == -5
    assert marked_id(CHANNEL, 5) == -1000000000005
    assert (
        unmark(-1000000000005) == (CHANNEL, 5)
        and unmark(-5) == (CHAT, 5)
        and unmark(5) == (USER, 5)
    )
    assert peer_id(types.peerChannel(channel_id=5)) == -1000000000005
    assert peer_id(types.inputPeerUser(user_id=3, access_hash=1)) == 3
    assert (
        peer_id(
            types.chat(
                id=9,
                title="g",
                participants_count=1,
                date=0,
                version=1,
                photo=types.chatPhotoEmpty(),
            )
        )
        == -9
    )
    assert peer_id(42) == 42
    with pytest.raises(ValueError):
        marked_id("bad", 1)
    with pytest.raises(TypeError):
        peer_id("x")
    with pytest.raises(TypeError):
        peer_id(types.inputPeerSelf())


def test_entity_cache() -> None:
    cache = EntityCache({2000: ["user", 555, "vali"]})
    assert cache.input_peer(2000) == types.inputPeerUser(user_id=2000, access_hash=555)
    assert cache.by_username("@VALI").id == 2000 and 2000 in cache and len(cache) == 1
    cache.add([types.user(id=2000, access_hash=999, min=True, username="vali2")])
    assert cache.get(2000).access_hash == 555 and cache.get(2000).username == "vali2"
    cache.add(
        [
            types.channel(id=7, title="c", photo=types.chatPhotoEmpty(), date=0, access_hash=8),
            "junk",
        ]
    )
    assert cache.input_peer(-1000000000007).channel_id == 7
    assert cache.input_peer(-15) == types.inputPeerChat(chat_id=15)
    assert cache.input_peer(31337) is None and cache.input_user(31337) is None
    assert cache.input_user(2000) == types.inputUser(user_id=2000, access_hash=555)
    cache.add([types.user(id=3, access_hash=1, min=True)])
    assert 3 not in cache.export()
