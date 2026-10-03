from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tests.mtproto.fake_server import FakeTelegramServer
from zafather import UserBot
from zafather.mtproto import DcOption, MemorySession, MTProtoClient, events, functions
from zafather.mtproto.errors import FloodWaitError, SlowModeWaitError, rpc_error
from zafather.userbot import flood_wait_seconds, is_connection_error, is_flood_wait


class FloodWait(Exception):
    """Mimics Pyrogram: the duration lives in `value`."""

    def __init__(self, value: Any = None) -> None:
        super().__init__(value)
        self.value = value


class Script:
    """Raises or returns the queued outcomes one call at a time."""

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self) -> None:
        self.handlers: list[tuple[Any, Any]] = []
        self.removed: list[Any] = []
        self.connects = 0
        self.disconnects = 0
        self.connect_error: BaseException | None = None
        self.start = Script("started")
        self.run_until_disconnected = Script(None)
        self.send_message = Script("sent")
        self.get_me = Script("me")
        self.username = "ali"

    def on(self, builder: Any) -> Any:
        def decorator(callback: Any) -> Any:
            self.handlers.append((builder, callback))
            return callback

        return decorator

    def add_event_handler(self, callback: Any, builder: Any = None) -> None:
        self.handlers.append((builder, callback))

    def remove_event_handler(self, callback: Any, builder: Any = None) -> int:
        self.removed.append(callback)
        return 1

    async def connect(self) -> None:
        self.connects += 1
        if self.connect_error is not None:
            raise self.connect_error

    def disconnect(self) -> None:  # synchronous on purpose: both styles are supported
        self.disconnects += 1


def make_userbot(client: Any = None, **options: Any) -> UserBot:
    options.setdefault("reconnect_delay", 0)
    options.setdefault("retry_delay", 0)
    return UserBot(1, "hash", client=client or FakeClient(), **options)


@pytest.mark.parametrize(
    "arguments",
    [
        {"api_id": 0},
        {"api_id": True},
        {"api_hash": " "},
        {"max_retries": -1},
        {"max_reconnects": -1},
        {"retry_delay": -1},
        {"reconnect_delay": -1},
        {"backoff": 0.5},
    ],
)
def test_constructor_validation(arguments: dict[str, Any]) -> None:
    values: dict[str, Any] = {"api_id": 1, "api_hash": "hash", "client": FakeClient()}
    values.update(arguments)
    with pytest.raises(ValueError):
        UserBot(**values)


def test_default_client_is_mtproto_with_options() -> None:
    userbot = UserBot(7, "hash", session=MemorySession(), device_model="zafather-test")
    assert isinstance(userbot.client, MTProtoClient)
    assert userbot.client.api_id == 7 and userbot.client.device_model == "zafather-test"
    assert userbot.events is events


def test_error_helpers() -> None:
    assert flood_wait_seconds(rpc_error(420, "FLOOD_WAIT_12")) == 12
    assert flood_wait_seconds(SlowModeWaitError(420, "SLOWMODE_WAIT_3")) == 3
    assert is_flood_wait(SlowModeWaitError(420, "SLOWMODE_WAIT_3"))
    assert flood_wait_seconds(FloodWait(4)) == 4 and flood_wait_seconds(FloodWait(True)) is None
    assert flood_wait_seconds(ValueError("FLOOD_WAIT_1")) is None
    assert is_connection_error(ConnectionResetError()) and is_connection_error(
        asyncio.TimeoutError()
    )
    assert not is_connection_error(ValueError())


def test_handlers_are_registered_with_the_right_builders() -> None:
    client = FakeClient()
    userbot = make_userbot(client)

    @userbot.on_message(pattern=r"^\.ping$", outgoing=True)
    async def ping(event: Any) -> None: ...

    decorators = (
        userbot.on_new_message(),
        userbot.on_edited(),
        userbot.on_deleted(),
        userbot.on_callback(),
        userbot.on_callback_query(data=b"x"),
        userbot.on(events.Raw()),
    )
    for decorator in decorators:
        decorator(ping)
    kinds = [type(builder).__name__ for builder, _ in client.handlers]
    assert kinds == [
        "NewMessage",
        "NewMessage",
        "MessageEdited",
        "MessageDeleted",
        "CallbackQuery",
        "CallbackQuery",
        "Raw",
    ]
    assert client.handlers[0][0].outgoing is True
    userbot.add_handler(ping)
    assert userbot.remove_handler(ping) == 1 and client.removed == [ping]


