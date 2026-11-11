from __future__ import annotations

import json
import random
import string
import zlib

import pytest

from tests.support import FakeSession, message, user
from zafather import (
    BadRequest,
    Bot,
    ContentTypes,
    F,
    InputSharedWidgetMessageContent,
    InputWidgetMessageContent,
    LongPolling,
    NetworkError,
    Router,
    SharedWidgetQuery,
    Update,
    UpdateType,
    Widget,
    WidgetQuery,
    WidgetQueryType,
    WidgetQueryTypeData,
    WidgetQueryTypeSentTransaction,
    WidgetQueryTypeSignData,
    Zafather,
    widget_size,
)
from zafather.api import PayloadBuilder
from zafather.dispatcher import EventScope
from zafather.types import ExternalReplyInfo, TonWalletCard, WidgetQueryWallet


def query_update(kind: str = "widget_query", *, inline: bool = False, **extra) -> dict:
    query = {
        "id": "q1",
        "from": user(42),
        "data": "refresh",
        "type": {"type": "data"},
        "widget_id": "9007199254740999",
        **extra,
    }
    if kind == "widget_query":
        query["chat_instance"] = "ci"
        query.update(
            {"inline_message_id": "inline-1", "chat_type": "group"}
            if inline
            else {"chat": {"id": -5, "type": "supergroup"}, "message_id": 7}
        )
    return {"update_id": 10, kind: query}


def test_widget_size_matches_telegram_compression() -> None:
    html = "<p>Salom, Привет, 👋</p>"
    raw = html.encode()
    assert widget_size(html) == (len(raw), len(zlib.compress(raw, 9)))


@pytest.mark.parametrize(
    "html",
    ["", "a" * 32769, "я" * 16385, "a\0b", "\ud800"],
    ids=["empty", "too-many-bytes", "multibyte-overflow", "nul", "invalid-utf8"],
)
def test_invalid_html_rejected(html: str) -> None:
    with pytest.raises(ValueError):
        PayloadBuilder().build("sendWidget", {"chat_id": 1, "html": html})


def test_compressed_html_limit_and_raw_limit_are_independent() -> None:
    builder = PayloadBuilder()
    assert builder.build("sendWidget", {"html": "a" * 32768}).fields["html"]
    rng = random.Random(42)
    html = "".join(rng.choices(string.ascii_letters + string.digits, k=6000))
    assert widget_size(html)[1] > 4096
    with pytest.raises(ValueError, match="4096"):
        builder.build("sendWidget", {"html": html})


@pytest.mark.parametrize("field", ["public_data", "chat_data"])
def test_state_utf8_limits_and_clear_semantics(field: str) -> None:
    builder = PayloadBuilder()
    base = {"chat_id": 1, "message_id": 2}
    for value in ("", "я" * 512):
        assert builder.build("editMessageWidgetData", {**base, field: value}).fields[field] == value
    assert field not in builder.build("editMessageWidgetData", {**base, field: None}).fields
    for value in ("я" * 513, "\0", "\ud800"):
        with pytest.raises(ValueError):
            builder.build("editMessageWidgetData", {**base, field: value})
    with pytest.raises(TypeError):
        builder.build("sendWidget", {"html": "a", field: {"x": 1}})


@pytest.mark.parametrize("name", ["width", "height"])
def test_sizes_preserve_auto_and_client_clamping(name: str) -> None:
    for value in (0, 1, 600, 1000):
        assert (
            PayloadBuilder().build("sendWidget", {"html": "a", name: value}).fields[name] == value
        )
    for value in (True, "320", 1.5):
        with pytest.raises(TypeError):
            PayloadBuilder().build("sendWidget", {"html": "a", name: value})


@pytest.mark.parametrize(
    "target",
    [
        {},
        {"chat_id": 1},
        {"message_id": 2},
        {"inline_message_id": ""},
        {"inline_message_id": "i", "chat_id": 1},
        {"inline_message_id": "i", "message_id": 2},
    ],
)
def test_edit_rejects_missing_or_ambiguous_coordinates(target: dict) -> None:
    with pytest.raises(ValueError):
        PayloadBuilder().build("editMessageWidgetData", {**target, "chat_data": ""})


