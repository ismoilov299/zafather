from __future__ import annotations

import asyncio

import pytest

from tests.mtproto.fake_server import FakeTelegramServer, RPCFailure, build
from zafather.mtproto import (
    DcOption,
    FileSession,
    FloodWaitError,
    MemorySession,
    MTProtoClient,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
    StringSession,
    TransportError,
    events,
    functions,
    types,
)
from zafather.mtproto.errors import MTProtoError


def make_client(server: FakeTelegramServer, session=None, **options) -> MTProtoClient:
    overrides = {dc: DcOption(dc, "127.0.0.1", server.port) for dc in (2, 4)}
    options.setdefault("reconnect_delay", 0.01)
    return MTProtoClient(
        1,
        "hash",
        session=session or MemorySession(),
        rsa_keys=[server.public],
        dc_overrides=overrides,
        **options,
    )


async def eventually(condition, timeout: float = 3.0) -> None:
    for _ in range(int(timeout / 0.01)):
        if condition():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met in time")


async def test_connect_creates_and_persists_auth_key(server: FakeTelegramServer) -> None:
    session = MemorySession()
    client = make_client(server, session)
    await client.connect()
    assert client.connected and client.dc_id == 2
    stored = session.load()
    assert 2 in stored.auth_keys and stored.auth_keys[2] in {
        k.key for k in server.auth_keys.values()
    }
    assert not await client.is_user_authorized()
    assert server.requests[0].tl_name == "invokeWithLayer"
    await client.disconnect()
    reconnect = make_client(server, session)
    await reconnect.connect()
    assert len(server.auth_keys) == 1
    await reconnect.disconnect()


async def test_code_login_and_messaging(server: FakeTelegramServer) -> None:
    client = make_client(server)
    await client.start(phone="998901234567", code_callback="12345")
    me = await client.get_me()
    assert me.first_name == "Ali" and client.self_id == 1000 and await client.is_user_authorized()
    sent = await client.send_message("@vali", "<b>Salom</b>", parse_mode="html")
    request = next(r for r in server.requests if r.tl_name == "messages.sendMessage")
    assert request.message == "Salom" and request.entities[0].tl_name == "messageEntityBold"
    assert request.peer == types.inputPeerUser(user_id=2000, access_hash=555)
    assert sent.out and sent.message == "Salom" and sent.from_id.user_id == 1000
    edited = await client.edit_message("@vali", sent.id, "tahrir")
    assert edited.message == "tahrir"
    history = await client.get_messages("vali", limit=3)
    assert [m.message for m in history] == ["m3", "m2", "m1"]
    affected = await client.delete_messages(2000, [sent.id])
    assert affected.pts_count == 1
    assert (await client.get_input_entity("me")).tl_name == "inputPeerSelf"
    assert (await client.get_input_entity(1000)).tl_name == "inputPeerSelf"
    with pytest.raises(ValueError, match="Unknown peer"):
        await client.get_input_entity(424242)
    with pytest.raises(ValueError):
        await client.get_input_entity("not a username!")
    with pytest.raises(ValueError, match="parse_mode"):
        await client.send_message("me", "x", parse_mode="markdown")
    await client.disconnect()


async def test_two_factor_login(server: FakeTelegramServer) -> None:
    server.account.password = "s3cret"
    client = make_client(server)
    await client.connect()
    await client.send_code("998901234567")
    with pytest.raises(SessionPasswordNeededError):
        await client.sign_in("998901234567", "12345")
    with pytest.raises(Exception, match="PASSWORD_HASH_INVALID"):
        await client.check_password("wrong")
    user = await client.check_password("s3cret")
    assert user.id == 1000 and await client.is_user_authorized()
    await client.disconnect()


async def test_interactive_start_retries_wrong_codes(server: FakeTelegramServer) -> None:
    codes = iter(["00000", "12345"])
    client = make_client(server)
    await client.start(phone=lambda: "998901234567", code_callback=lambda: next(codes))
    assert client.self_id == 1000
    await client.disconnect()
    failing = make_client(server)
    with pytest.raises(PhoneCodeInvalidError):
        await failing.start(phone="998901234567", code_callback="99999")
    await failing.disconnect()
    unknown = make_client(server)
    await unknown.connect()
    with pytest.raises(ValueError, match="send_code"):
        await unknown.sign_in("998901234567", "12345")
    await unknown.disconnect()


async def test_bot_login(server: FakeTelegramServer) -> None:
    session = MemorySession()
    client = make_client(server, session)
    await client.start(bot_token="42:BOT")
    assert session.load().is_bot and client.self_id == 1000
    await client.disconnect()


async def test_phone_migration_switches_dc(server: FakeTelegramServer) -> None:
    server.migrate_to = 4
    session = MemorySession()
    client = make_client(server, session)
    await client.connect()
    sent = await client.send_code("998901234567")
    assert sent.phone_code_hash == "code-hash" and client.dc_id == 4
    assert set(session.load().auth_keys) == {2, 4}
    await client.disconnect()


async def test_flood_wait_is_slept_or_raised(server: FakeTelegramServer) -> None:
    calls = []

    @server.on("help.getNearestDc")
    def nearest(connection, request):
        calls.append(1)
        if len(calls) == 1:
            raise RPCFailure(420, "FLOOD_WAIT_0")
        return build("nearestDc", country="UZ", this_dc=2, nearest_dc=2)

    client = make_client(server, flood_sleep_threshold=0)
    await client.connect()
    nearest_dc = await client.invoke(functions.help.getNearestDc())
    assert nearest_dc.country == "UZ" and len(calls) == 2
    calls.clear()
    client.flood_sleep_threshold = -1
    with pytest.raises(FloodWaitError):
        await client.invoke(functions.help.getNearestDc())
    with pytest.raises(TypeError):
        await client.invoke(types.inputPeerSelf())
    await client.disconnect()