async def test_flood_wait_is_retried_until_the_limit() -> None:
    client = FakeClient()
    client.get_me = Script(rpc_error(420, "FLOOD_WAIT_0"), FloodWait(), "me")
    userbot = make_userbot(client, max_retries=2)
    assert await userbot.call("get_me") == "me"
    assert len(client.get_me.calls) == 3
    client.get_me = Script(FloodWaitError(420, "FLOOD_WAIT_0"), FloodWaitError(420, "FLOOD_WAIT_0"))
    with pytest.raises(FloodWaitError):
        await make_userbot(client, max_retries=1).call(client.get_me)


async def test_connection_errors_reconnect_with_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    delays: list[float] = []
    real_sleep = asyncio.sleep

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    client = FakeClient()
    client.get_me = Script(ConnectionResetError(), OSError(), "me")
    userbot = make_userbot(client, reconnect_delay=1.5, backoff=2)
    assert await userbot.request("get_me") == "me"
    assert delays == [1.5, 3.0] and client.connects == 2
    client.get_me = Script(ConnectionResetError(), ConnectionResetError())
    with pytest.raises(ConnectionResetError):
        await make_userbot(client, max_reconnects=1).call("get_me")
    client.get_me = Script(ValueError("bad"))
    with pytest.raises(ValueError):
        await userbot.call("get_me")


async def test_failed_reconnects_count_towards_the_limit() -> None:
    client = FakeClient()
    client.connect_error = ConnectionRefusedError()
    client.get_me = Script(ConnectionResetError(), ConnectionResetError(), ConnectionResetError())
    with pytest.raises(ConnectionResetError):
        await make_userbot(client, max_reconnects=2).call("get_me")
    assert client.connects == 2
    client.connect_error = RuntimeError("broken")
    client.get_me = Script(ConnectionResetError())
    with pytest.raises(RuntimeError, match="broken"):
        await make_userbot(client).call("get_me")


async def test_send_message_is_not_repeated_after_a_drop() -> None:
    client = FakeClient()
    client.send_message = Script(ConnectionResetError())
    userbot = make_userbot(client)
    with pytest.raises(ConnectionResetError):
        await userbot.send_message("me", "salom")
    assert client.connects == 0
    client.send_message = Script(FloodWaitError(420, "FLOOD_WAIT_0"), "sent")
    assert await userbot.send_message("me", "salom", silent=True) == "sent"
    assert client.send_message.calls[-1] == (("me", "salom"), {"silent": True})


async def test_invoke_prefers_invoke_and_falls_back_to_call() -> None:
    client = FakeClient()
    client.invoke = Script("result")  # type: ignore[attr-defined]
    assert await make_userbot(client).invoke("request", timeout=3) == "result"
    assert client.invoke.calls == [(("request",), {"timeout": 3})]  # type: ignore[attr-defined]

    class CallableClient(FakeClient):
        async def __call__(self, request: Any) -> Any:
            return ("called", request)

    assert await make_userbot(CallableClient()).invoke("raw") == ("called", "raw")


async def test_lifecycle_delegation() -> None:
    client = FakeClient()
    userbot = make_userbot(client)
    assert await userbot.start("998901234567", code_callback="1") == "started"
    assert client.start.calls == [((), {"phone": "998901234567", "code_callback": "1"})]
    client.start = Script("started")
    client.run_until_disconnected = Script(ConnectionResetError(), "finished")
    assert await userbot.run() == "finished" and client.connects == 1
    client.start = Script("started")
    async with userbot as entered:
        assert entered is userbot
    assert client.disconnects == 1
    assert userbot.username == "ali"
    with pytest.raises(AttributeError):
        _ = userbot._missing


async def test_userbot_end_to_end_with_mtproto(server: FakeTelegramServer) -> None:
    overrides = {dc: DcOption(dc, "127.0.0.1", server.port) for dc in (2, 4)}
    userbot = UserBot(
        1,
        "hash",
        session=MemorySession(),
        rsa_keys=[server.public],
        dc_overrides=overrides,
        reconnect_delay=0.01,
    )
    replies: list[Any] = []

    @userbot.on_message(pattern=r"^\.ping$", incoming=True)
    async def ping(event: Any) -> None:
        replies.append(await event.reply("pong"))

    await userbot.start("998901234567", code_callback="12345")
    runner = asyncio.create_task(userbot.run_until_disconnected())
    incoming = await server.push_incoming(".ping")
    for _ in range(300):
        if replies:
            break
        await asyncio.sleep(0.01)
    assert replies and replies[0].reply_to.reply_to_msg_id == incoming.id
    me = await userbot.call("get_me")
    assert me.id == 1000
    sent = await userbot.send_message("@vali", "salom")
    assert sent.message == "salom"
    config = await userbot.invoke(functions.help.getConfig())
    assert config.tl_name == "config"
    await userbot.disconnect()
    await asyncio.wait_for(runner, timeout=2)