@pytest.mark.parametrize("cache", [5, 30, 3600, 3601])
def test_shared_cache_preserves_server_clamping(cache: int) -> None:
    payload = PayloadBuilder().build(
        "editSharedWidgetData", {"widget_id": "w", "public_data": "", "cache_time": cache}
    )
    assert payload.fields["cache_time"] == cache


@pytest.mark.parametrize("cache", [0, 4, True, 5.5, "30"])
def test_invalid_shared_cache(cache) -> None:
    with pytest.raises((TypeError, ValueError)):
        PayloadBuilder().build(
            "editSharedWidgetData", {"widget_id": "w", "public_data": "", "cache_time": cache}
        )


async def test_all_widget_methods_and_wrapping(bot: Bot, session: FakeSession) -> None:
    html = "<button>Hi</button>"
    result = message(None, widget={"id": "w", "html": html, "chat_data": "{}"})
    session.respond("sendWidget", result)
    sent = await bot.send_widget(
        1,
        html,
        width=0,
        height=0,
        public_data="{}",
        chat_data="{}",
        allow_queries=True,
        is_shared=True,
        caption="<b>Hello</b>",
        protect_content=True,
    )
    assert isinstance(sent.widget, Widget) and sent.widget.get_bot() is bot
    assert sent.content_type == ContentTypes.WIDGET
    params = session.last().params
    assert params["html"] == html and params["parse_mode"] == "HTML"
    assert params["allow_queries"] is True and params["is_shared"] is True
    assert params["width"] == params["height"] == 0
    session.respond("sendSharedWidget", result)
    resent = await bot.send_shared_widget(2, "w", chat_data="", caption="copy", parse_mode=None)
    assert isinstance(resent.widget, Widget)
    assert session.last().params == {
        "chat_id": 2,
        "widget_id": "w",
        "chat_data": "",
        "caption": "copy",
    }
    assert await bot.answer_widget_query("q", "") is True
    assert session.last().params == {"widget_query_id": "q", "data": ""}
    assert await bot.edit_message_widget_data(chat_id=1, message_id=2, chat_data="") is True
    assert session.last().params == {"chat_id": 1, "message_id": 2, "chat_data": ""}
    assert await bot.edit_shared_widget_data("w", "{}", cache_time=10) is True
    assert session.last().params == {"widget_id": "w", "public_data": "{}", "cache_time": 10}


async def test_caption_entities_disable_default_parse_mode(bot: Bot, session: FakeSession) -> None:
    await bot.send_widget(1, "a", caption="Hi", caption_entities=[])
    assert "parse_mode" not in session.last().params
    await bot.send_shared_widget(1, "w", caption="Hi", caption_entities=[])
    assert "parse_mode" not in session.last().params


async def test_answer_omission_byte_limit_and_invalid_send_no_network(
    bot: Bot, session: FakeSession
) -> None:
    await bot.answer_widget_query("q")
    assert session.last().params == {"widget_query_id": "q"}
    await bot.answer_widget_query("q", "я" * 512)
    count = len(session.requests)
    for operation in (
        bot.answer_widget_query("q", "я" * 513),
        bot.send_widget(1, ""),
        bot.send_shared_widget(1, ""),
        bot.edit_shared_widget_data("", "{}"),
        bot.answer_widget_query(""),
    ):
        with pytest.raises(ValueError):
            await operation
    assert len(session.requests) == count


async def test_raw_call_also_validates_and_does_not_retry_unsafe_writes(
    bot: Bot, session: FakeSession
) -> None:
    with pytest.raises(ValueError):
        await bot.call("sendWidget", chat_id=1, html="\0")
    assert not session.requests
    session.respond("sendWidget", NetworkError("lost response"))
    with pytest.raises(NetworkError):
        await bot.send_widget(1, "a")
    assert len(session.calls("sendWidget")) == 1
    session.fail("editSharedWidgetData", 400, "Bad Request: widget not found")
    with pytest.raises(BadRequest):
        await bot.edit_shared_widget_data("w", "{}")


