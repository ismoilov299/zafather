from __future__ import annotations

from tests.support import FakeSession, callback_update, message, user
from zafather import Bot
from zafather.types import (
    CallbackQuery,
    ChatJoinRequest,
    InlineQuery,
    ManagedBotUpdated,
    Message,
    PreCheckoutQuery,
    TelegramObject,
    Update,
    User,
    wrap_result,
)


def test_field_access_wrapping_and_aliases() -> None:
    msg = Message(message("hi", web_app_data={"data": "{}", "button_text": "Open"}))
    assert msg.text == "hi" and msg.unknown_field is None
    assert msg.from_user.full_name == "Ali Valiev"
    assert isinstance(msg.from_user, User)
    assert msg.web_app_data.button_text == "Open"
    assert msg.chat_id == 1 and msg.user_id == 1 and msg.content_type == "text"
    assert msg["message_id"] == 1 and "text" in msg and msg.get("missing", 5) == 5
    assert "from_user" in dir(msg)


def test_unknown_nested_objects_are_wrapped() -> None:
    obj = TelegramObject({"reply_markup": {"inline_keyboard": [[{"text": "a"}]]}})
    assert obj.reply_markup.inline_keyboard[0][0].text == "a"


def test_managed_bot_field_is_data_not_client() -> None:
    event = ManagedBotUpdated({"user": user(1), "bot": {"id": 777, "is_bot": True}}, Bot("1:a"))
    assert event.bot.id == 777 and event.bot_id == 777
    assert isinstance(event.get_bot(), Bot)


def test_mention_is_escaped() -> None:
    person = User({"id": 3, "first_name": "<b>A</b>"})
    assert person.mention == '<a href="tg://user?id=3">&lt;b&gt;A&lt;/b&gt;</a>'


def test_equality_and_bind(bot: Bot) -> None:
    raw = {"id": 1, "first_name": "A"}
    assert User(raw) == User(dict(raw)) and User(raw) != TelegramObject(raw)
    assert User(raw).bind(bot).get_bot() is bot


def test_unbound_object_raises_clear_error() -> None:
    import pytest

    with pytest.raises(RuntimeError, match="not bound"):
        Message(message("x"))._client()


def test_update_event_and_wrap_result() -> None:
    update = Update(callback_update("menu:1"))
    assert update.event_type == "callback_query" and isinstance(update.event, CallbackQuery)
    assert isinstance(wrap_result({"message_id": 1, "chat": {"id": 1}}), Message)
    assert isinstance(wrap_result({"id": 1, "is_bot": False}), User)
    assert isinstance(wrap_result([{"update_id": 1}])[0], Update)
    assert wrap_result(True) is True


async def test_message_helpers_send_expected_requests(bot: Bot, session: FakeSession) -> None:
    topic = Message(
        message("x", is_topic_message=True, message_thread_id=9, business_connection_id="bc"),
        bot,
    )
    await topic.answer("hi")
    assert session.last("sendMessage").params == {
        "chat_id": 1,
        "message_thread_id": 9,
        "business_connection_id": "bc",
        "text": "hi",
        "parse_mode": "HTML",
    }
    await topic.reply("re")
    assert session.last("sendMessage").params["reply_parameters"] == {"message_id": 1}

    plain = Message(message("x", chat_id=5, user_id=3, message_id=4), bot)
    await plain.answer_photo("file-id", caption="c")
    assert session.last("sendPhoto").params == {
        "chat_id": 5,
        "photo": "file-id",
        "caption": "c",
        "parse_mode": "HTML",
    }
    await plain.edit_text("new")
    assert session.last("editMessageText").params["message_id"] == 4
    await plain.react("🔥")
    assert session.last("setMessageReaction").params["reaction"] == [
        {"type": "emoji", "emoji": "🔥"}
    ]
    await plain.react(custom_emoji_id="555")
    assert session.last("setMessageReaction").params["reaction"][0]["custom_emoji_id"] == "555"
    await plain.forward(9)
    assert session.last("forwardMessage").params == {
        "chat_id": 9,
        "from_chat_id": 5,
        "message_id": 4,
    }
    await plain.delete()
    assert session.last("deleteMessage").params == {"chat_id": 5, "message_id": 4}
    await plain.answer_ephemeral("secret")
    assert session.last("sendMessage").params["ephemeral_message_parameters"] == {
        "receiver_user_id": 3
    }


async def test_callback_query_helpers(bot: Bot, session: FakeSession) -> None:
    query = Update(callback_update("x", chat_id=8), bot).event
    await query.answer("ok", show_alert=True)
    assert session.last("answerCallbackQuery").params == {
        "callback_query_id": "cb1",
        "text": "ok",
        "show_alert": True,
    }
    await query.edit_text("edited")
    assert session.last("editMessageText").params["chat_id"] == 8
    await query.answer_ephemeral("only you")
    assert session.last("sendMessage").params["ephemeral_message_parameters"] == {
        "callback_query_id": "cb1"
    }
    inline_query = CallbackQuery({"id": "q", "inline_message_id": "im", "from": user()}, bot)
    await inline_query.edit_text("inline")
    assert session.last("editMessageText").params == {
        "inline_message_id": "im",
        "text": "inline",
        "parse_mode": "HTML",
    }


async def test_query_answers(bot: Bot, session: FakeSession) -> None:
    await InlineQuery({"id": "iq", "from": user()}, bot).answer([{"type": "article"}])
    assert session.last("answerInlineQuery").params["inline_query_id"] == "iq"
    await PreCheckoutQuery({"id": "pc", "from": user()}, bot).answer(ok=False, error_message="no")
    assert session.last("answerPreCheckoutQuery").params == {
        "pre_checkout_query_id": "pc",
        "ok": False,
        "error_message": "no",
    }
    request = ChatJoinRequest({"chat": {"id": -1}, "from": user(4)}, bot)
    await request.approve()
    assert session.last("approveChatJoinRequest").params == {"chat_id": -1, "user_id": 4}
