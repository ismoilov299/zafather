"""UZ: Zafather — Rich Messages namunasi (Bot API 10.1 / 10.2).
RU: Zafather — пример Rich Messages (Bot API 10.1 / 10.2).
EN: Zafather — Rich Messages example (Bot API 10.1 / 10.2).

UZ:  /report  — sarlavha, ro'yxat, jadval, kod bloki va yig'iladigan bo'limdan
     iborat tuzilgan xabar
RU:  /report  — структурированное сообщение с заголовком, списком, таблицей,
     блоком кода и раскрывающимся разделом
EN:  /report  — structured message with a heading, list, table, code block,
     and collapsible section

UZ:  /ask ... — javobni bo'lak-bo'lak (oqim bilan) yuborish, AI botlar uchun
RU:  /ask ... — потоковая отправка ответа частями, для AI-ботов
EN:  /ask ... — stream the answer in chunks, for AI bots
"""
import asyncio
import os

from zafather import (
    Message,
    RichMessage,
    RichStream,
    Zafather,
    bold,
    emoji,
    italic,
    link,
)

bot = Zafather(os.getenv("BOT_TOKEN", "TOKENNI_SHU_YERGA"), parse_mode="HTML")

FIRE = "5368324170671202286"


@bot.command("report")
async def report(m: Message):
    """Tuzilgan hisobot — oddiy xabarda bunday formatlash imkonsiz."""
    rm = RichMessage()
    rm.heading("Avgust hisoboti")
    rm.paragraph(emoji(FIRE, "🔥"), " Oy ", bold("rejadan oshiq"), " yakunlandi.")

    rm.heading("Asosiy ko'rsatkichlar", level=2)
    rm.table(
        [
            ["Ko'rsatkich", "Reja", "Fakt"],
            ["Sotuv", "10 000", "12 400"],
            ["Yangi mijoz", "150", "173"],
        ],
        header=True,
    )

    rm.heading("Keyingi qadamlar", level=2)
    rm.checklist([("Hisobotni yuborish", True), ("Narxni qayta ko'rish", False)])

    rm.heading("So'rov", level=2)
    rm.code("SELECT region, SUM(total)\nFROM sales\nGROUP BY region;", "sql")

    rm.details(
        "Hisoblash usuli",
        "Fakt qiymatlari CRM'dan olindi, qaytarilgan buyurtmalar chiqarib tashlandi.",
    )
    rm.divider()
    rm.paragraph(italic("Manba: "), link("CRM", "https://example.com/crm"))

    await m.answer_rich(rm)


async def fake_llm(question: str):
    """Haqiqiy loyihada bu yerda LLM'ning oqim javobi bo'ladi."""
    words = f"Savolingiz: {question}. Javob tayyorlanmoqda va bo'lak-bo'lak yuborilmoqda.".split()
    for word in words:
        await asyncio.sleep(0.15)
        yield word + " "


@bot.command("ask")
async def ask(m: Message, args):
    """Javobni oqim bilan yuborish: foydalanuvchi matn yozilishini kuzatib turadi."""
    if not args:
        await m.answer("Savolingizni yozing: <code>/ask Zafather nima?</code>")
        return

    async with RichStream(bot.bot, m.chat_id, min_interval=0.7) as stream:
        async for chunk in fake_llm(args):
            await stream.push(chunk)
    # `async with` tugagach yakuniy sendRichMessage avtomatik yuboriladi


@bot.command("thinking")
async def thinking(m: Message):
    """AI mulohazasini alohida blokda ko'rsatish."""
    rm = RichMessage()
    rm.thinking("Ma'lumotlarni tekshiryapman, uch manbani solishtiryapman…")
    rm.paragraph("Tayyor: uchala manba ham bir xil raqamni ko'rsatdi.")
    await m.answer_rich(rm)


if __name__ == "__main__":
    bot.run()