@pytest.mark.parametrize("kind", ["widget_query", "shared_widget_query"])
@pytest.mark.parametrize(
    ("variant", "model"),
    [
        ("data", WidgetQueryTypeData),
        ("sign_data", WidgetQueryTypeSignData),
        ("sent_transaction", WidgetQueryTypeSentTransaction),
        ("future_type", WidgetQueryType),
    ],
)
def test_query_models_and_wallet_variants(kind: str, variant: str, model, bot: Bot) -> None:
    raw = query_update(
        kind,
        type={
            "type": variant,
            "wallet_card": {"address": "profile-wallet", "amount": "1"},
            "wallet": {"address": "device-wallet", "amount": "2", "state_init": "base64"},
            "sign_data": '{"signature":"test"}',
            "msg_hash": "hash",
        },
    )
    update = Update(raw, bot)
    q = update.event
    assert update.event_type == kind
    assert isinstance(q, WidgetQuery if kind == "widget_query" else SharedWidgetQuery)
    assert q.get_bot() is bot and q.from_user.id == q.user_id == 42
    assert type(q.type) is model and q.type.get_bot() is bot
    assert q.widget_id == "9007199254740999"
    if variant == "data":
        assert isinstance(q.type.wallet_card, TonWalletCard)
    elif variant in {"sign_data", "sent_transaction"}:
        assert isinstance(q.type.wallet, WidgetQueryWallet)
        assert q.type.wallet.state_init == "base64"
    assert q.raw == raw[kind]


def test_external_reply_widget_and_bind(bot: Bot) -> None:
    msg = Update(
        {
            "update_id": 1,
            "message": message(None, external_reply={"widget": {"html": "a", "public_data": "{}"}}),
        },
        bot,
    ).event
    assert isinstance(msg.external_reply, ExternalReplyInfo)
    assert isinstance(msg.external_reply.widget, Widget)
    assert msg.external_reply.widget.get_bot() is bot
    other = Bot("987654:test")
    assert msg.bind(other).external_reply.widget.get_bot() is other


@pytest.mark.parametrize("inline", [False, True])
async def test_original_query_shortcuts(inline: bool, bot: Bot, session: FakeSession) -> None:
    q = Update(query_update(inline=inline), bot).event
    target = {"inline_message_id": "inline-1"} if inline else {"chat_id": -5, "message_id": 7}
    await q.answer("ok")
    assert session.last().params == {"widget_query_id": "q1", "data": "ok"}
    await q.edit_data(chat_data="", public_data="{}")
    assert session.last().params == {**target, "chat_data": "", "public_data": "{}"}
    await q.edit_shared_data("", cache_time=5)
    assert session.last().params == {
        "widget_id": "9007199254740999",
        "public_data": "",
        "cache_time": 5,
    }
    scope = EventScope.from_event(q)
    assert scope.chat_id == (None if inline else -5) and scope.user_id == 42


async def test_forward_shortcuts_do_not_invent_message_coordinates(
    bot: Bot, session: FakeSession
) -> None:
    q = Update(query_update("shared_widget_query"), bot).event
    assert q.chat is None and q.message_id is None and q.edit_data is None
    assert EventScope.from_event(q).chat_id is None
    await q.answer()
    assert session.last().method == "answerWidgetQuery"
    await q.edit_shared_data("{}")
    assert session.last().params == {"widget_id": "9007199254740999", "public_data": "{}"}


async def test_static_query_rejects_shared_edit_and_missing_target(bot: Bot) -> None:
    q = WidgetQuery({"id": "q", "from": user()}, bot)
    with pytest.raises(ValueError, match="shared"):
        await q.edit_shared_data("{}")
    with pytest.raises(ValueError, match="coordinates"):
        await q.edit_data(chat_data="{}")


