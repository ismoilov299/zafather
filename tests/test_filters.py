from __future__ import annotations

import pytest

from tests.support import FakeSession, message
from zafather import (
    Bot,
    ChatType,
    Command,
    ContentType,
    Ephemeral,
    ExceptionTypeFilter,
    F,
    HasCustomEmoji,
    Premium,
    Regex,
    Service,
    State,
    StateFilter,
    StatesGroup,
    Text,
    UserFilter,
)
from zafather.filters import compile_filter
from zafather.types import Message


class Form(StatesGroup):
    name = State()
    age = State()


def msg(text: str | None = "hello", **fields) -> Message:
    return Message(message(text, **fields))


async def check(target, event, data=None):
    return await compile_filter(target).check(event, data or {})


async def test_command_parsing() -> None:
    result = await Command("start")(msg("/start  salom dunyo"))
    assert result == {"command": "start", "args": "salom dunyo", "mention": None}
    assert await Command("start")(msg("/START")) == {
        "command": "start",
        "args": None,
        "mention": None,
    }
    assert await Command("start")(msg("start")) is False
    assert await Command("help")(msg("/start")) is False
    assert await Command("start", prefix="!")(msg("!start x")) == {
        "command": "start",
        "args": "x",
        "mention": None,
    }
    assert (await Command()(msg("/anything")))["command"] == "anything"


async def test_command_mention_must_target_this_bot(bot: Bot, session: FakeSession) -> None:
    data = {"bot": bot}
    assert (await Command("start")(msg("/start@ZafatherBot"), data))["mention"] == "ZafatherBot"
    assert await Command("start")(msg("/start@OtherBot"), data) is False
    assert await Command("start", ignore_mention=True)(msg("/start@OtherBot"), data)


async def test_text_and_regex() -> None:
    assert await Text("Salom")(msg("salom"))
    assert not await Text("Salom", ignore_case=False)(msg("salom"))
    assert await Text(contains="lo")(msg("hello"))
    assert await Text(startswith="he")(msg("hello"))
    assert await Text(endswith="lo")(msg("hello"))
    assert not await Text()(msg(None))
    match = await Regex(r"^(\d+)$")(msg("42"))
    assert match["match"].group(1) == "42"
    assert await Regex(r"\d")(msg("abc")) is False


async def test_chat_user_content_filters() -> None:
    group = msg("x", chat_type="supergroup")
    assert await ChatType("group", "supergroup")(group)
    assert not await ChatType("private")(group)
    assert await UserFilter(1)(group) and not await UserFilter(2)(group)
    assert await ContentType("photo")(msg(None, photo=[{"file_id": "p"}]))
    assert not await ContentType("photo")(group)


async def test_state_filter_semantics() -> None:
    assert await StateFilter(None)(msg(), {"raw_state": None})
    assert await StateFilter("*")(msg(), {"raw_state": "Form:name"})
    assert not await StateFilter("*")(msg(), {"raw_state": None})
    assert await StateFilter("*", None)(msg(), {"raw_state": None})
    assert await StateFilter(Form.name)(msg(), {"raw_state": "Form:name"})
    assert await StateFilter(Form)(msg(), {"raw_state": "Form:age"})
    assert not await StateFilter(Form.name)(msg(), {"raw_state": "Form:age"})


async def test_service_premium_ephemeral_custom_emoji() -> None:
    service = msg(None, managed_bot_created={"bot": {"id": 1}})
    assert await Service("managed_bot_created")(service) == {
        "service": "managed_bot_created",
        "service_data": service.managed_bot_created,
    }
    assert await Ephemeral()(msg("x", ephemeral_message_id=3))
    premium = Message({**message("x"), "from": {"id": 1, "is_premium": True}})
    assert await Premium()(premium) and not await Premium()(msg())
    emoji_message = msg("x", entities=[{"type": "custom_emoji", "custom_emoji_id": "77"}])
    assert await HasCustomEmoji()(emoji_message) == {"custom_emoji_ids": ["77"]}


async def test_combinators_merge_results() -> None:
    combined = Command("start") & ChatType("private")
    assert (await combined(msg("/start x")))["args"] == "x"
    assert await (Command("a") | Command("start"))(msg("/start"))
    assert await (~Command("start"))(msg("hello"))
    assert await (Text("x") | (lambda event: event.text == "hello"))(msg("hello"))


async def test_exception_type_filter() -> None:
    assert await ExceptionTypeFilter(ValueError)(None, {"exception": ValueError()})
    assert not await ExceptionTypeFilter(KeyError)(None, {"exception": ValueError()})


async def test_compiled_filter_arity_detection() -> None:
    event = msg("hello")
    assert await check(lambda e: e.text == "hello", event) == (True, {})
    assert await check(lambda e, data: data["flag"], event, {"flag": True}) == (True, {})

    async def async_filter(e):
        return {"value": 1}

    assert await check(async_filter, event) == (True, {"value": 1})
    with pytest.raises(TypeError):
        compile_filter("not callable")


async def test_magic_filter() -> None:
    event = msg("salom", chat_type="private")
    assert F.text(event) and not (~F.text)(event)
    assert (F.text == "salom")(event) and (F.text != "x")(event)
    assert (F.chat.type == "private")(event)
    assert F.text.startswith("sa")(event) and F.text.endswith("om")(event)
    assert F.text.lower().contains("lo")(event)
    assert F.text.in_(["salom", "hi"])(event)
    assert (F.text.len() > 3)(event) and not (F.text.len() > 10)(event)
    assert F.photo.is_none()(event) and F.text.is_not_none()(event)
    assert F.text.func(str.isalpha)(event)
    assert not F.text.func(int)(msg("abc"))
    assert F.text.regexp(r"^s")(event)
    assert F.entities[0].type.is_none()(event)
    assert (F.text & (F.chat.type == "private"))(event)
    assert (F.photo | F.text)(event)
    assert F.text.as_("value")(event) == {"value": "salom"}
    assert repr(F.chat.type == "private") == "F.chat.type == 'private'"


async def test_magic_combined_with_filter_objects() -> None:
    combined = F.text & Command("start")
    assert (await combined(msg("/start")))["command"] == "start"
    either = F.photo | Command("start")
    assert await either(msg("/start"))
