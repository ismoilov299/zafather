from __future__ import annotations

import pytest

from zafather import (
    ButtonStyle,
    ForceReply,
    InlineKeyboard,
    RemoveKeyboard,
    ReplyKeyboard,
    SafeHTML,
    TextBuilder,
    bold,
    code,
    confirm_keyboard,
    emoji,
    escape,
    italic,
    link,
    mention,
    pre,
    quote,
    spoiler,
    strike,
    strip_custom_emoji,
    underline,
)
from zafather.text import extract_custom_emoji_ids, hashtag, utf16_length


def test_inline_keyboard_rows_and_actions() -> None:
    kb = InlineKeyboard().add("Ha", callback_data="yes").add("Yo'q", callback_data="no")
    kb.row().add("Sayt", url="https://example.com")
    assert kb.to_dict() == {
        "inline_keyboard": [
            [{"text": "Ha", "callback_data": "yes"}, {"text": "Yo'q", "callback_data": "no"}],
            [{"text": "Sayt", "url": "https://example.com"}],
        ]
    }
    assert InlineKeyboard().add("plain").rows == [[{"text": "plain", "callback_data": "plain"}]]
    assert bool(kb) and not InlineKeyboard()
    assert repr(kb) == "<InlineKeyboard rows=2 buttons=3>"


def test_colored_buttons_and_special_actions() -> None:
    kb = (
        InlineKeyboard()
        .success("Ha", "yes")
        .danger("Yo'q", "no")
        .row()
        .primary("Asosiy", "main", icon="123")
    )
    rows = kb.to_dict()["inline_keyboard"]
    assert rows[0][0]["style"] == ButtonStyle.SUCCESS and rows[0][1]["style"] == "danger"
    assert rows[1][0] == {
        "text": "Asosiy",
        "callback_data": "main",
        "style": "primary",
        "icon_custom_emoji_id": "123",
    }
    special = (
        InlineKeyboard()
        .copy("Copy", "CODE")
        .app("App", "https://app")
        .pay_button()
        .switch("Share", "q")
    )
    buttons = special.rows[0]
    assert buttons[0]["copy_text"] == {"text": "CODE"}
    assert buttons[1]["web_app"] == {"url": "https://app"}
    assert buttons[2]["pay"] is True
    assert buttons[3]["switch_inline_query"] == "q"
    current = InlineKeyboard().switch("Here", "x", current_chat=True).rows[0][0]
    assert current["switch_inline_query_current_chat"] == "x"


def test_invalid_buttons() -> None:
    with pytest.raises(ValueError):
        InlineKeyboard().add("X", "x", style="pink")
    with pytest.raises(ValueError):
        InlineKeyboard().add("X", "x" * 65)
    with pytest.raises(ValueError):
        ReplyKeyboard().add("1").adjust(0)


def test_reply_keyboard() -> None:
    rk = ReplyKeyboard(placeholder="Tanlang", one_time=True).add("1").add("2").add("3").adjust(2)
    markup = rk.to_dict()
    assert [len(row) for row in markup["keyboard"]] == [2, 1]
    assert markup["input_field_placeholder"] == "Tanlang" and markup["one_time_keyboard"] is True
    assert ReplyKeyboard().request_bot("Bot", request_id=7).rows[0][0]["request_managed_bot"] == {
        "request_id": 7
    }
    assert ReplyKeyboard().contact().location().rows[0][1]["request_location"] is True
    users = ReplyKeyboard().request_user("U", user_is_bot=False).rows[0][0]["request_users"]
    assert users["user_is_bot"] is False and users["request_id"] == 1
    group = ReplyKeyboard().request_group("G", bot_is_member=True).rows[0][0]["request_chat"]
    assert group["bot_is_member"] is True
    assert ReplyKeyboard().add("Poll", request_poll="quiz").rows[0][0]["request_poll"] == {
        "type": "quiz"
    }
    assert ReplyKeyboard().add("Poll", request_poll="").rows[0][0]["request_poll"] == {}
    assert ReplyKeyboard().danger("Cancel").rows[0][0]["style"] == "danger"


def test_keyboard_extend_and_markups() -> None:
    first = InlineKeyboard().add("a", "a")
    first.extend(InlineKeyboard().add("b", "b"))
    assert first.rows == [
        [{"text": "a", "callback_data": "a"}],
        [{"text": "b", "callback_data": "b"}],
    ]
    assert RemoveKeyboard().to_dict() == {"remove_keyboard": True, "selective": False}
    assert ForceReply("Ism").to_dict()["input_field_placeholder"] == "Ism"
    assert [b["callback_data"] for b in confirm_keyboard().rows[0]] == ["confirm:yes", "confirm:no"]


def test_html_helpers_escape_and_stay_safe() -> None:
    assert escape("<a & b>") == "&lt;a &amp; b&gt;"
    assert bold("<x>") == "<b>&lt;x&gt;</b>" and isinstance(bold("x"), SafeHTML)
    assert bold(italic("x")) == "<b><i>x</i></b>"
    assert underline("u") == "<u>u</u>" and strike("s") == "<s>s</s>"
    assert spoiler("s") == "<tg-spoiler>s</tg-spoiler>" and code("<c>") == "<code>&lt;c&gt;</code>"
    assert pre("x", "py") == '<pre><code class="language-py">x</code></pre>'
    assert link("t", 'https://e.com/?a="1"') == '<a href="https://e.com/?a=&quot;1&quot;">t</a>'
    assert mention("Ali", 5) == '<a href="tg://user?id=5">Ali</a>'
    assert quote("q", expandable=True) == "<blockquote expandable>q</blockquote>"
    assert (
        emoji("5368324170671202286", "🔥")
        == '<tg-emoji emoji-id="5368324170671202286">🔥</tg-emoji>'
    )
    assert strip_custom_emoji(f"{emoji('1', '🔥')} hi") == "🔥 hi"
    assert hashtag("news") == "#news"
    assert hashtag("#news", "@chan") == '<a href="https://t.me/chan?q=%23news">#news</a>'


def test_text_builder_uses_utf16_offsets() -> None:
    tb = (
        TextBuilder("😀 Salom ")
        .bold("dunyo")
        .text(" ")
        .emoji("777", "⭐️")
        .line()
        .link("L", "https://e")
    )
    entities = {entity["type"]: entity for entity in tb.entities}
    assert utf16_length("😀") == 2
    assert entities["bold"] == {"type": "bold", "offset": 9, "length": 5}
    assert entities["custom_emoji"]["custom_emoji_id"] == "777"
    assert entities["text_link"]["url"] == "https://e"
    assert tb.as_kwargs()["parse_mode"] is None and tb.as_kwargs()["entities"] == tb.entities
    caption = tb.as_kwargs("caption")
    assert "caption" in caption and "caption_entities" in caption
    assert str(tb) == tb.text_value and len(tb) == len(tb.text_value)
    assert TextBuilder().bold("").entities == []
    assert extract_custom_emoji_ids(tb.entities) == ["777"]
    when = TextBuilder().date_time("ertaga", unix_time=1).entities[0]
    assert when == {"type": "date_time", "offset": 0, "length": 6, "unix_time": 1}