async def test_message_shortcuts_keep_topics_and_reply_overrides(
    bot: Bot, session: FakeSession
) -> None:
    msg = Update(
        {
            "update_id": 1,
            "message": message(
                None,
                message_id=7,
                is_topic_message=True,
                message_thread_id=10,
                business_connection_id="business",
            ),
        },
        bot,
    ).event
    await msg.answer_widget("a", caption="Hi")
    assert session.last().params["message_thread_id"] == 10
    assert "business_connection_id" not in session.last().params
    await msg.reply_widget("a")
    assert session.last().params["reply_parameters"] == {"message_id": 7}
    await msg.reply_widget("a", reply_parameters={"message_id": 9}, message_thread_id=20)
    assert session.last().params["reply_parameters"] == {"message_id": 9}
    assert session.last().params["message_thread_id"] == 20
    await msg.answer_shared_widget("w", chat_data="")
    assert session.last().method == "sendSharedWidget" and session.last().params["widget_id"] == "w"
    await msg.edit_widget_data(public_data="")
    assert session.last().params == {"chat_id": 1, "message_id": 7, "public_data": ""}


async def test_inline_builders_serialize_through_normal_inline_answer(
    bot: Bot, session: FakeSession
) -> None:
    new = InputWidgetMessageContent(
        "a", width=0, allow_queries=False, is_shared=True, public_data="{}"
    )
    shared = InputSharedWidgetMessageContent("w", chat_data="", caption="Hi")
    await bot.answer_inline_query(
        inline_query_id="i",
        results=[
            {"type": "article", "id": "1", "title": "New", "input_message_content": new},
            {"type": "article", "id": "2", "title": "Shared", "input_message_content": shared},
        ],
    )
    results = session.last().params["results"]
    assert results[0]["input_message_content"] == {
        "html": "a",
        "width": 0,
        "public_data": "{}",
        "allow_queries": False,
        "is_shared": True,
    }
    assert results[1]["input_message_content"] == {
        "widget_id": "w",
        "chat_data": "",
        "caption": "Hi",
    }
    assert "parse_mode" not in results[1]["input_message_content"]
    assert json.loads(json.dumps(results)) == results


@pytest.mark.parametrize(
    "content",
    [
        {"html": "a", "public_data": "я" * 513},
        {"html": ""},
        {"widget_id": ""},
        {"html": "a", "widget_id": "w"},
    ],
)
async def test_invalid_raw_inline_widget_rejected(
    content: dict, bot: Bot, session: FakeSession
) -> None:
    with pytest.raises(ValueError):
        await bot.answer_inline_query(
            inline_query_id="i",
            results=[
                {
                    "type": "article",
                    "id": "1",
                    "title": "Widget",
                    "input_message_content": content,
                }
            ],
        )
    assert not session.requests


@pytest.mark.parametrize("kind", ["widget_query", "shared_widget_query"])
async def test_routing_filters_di_nested_router_and_raw_webhook(
    kind: str, app: Zafather, session: FakeSession
) -> None:
    router = Router("widgets")
    app.include(router)
    captured = []

    async def middleware(event, data, next_):
        data["marker"] = "middleware"
        return await next_(event, data)

    router.middleware(middleware)

    @getattr(router, kind)(F.data == "refresh")
    async def handle(q, user_id, chat_id, marker, event_type):
        captured.append((user_id, chat_id, marker, event_type))
        await q.answer("ok")

    assert await app.handle_webhook(query_update(kind)) is True
    expected_chat = -5 if kind == "widget_query" else None
    assert captured == [(42, expected_chat, "middleware", kind)]
    assert session.last().params == {"widget_query_id": "q1", "data": "ok"}
    assert await app.feed_raw_update(query_update(kind, data="other")) is False


def test_polling_default_and_explicit_update_lists(bot: Bot) -> None:
    async def feed(update: Update) -> None:
        pass

    polling = LongPolling(bot, feed)
    assert UpdateType.WIDGET_QUERY in polling.allowed_updates
    assert UpdateType.SHARED_WIDGET_QUERY in polling.allowed_updates
    assert LongPolling(bot, feed, allowed_updates=["message"]).allowed_updates == ["message"]
