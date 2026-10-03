from __future__ import annotations

import asyncio

from tests.support import FakeSession, message
from zafather import Bot, Message, RichMessage, RichStream, bold, emoji, markdown_rich


def test_builder_blocks() -> None:
    assert (
        RichMessage().heading("Hisobot").heading("Kichik", level=3).html
        == "<h1>Hisobot</h1><h3>Kichik</h3>"
    )
    paragraph = RichMessage().paragraph("Bugungi ", bold("natijalar"), " & <x>")
    assert paragraph.html == "<p>Bugungi <b>natijalar</b> &amp; &lt;x&gt;</p>"
    assert "&lt;" not in RichMessage().paragraph(emoji("1", "🔥")).html
    lists = RichMessage().bullets(["Bir", "Ikki"]).numbered(["A", "B"], start=3)
    assert lists.html == '<ul><li>Bir</li><li>Ikki</li></ul><ol start="3"><li>A</li><li>B</li></ol>'
    checklist = RichMessage().checklist(["Done", ("Todo", False)]).html
    assert 'type="checkbox" checked>Done' in checklist and 'type="checkbox">Todo' in checklist
    assert (
        '<pre><code class="language-python">if x &lt; 3:'
        in RichMessage().code("if x < 3:", "python").html
    )
    assert RichMessage().code("x").html == "<pre>x</pre>"
    table = RichMessage().table([["Oy", "Summa"], ["Avgust", 12000]], header=True)
    assert (
        table.html
        == "<table><tr><th>Oy</th><th>Summa</th></tr><tr><td>Avgust</td><td>12000</td></tr></table>"
    )
    assert RichMessage().details("More", "Inside").divider().html == (
        "<details><summary>More</summary>Inside</details><hr>"
    )
    other = RichMessage().quote("Q", expandable=True).thinking("hmm").math("x^2")
    assert "<blockquote expandable>Q</blockquote>" in other.html
    assert "<tg-thinking>hmm</tg-thinking>" in other.html and "<tg-math>x^2</tg-math>" in other.html


def test_extension_points_and_payload() -> None:
    tagged = RichMessage().tag("tg-map", "Toshkent", latitude=41.3, data_zoom='"5"')
    assert tagged.html == '<tg-map latitude="41.3" data-zoom="&quot;5&quot;">Toshkent</tg-map>'
    image = RichMessage().image('https://e/x.png"', caption="Alt")
    assert image.html == '<img src="https://e/x.png&quot;" alt="Alt">'
    rm = (
        RichMessage(is_rtl=True, skip_entity_detection=True)
        .paragraph("Matn")
        .add_media({"type": "photo"})
    )
    assert rm.to_dict() == {
        "html": "<p>Matn</p>",
        "media": [{"type": "photo"}],
        "is_rtl": True,
        "skip_entity_detection": True,
    }
    assert RichMessage().block("paragraph", text="B").to_dict() == {
        "blocks": [{"type": "paragraph", "text": "B"}]
    }
    assert RichMessage().raw("<p>r</p>").p("x").html == "<p>r</p><p>x</p>"
    assert markdown_rich("# S", is_rtl=True, media=None) == {"markdown": "# S", "is_rtl": True}
    filled = RichMessage().paragraph("a")
    assert (
        bool(filled)
        and not RichMessage()
        and len(filled) == len(filled.html)
        and str(filled) == filled.html
    )


async def test_sending_helpers(bot: Bot, session: FakeSession) -> None:
    rm = RichMessage().heading("Salom")
    await bot.send_rich(5, rm)
    assert session.last("sendRichMessage").params == {
        "chat_id": 5,
        "rich_message": {"html": "<h1>Salom</h1>"},
    }
    msg = Message(message("x", chat_id=5, message_id=7), bot)
    await msg.answer_rich(rm)
    assert session.last("sendRichMessage").params["chat_id"] == 5
    await msg.edit_rich(rm)
    assert session.last("editMessageText").params["message_id"] == 7


async def test_stream_throttles_drafts_and_finishes(bot: Bot, session: FakeSession) -> None:
    stream = RichStream(bot, 5, draft_id=77, min_interval=0.05, can_stop=True)
    await stream.push("Salom")
    await stream.push(", dunyo")
    drafts = session.calls("sendRichMessageDraft")
    assert (
        len(drafts) == 1
        and drafts[0].params["draft_id"] == 77
        and drafts[0].params["can_stop"] is True
    )
    await asyncio.sleep(0.06)
    await stream.push("!")
    drafts = session.calls("sendRichMessageDraft")
    assert len(drafts) == 2 and drafts[-1].params["rich_message"] == {"markdown": "Salom, dunyo!"}
    await stream.push("", force=True)
    assert len(session.calls("sendRichMessageDraft")) == 2
    await stream.finish()
    assert session.last().method == "sendRichMessage"


async def test_stream_context_manager_and_html_mode(bot: Bot, session: FakeSession) -> None:
    async with RichStream(bot, 5, min_interval=0, as_markdown=False, thinking="...") as stream:
        await stream.push("javob")
    draft = session.calls("sendRichMessageDraft")[0].params["rich_message"]
    assert draft == {"html": "<tg-thinking>...</tg-thinking><p>javob</p>"}
    assert session.last().params["rich_message"] == {"html": "<p>javob</p>"}
    assert 0 < RichStream(bot, 1).draft_id <= 2_147_483_647


async def test_draft_errors_do_not_break_stream(bot: Bot, session: FakeSession) -> None:
    session.fail("sendRichMessageDraft", 400, "Bad Request")
    stream = RichStream(bot, 5, min_interval=0)
    await stream.push("matn")
    assert stream.text == "matn" and repr(stream) == "<RichStream chat=5 chars=4>"
