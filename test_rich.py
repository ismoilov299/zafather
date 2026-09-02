"""Zafather — Rich Messages testlari (Telegram'ga ulanmasdan)."""
import asyncio
import sys

from zafather import (
    Message,
    RichMessage,
    RichStream,
    Zafather,
    bold,
    emoji,
    markdown_rich,
)

TOKEN = "123456:AA-TEST-TOKEN"
ok = fail = 0


def check(cond, label):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ok  — {label}")
    else:
        fail += 1
        print(f"  XATO — {label}")


def test_builder():
    print("HTML quruvchi:")
    rm = RichMessage()
    rm.heading("Hisobot").heading("Kichik", level=3)
    check(rm.html == "<h1>Hisobot</h1><h3>Kichik</h3>", "heading + level")

    rm = RichMessage().paragraph("Bugungi ", bold("natijalar"), " & <xtra>")
    check(
        rm.html == "<p>Bugungi <b>natijalar</b> &amp; &lt;xtra&gt;</p>",
        "abzats: formatlash saqlanadi, xavfli belgilar ekranlanadi",
    )

    rm = RichMessage().paragraph(emoji("5368324170671202286", "🔥"), " Chegirma")
    check("tg-emoji" in rm.html and "&lt;" not in rm.html, "premium emoji ikki marta ekranlanmadi")

    rm = RichMessage().bullets(["Bir", "Ikki"]).numbered(["A", "B"], start=3)
    check(
        rm.html == "<ul><li>Bir</li><li>Ikki</li></ul><ol start=\"3\"><li>A</li><li>B</li></ol>",
        "ro'yxatlar (belgili va raqamli)",
    )

    rm = RichMessage().checklist(["Bajarildi", ("Qoldi", False)])
    check(
        'type="checkbox" checked>Bajarildi' in rm.html and 'type="checkbox">Qoldi' in rm.html,
        "checklist: belgilangan va belgilanmagan",
    )

    rm = RichMessage().code("if x < 3:\n    pass", "python")
    check(
        '<pre><code class="language-python">if x &lt; 3:' in rm.html,
        "kod bloki: til + ekranlash",
    )

    rm = RichMessage().table([["Oy", "Summa"], ["Avgust", 12000]], header=True)
    check(
        rm.html == "<table><tr><th>Oy</th><th>Summa</th></tr><tr><td>Avgust</td><td>12000</td></tr></table>",
        "jadval: sarlavha qatori th bo'ldi",
    )

    rm = RichMessage().details("Batafsil", "Ichki matn").divider()
    check(
        rm.html == "<details><summary>Batafsil</summary>Ichki matn</details><hr>",
        "yig'iladigan bo'lim + ajratgich",
    )

    rm = RichMessage().quote("Sitata", expandable=True).thinking("mulohaza")
    check(
        "<blockquote expandable>Sitata</blockquote>" in rm.html
        and "<tg-thinking>mulohaza</tg-thinking>" in rm.html,
        "sitata (yig'iladigan) va thinking bloki",
    )

    rm = RichMessage().tag("tg-map", "Toshkent", latitude=41.3, longitude=69.2)
    check(
        rm.html == '<tg-map latitude="41.3" longitude="69.2">Toshkent</tg-map>',
        "tag(): noma'lum bloklar uchun kengaytma",
    )

    rm = RichMessage(is_rtl=True, skip_entity_detection=True).paragraph("Matn")
    payload = rm.to_dict()
    check(
        payload == {"html": "<p>Matn</p>", "is_rtl": True, "skip_entity_detection": True},
        "to_dict(): html + bayroqlar",
    )

    rm = RichMessage().block("paragraph", text="Blok usuli")
    check(
        rm.to_dict() == {"blocks": [{"type": "paragraph", "text": "Blok usuli"}]},
        "block(): 10.2 blok usuli",
    )

    check(
        markdown_rich("# Salom", is_rtl=True) == {"markdown": "# Salom", "is_rtl": True},
        "markdown_rich(): markdown maydoni",
    )

    rm = RichMessage().paragraph("a")
    check(bool(rm) and len(rm) == len(rm.html) and str(rm) == rm.html, "bool / len / str")


async def test_sending():
    print("\nYuborish:")
    app = Zafather(TOKEN)
    sent = []

    async def fake_request(method, **kwargs):
        sent.append((method, kwargs))
        return {"message_id": 1, "chat": {"id": 5, "type": "private"}, "date": 0}

    async def fake_call(method, **kwargs):
        sent.append((method, kwargs))
        return {"ok": True}

    app.bot.request = fake_request
    app.bot.call = fake_call

    rm = RichMessage().heading("Salom")
    await app.bot.send_rich(5, rm)
    check(
        sent[-1][0] == "sendRichMessage"
        and sent[-1][1]["rich_message"] == {"html": "<h1>Salom</h1>"},
        "bot.send_rich()",
    )

    msg = Message({"message_id": 7, "date": 0, "chat": {"id": 5, "type": "private"}}, app.bot)
    await msg.answer_rich(rm)
    check(sent[-1][1]["chat_id"] == 5, "message.answer_rich()")

    await msg.edit_rich(rm)
    check(
        sent[-1][0] == "editMessageText" and sent[-1][1]["message_id"] == 7,
        "message.edit_rich()",
    )

    # --- oqim ---
    sent.clear()
    stream = RichStream(app.bot, 5, min_interval=0.05)
    await stream.push("Salom")
    await stream.push(", dunyo")          # interval o'tmagan — yuborilmaydi
    drafts = [s for s in sent if s[0] == "sendRichMessageDraft"]
    check(len(drafts) == 1, f"oqim: interval ichida bitta qoralama ({len(drafts)})")

    await asyncio.sleep(0.06)
    await stream.push("!")
    drafts = [s for s in sent if s[0] == "sendRichMessageDraft"]
    check(len(drafts) == 2, "oqim: interval o'tgach yangi qoralama")
    check(drafts[-1][1]["rich_message"] == {"markdown": "Salom, dunyo!"}, "oqim: matn yig'ildi")

    await stream.finish()
    check(sent[-1][0] == "sendRichMessage", "oqim: yakuniy xabar yuborildi")

    sent.clear()
    async with RichStream(app.bot, 5, min_interval=0.05) as s2:
        await s2.push("javob")
    check(sent[-1][0] == "sendRichMessage", "async with: chiqishda avtomatik yakunlanadi")

    # qoralama xatosi oqimni to'xtatmasligi kerak
    async def broken_call(method, **kwargs):
        raise RuntimeError("tarmoq")

    app.bot.call = broken_call
    s3 = RichStream(app.bot, 5, min_interval=0)
    await s3.push("matn")
    check(s3.text == "matn", "qoralama xatosi oqimni to'xtatmadi")


def main():
    test_builder()
    asyncio.run(test_sending())
    print(f"\nNatija: {ok} ta test o'tdi, {fail} ta xato.")
    return fail


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
