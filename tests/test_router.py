from __future__ import annotations

import pytest

from tests.support import FakeSession, callback_update, message_update
from zafather import Command, ExceptionTypeFilter, F, Router, SkipHandler, Update, Zafather
from zafather.handler import CallableSpec


async def feed(app: Zafather, raw: dict) -> bool:
    return await app.feed_update(Update(raw, app.bot))


def test_register_rejects_unknown_event() -> None:
    with pytest.raises(ValueError, match="Unknown event type"):
        Router().register("no_such_event", lambda event: None)


def test_include_rejects_cycles() -> None:
    parent, child, grandchild = Router("p"), Router("c"), Router("g")
    parent.include(child)
    child.include(grandchild)
    with pytest.raises(ValueError):
        grandchild.include(parent)
    with pytest.raises(ValueError):
        parent.include(parent)
    assert parent.reaches(grandchild) and not grandchild.reaches(parent)


def test_callable_spec_selects_arguments() -> None:
    def handler(event, state, bot=None, *, extra):
        return event

    spec = CallableSpec(handler)
    assert spec.parameters == ("state", "bot", "extra")
    assert spec.select({"state": 1, "extra": 2, "unused": 3}) == {"state": 1, "extra": 2}

    def catch_all(event, **kwargs):
        return kwargs

    assert CallableSpec(catch_all).select({"a": 1}) == {"a": 1}


async def test_first_matching_handler_wins_and_skip(app: Zafather) -> None:
    calls = []

    @app.message(F.text == "hi")
    async def skipper(message):
        calls.append("skipper")
        raise SkipHandler

    @app.message(F.text == "hi")
    async def second(message):
        calls.append("second")

    @app.message()
    async def fallback(message):
        calls.append("fallback")

    assert await feed(app, message_update("hi"))
    assert calls == ["skipper", "second"]


async def test_sub_routers_and_handled_flag(app: Zafather, session: FakeSession) -> None:
    admin = Router("admin")

    @admin.callback(F.data.startswith("menu:"))
    async def menu(query):
        await query.answer("ok")

    app.include(admin)
    assert await feed(app, callback_update("menu:main"))
    assert session.last().method == "answerCallbackQuery"
    assert await feed(app, callback_update("other")) is False


async def test_outer_and_inner_middlewares(app: Zafather) -> None:
    trace = []

    @app.middleware
    async def outer(event, data, next_):
        trace.append("outer")
        data["db"] = "conn"
        return await next_(event, data)

    @app.inner_middleware
    async def inner(event, data, next_):
        trace.append(f"inner:{data['handler'].flags.get('rate')}")
        return await next_(event, data)

    @app.command("start", rate=5)
    async def start(message, db, command):
        trace.append(f"handler:{db}:{command}")

    await feed(app, message_update("/start"))
    assert trace == ["outer", "inner:5", "handler:conn:start"]

    trace.clear()
    await feed(app, message_update("no match"))
    assert trace == ["outer"]


async def test_middleware_can_stop_processing(app: Zafather) -> None:
    @app.middleware
    async def blocker(event, data, next_):
        return False

    @app.message()
    async def never(message):  # pragma: no cover - must not run
        raise AssertionError

    assert await feed(app, message_update("x")) is False


async def test_error_handlers_with_filters(app: Zafather) -> None:
    caught = []

    @app.error(ExceptionTypeFilter(KeyError))
    async def on_key_error(event, exception):
        caught.append(("key", type(exception)))

    @app.errors
    async def on_any(event, exception):
        caught.append(("any", type(exception)))

    @app.command("key")
    async def key_error(message):
        raise KeyError("x")

    @app.command("value")
    async def value_error(message):
        raise ValueError("x")

    assert await feed(app, message_update("/key")) is False
    assert await feed(app, message_update("/value")) is False
    assert caught == [("key", KeyError), ("any", ValueError)]


