from __future__ import annotations

import asyncio

import pytest

from tests.support import ME, TOKEN, FakeSession, callback_update, message_update
from zafather import (
    FSMContext,
    FSMStrategy,
    Message,
    Regex,
    State,
    StatesGroup,
    StorageKey,
    Update,
    Zafather,
)
from zafather.dispatcher import EventScope
from zafather.types import CallbackQuery


class Form(StatesGroup):
    name = State()
    age = State()


async def feed(app: Zafather, raw: dict) -> bool:
    return await app.feed_update(Update(raw, app.bot))


def texts(session: FakeSession) -> list[str]:
    return [request.params["text"] for request in session.calls("sendMessage")]


async def test_fsm_conversation(app: Zafather, session: FakeSession) -> None:
    @app.command("form")
    async def start(message: Message, state: FSMContext):
        await state.set_state(Form.name)
        await message.answer("Name?")

    @app.message(state=Form.name)
    async def name(message: Message, state: FSMContext):
        await state.update_data(name=message.text)
        await state.set_state(Form.age)
        await message.answer("Age?")

    @app.message(Regex(r"^\d+$"), state=Form.age)
    async def age(message: Message, state: FSMContext):
        data = await state.update_data(age=int(message.text))
        await state.clear()
        await message.answer(f"{data['name']}, {data['age']}")

    @app.message(state=Form.age)
    async def wrong_age(message: Message):
        await message.answer("Digits only")

    for text in ("/form", "Ali", "abc", "20"):
        await feed(app, message_update(text))
    assert texts(session) == ["Name?", "Age?", "Digits only", "Ali, 20"]
    key = StorageKey(123456, 1, 1)
    assert await FSMContext(app.storage, key).get_state() is None


async def test_context_injection(app: Zafather) -> None:
    app.data["db"] = "database"
    captured = {}

    @app.callback()
    async def handler(
        query: CallbackQuery, bot, app, update, event_type, chat_id, user_id, db, raw_state
    ):
        captured.update(
            bot=bot,
            app=app,
            update=update,
            event_type=event_type,
            chat_id=chat_id,
            user_id=user_id,
            db=db,
            raw_state=raw_state,
        )

    await feed(app, callback_update("x", chat_id=7, user_id=3))
    assert captured["bot"] is app.bot and captured["app"] is app
    assert captured["event_type"] == "callback_query"
    assert (captured["chat_id"], captured["user_id"], captured["db"]) == (7, 3, "database")
    assert captured["raw_state"] is None


def test_event_scope_rules() -> None:
    message = Update(message_update("x", chat_id=5, user_id=2)).event
    assert EventScope.from_event(message) == EventScope(5, 2, None)
    inline = Update({"update_id": 1, "inline_query": {"id": "q", "from": {"id": 9}}}).event
    assert EventScope.from_event(inline) == EventScope(9, 9, None)
    topic = Update(message_update("x", is_topic_message=True, message_thread_id=4)).event
    assert EventScope.from_event(topic).thread_id == 4


async def test_fsm_strategy_chat_shares_state(session: FakeSession) -> None:
    app = Zafather(TOKEN, session=session, fsm_strategy=FSMStrategy.CHAT)

    @app.command("set")
    async def set_state(message: Message, state: FSMContext):
        await state.set_state("shared")

    @app.message(state="shared")
    async def shared(message: Message):
        await message.answer("seen")

    await feed(app, message_update("/set", chat_id=-10, user_id=1, chat_type="group"))
    await feed(app, message_update("hi", chat_id=-10, user_id=2, chat_type="group"))
    assert texts(session) == ["seen"]


async def test_unsupported_update_is_ignored(app: Zafather) -> None:
    assert await feed(app, {"update_id": 1, "something_new": {}}) is False


async def test_hooks_and_polling_lifecycle(session: FakeSession) -> None:
    app = Zafather(TOKEN, session=session, polling_timeout=0)
    events = []

    @app.on_startup
    async def started(bot, app):
        events.append(("startup", bot is app.bot))

    @app.on_shutdown
    def stopped():
        events.append(("shutdown", True))

    @app.message()
    async def echo(message: Message):
        await message.answer(message.text)
        await app.stop()

    session.respond("getUpdates", [message_update("ping", update_id=10)])
    await asyncio.wait_for(app.start_polling(), timeout=5)
    assert events == [("startup", True), ("shutdown", True)]
    assert texts(session) == ["ping"]
    assert session.calls("deleteWebhook")[0].params == {"drop_pending_updates": True}
    assert not session.closed  # injected sessions stay owned by the caller


async def test_shared_storage_is_not_closed_by_child(session: FakeSession) -> None:
    parent = Zafather(TOKEN, session=session)

    @parent.command("start")
    async def start(message: Message):
        await message.answer("from parent handlers")

    child = parent.spawn("654321:CHILD-TOKEN", session=session)
    assert child.storage is parent.storage and child.data["parent"] is parent
    await child.feed_update(Update(message_update("/start"), child.bot))
    assert texts(session) == ["from parent handlers"]

    closed = []
    parent.storage.close = lambda: closed.append(True) or asyncio.sleep(0)  # type: ignore[method-assign]
    await child._release_resources()
    assert closed == []
    await parent._release_resources()
    assert closed == [True]


async def test_webhook_mode_sets_and_serves(session: FakeSession, unused_tcp_port: int) -> None:
    import aiohttp

    app = Zafather(TOKEN, session=session)

    @app.message()
    async def echo(message: Message):
        await message.answer("got it")

    server = asyncio.create_task(
        app.start_webhook(
            "https://example.com/hook",
            host="127.0.0.1",
            port=unused_tcp_port,
            secret_token="s3cret",
            delete_on_shutdown=True,
        )
    )
    for _ in range(100):
        if session.calls("setWebhook"):
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.05)
    url = f"http://127.0.0.1:{unused_tcp_port}/hook"
    async with aiohttp.ClientSession() as client:
        async with client.post(url, json=message_update("hi")) as response:
            assert response.status == 403
        headers = {"X-Telegram-Bot-Api-Secret-Token": "s3cret"}
        async with client.post(url, json=message_update("hi"), headers=headers) as response:
            assert response.status == 200
        async with client.post(url, data=b"{", headers=headers) as response:
            assert response.status == 400
    await asyncio.sleep(0.05)
    await app.stop()
    await asyncio.wait_for(server, timeout=5)
    set_webhook = session.last("setWebhook").params
    assert (
        set_webhook["url"] == "https://example.com/hook" and set_webhook["secret_token"] == "s3cret"
    )
    assert texts(session) == ["got it"]
    assert session.calls("deleteWebhook")


def test_invalid_secret_token_is_rejected(app: Zafather) -> None:
    with pytest.raises(ValueError):
        asyncio.run(app.start_webhook("https://e.com/h", secret_token="has space"))


async def test_handle_webhook_payload(app: Zafather, session: FakeSession) -> None:
    @app.message()
    async def echo(message: Message):
        await message.answer("ok")

    assert await app.handle_webhook(message_update("x"))
    assert texts(session) == ["ok"]
    assert ME["username"] == (await app.bot.me()).username