async def test_events_from_short_and_full_updates(server: FakeTelegramServer) -> None:
    client = make_client(server)
    replies, stopped = [], []

    @client.on(events.NewMessage(pattern=r"^\.ping$", incoming=True))
    async def ping(event):
        replies.append(await event.reply("pong"))
        raise events.StopPropagation

    @client.on(events.NewMessage)
    async def never(event):
        stopped.append(event)

    await client.start(phone="998901234567", code_callback="12345")
    first = await server.push_incoming(".ping")
    await eventually(lambda: len(replies) == 1)
    second = await server.push_incoming(".ping", short=False)
    await eventually(lambda: len(replies) == 2)
    assert stopped == []
    assert [reply.reply_to.reply_to_msg_id for reply in replies] == [first.id, second.id]
    assert all(reply.message == "pong" and reply.peer_id.user_id == 2000 for reply in replies)
    assert client._updates.state.pts == server.pts
    assert len(client.list_event_handlers()) == 2
    assert client.remove_event_handler(never, events.MessageEdited) == 0
    assert client.remove_event_handler(never, events.NewMessage) == 1
    client.add_event_handler(ping, events.MessageEdited)
    assert type(client.list_event_handlers()[-1][0]) is events.MessageEdited
    assert client.remove_event_handler(ping) == 2
    client.add_event_handler(lambda event: None)
    assert type(client.list_event_handlers()[-1][0]) is events.Raw
    await client.disconnect()


async def test_bad_salt_gzip_containers_and_reconnect(server: FakeTelegramServer) -> None:
    client = make_client(server)
    await client.start(phone="998901234567", code_callback="12345")
    server.send_bad_salt_once = True
    server.gzip_results = True
    assert (await client.get_me()).id == 1000
    users = await client.invoke(functions.users.getUsers(id=[types.inputUserSelf()]))
    assert users[0].id == 1000
    server.gzip_results = False
    server.drop_connections()
    await asyncio.sleep(0.05)
    users = await client.invoke(functions.users.getUsers(id=[types.inputUserSelf()]))
    assert users[0].id == 1000 and client.connected
    await client.disconnect()


async def test_missed_updates_are_fetched_after_reconnect(server: FakeTelegramServer) -> None:
    client = make_client(server)
    seen: list[str] = []

    @client.on(events.NewMessage(incoming=True))
    async def collect(event):
        seen.append(event.text)

    await client.start(phone="998901234567", code_callback="12345")
    server.drop_connections()
    await server.push_incoming("while offline")
    await eventually(lambda: seen == ["while offline"], timeout=5)
    assert client.connected and client._updates.state.pts == server.pts
    await client.disconnect()


async def test_connection_loss_surfaces_in_run_until_disconnected(
    server: FakeTelegramServer,
) -> None:
    client = make_client(server, reconnect_retries=1)
    await client.connect()
    runner = asyncio.create_task(client.run_until_disconnected())
    await server.stop()
    server.drop_connections()
    with pytest.raises(TransportError):
        await asyncio.wait_for(runner, timeout=5)
    await client.disconnect()


async def test_disconnect_ends_run_until_disconnected(server: FakeTelegramServer) -> None:
    client = make_client(server)
    with pytest.raises(TransportError):
        await client.run_until_disconnected()
    async with client:
        runner = asyncio.create_task(client.run_until_disconnected())
        await asyncio.sleep(0.01)
    await asyncio.wait_for(runner, timeout=1)
    assert "MTProtoClient" in repr(client)


async def test_log_out_clears_session(server: FakeTelegramServer, tmp_path) -> None:
    storage = FileSession(tmp_path / "user")
    client = make_client(server, storage)
    await client.start(phone="998901234567", code_callback="12345")
    assert storage.path.exists()
    assert await client.log_out()
    assert not storage.path.exists() and client.session.user_id is None


async def test_string_session_and_environment_guard(server: FakeTelegramServer) -> None:
    session = StringSession()
    client = make_client(server, session)
    await client.start(phone="998901234567", code_callback="12345")
    await client.disconnect()
    assert session.value
    restored = make_client(server, StringSession(session.value))
    await restored.connect()
    assert await restored.is_user_authorized()
    await restored.disconnect()
    with pytest.raises(ValueError, match="environment"):
        make_client(server, StringSession(session.value), test_mode=True)


def test_constructor_validation() -> None:
    with pytest.raises(ValueError):
        MTProtoClient(0, "hash", session=None)
    with pytest.raises(ValueError):
        MTProtoClient(1, " ", session=None)
    client = MTProtoClient(1, "hash", session=None, connection="intermediate")
    assert client._default_transport(DcOption(2, "127.0.0.1")).codec.tag == b"\xee\xee\xee\xee"


async def test_unregistered_phone_is_reported(server: FakeTelegramServer) -> None:
    @server.on("auth.signIn")
    def sign_up_required(connection, request):
        return build("auth.authorizationSignUpRequired")

    client = make_client(server)
    await client.connect()
    await client.send_code("998901234567")
    with pytest.raises(MTProtoError, match="not registered"):
        await client.sign_in("998901234567", "12345")
    await client.disconnect()