async def test_unhandled_error_is_logged(app: Zafather, caplog) -> None:
    @app.command("boom")
    async def boom(message):
        raise RuntimeError("boom")

    await feed(app, message_update("/boom"))
    assert "Unhandled error in message handler" in caplog.text


async def test_all_update_decorators_route(app: Zafather) -> None:
    seen = []
    payloads = {
        "edited_message": {"message_id": 1, "date": 0, "chat": {"id": 1, "type": "private"}},
        "channel_post": {"message_id": 1, "date": 0, "chat": {"id": -1, "type": "channel"}},
        "inline_query": {"id": "q", "from": {"id": 1}, "query": "", "offset": ""},
        "managed_bot": {"user": {"id": 1}, "bot": {"id": 555, "is_bot": True}},
        "guest_message": {"message_id": 1, "date": 0, "chat": {"id": 5, "type": "group"}},
        "subscription": {"from": {"id": 1}},
        "stopped_message_generation": {"chat": {"id": 1, "type": "private"}},
        "message_reaction": {"chat": {"id": 1}, "message_id": 1, "date": 0},
        "poll_answer": {"poll_id": "p", "user": {"id": 1}, "option_ids": []},
        "pre_checkout_query": {"id": "pc", "from": {"id": 1}},
        "chat_join_request": {"chat": {"id": -1}, "from": {"id": 1}, "date": 0},
        "chat_boost": {"chat": {"id": -1}, "boost": {}},
        "removed_chat_boost": {"chat": {"id": -1}},
        "my_chat_member": {"chat": {"id": 1}, "from": {"id": 1}, "date": 0},
        "chat_member": {"chat": {"id": 1}, "from": {"id": 1}, "date": 0},
        "business_message": {"message_id": 1, "date": 0, "chat": {"id": 1}},
        "business_connection": {"id": "b", "user": {"id": 1}},
        "shipping_query": {"id": "s", "from": {"id": 1}},
        "chosen_inline_result": {"result_id": "r", "from": {"id": 1}, "query": ""},
        "purchased_paid_media": {"from": {"id": 1}, "paid_media_payload": "x"},
        "poll": {"id": "p"},
    }
    decorators = {
        "edited_message": app.edited_message,
        "channel_post": app.channel_post,
        "inline_query": app.inline,
        "managed_bot": app.managed_bot,
        "guest_message": app.guest,
        "subscription": app.subscription,
        "stopped_message_generation": app.stopped_generation,
        "message_reaction": app.reaction,
        "poll_answer": app.poll_answer,
        "pre_checkout_query": app.pre_checkout,
        "chat_join_request": app.join_request,
        "chat_boost": app.boost,
        "removed_chat_boost": app.removed_boost,
        "my_chat_member": app.my_chat_member,
        "chat_member": app.chat_member,
        "business_message": app.business_message,
        "business_connection": app.business_connection,
        "shipping_query": app.shipping_query,
        "chosen_inline_result": app.chosen_inline_result,
        "purchased_paid_media": app.paid_media,
        "poll": app.poll,
    }
    for name, decorator in decorators.items():
        decorator()(lambda event, _name=name: seen.append(_name))
    for index, (name, payload) in enumerate(payloads.items()):
        assert await feed(app, {"update_id": index, name: payload}), name
    assert seen == list(payloads)


async def test_command_decorator_with_state_and_text_decorator(app: Zafather) -> None:
    seen = []

    @app.text("ha", "yes")
    async def agree(message):
        seen.append(message.text)

    @app.command("cancel", state="*")
    async def cancel(message):  # pragma: no cover - no state set
        seen.append("cancel")

    await feed(app, message_update("HA"))
    await feed(app, message_update("/cancel"))
    assert seen == ["HA"]
    assert repr(app).startswith("<Zafather 'zafather' handlers=2")


def test_command_filter_object_in_handlers(app: Zafather) -> None:
    handler = app.register("message", lambda event: None, Command("x"), flag=1)
    assert handler.flags == {"flag": 1} and handler.name == "<lambda>"
