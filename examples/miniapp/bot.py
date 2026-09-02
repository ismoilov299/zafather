"""Zafather — Mini App namunasi (bot + backend).

Ishga tushirish:

    pip install aiohttp
    export BOT_TOKEN="..."          # @BotFather bergan token
    export APP_URL="https://sizning-domeningiz.uz"   # HTTPS shart!
    python bot.py

Lokalda sinash uchun tunnel kerak (HTTPS majburiy):

    ngrok http 8080      →   export APP_URL="https://xxxx.ngrok-free.app"

Keyin @BotFather → /mybots → Bot Settings → Menu Button → APP_URL ni qo'ying,
yoki bot ishga tushganda menyu tugmasi avtomatik o'rnatiladi (pastga qarang).
"""
import os
import time

from zafather import (
    InlineKeyboard,
    Message,
    WebAppData,
    Zafather,
    bold,
    direct_link,
)

TOKEN = os.getenv("BOT_TOKEN", "TOKENNI_SHU_YERGA")
APP_URL = os.getenv("APP_URL", "https://example.com")
PORT = int(os.getenv("PORT", "8080"))

bot = Zafather(TOKEN, parse_mode="HTML")

# Oddiy "baza" — haqiqiy loyihada bu SQLite/Postgres bo'ladi
CLICKS: dict = {}


# ============================================================ BOT TOMONI
@bot.command("start")
async def start(m: Message):
    kb = InlineKeyboard()
    kb.primary("🚀 Mini App'ni ochish", web_app=APP_URL)
    kb.row()
    kb.link("↗️ To'g'ridan-to'g'ri havola", direct_link("YourBot", "app", "ref_" + str(m.user_id)))
    await m.answer(
        f"{bold('Zafather Mini App')}\n\n"
        "Tugmani bosing — ilova ichida siz kimligingiz server tomonda "
        "kriptografik tekshiriladi.",
        reply_markup=kb,
    )


@bot.message(WebAppData())
async def on_web_app_data(m: Message, web_app_data):
    """Reply-keyboard Mini App'dan `sendData()` orqali kelgan ma'lumot.

    Diqqat: bu kanal imzolanmagan — muhim amallar uchun backend API'dan
    (initData tekshiruvi bilan) foydalaning.
    """
    await m.answer(f"Ilovadan keldi: <code>{web_app_data}</code>")


@bot.on_startup
async def setup_menu():
    """Chatdagi menyu tugmasini Mini App'ga aylantiradi."""
    await bot.mini_app.set_menu_button("🚀 Ochish", APP_URL)


# ============================================================ BACKEND API
# static_dir — index.html shu papkadan beriladi
server = bot.serve_mini_app(
    static_dir=os.path.join(os.path.dirname(__file__), "webapp"),
    port=PORT,
    max_age=3600,          # initData 1 soatdan eski bo'lsa rad etiladi
)


@server.api("/me")
async def me(user, init):
    """Kim kirganini qaytaradi. `user` — TEKSHIRILGAN ma'lumot."""
    return {
        "id": user.id,
        "name": user.full_name,
        "username": user.username,
        "is_premium": bool(user.is_premium),
        "language": user.language_code,
        "start_param": init.start_param,
        "checked_at": int(time.time()),
    }


@server.api("/click")
async def click(user):
    """Har bosishda hisoblagichni oshiradi — server holatiga misol."""
    CLICKS[user.id] = CLICKS.get(user.id, 0) + 1
    return {"clicks": CLICKS[user.id]}


@server.api("/notify")
async def notify(user, data, bot):
    """Ilovadan botga xabar yubortirish — ikkalasini bog'lashning eng oddiy yo'li."""
    text = str(data.get("text", "")).strip()[:400] or "Salom, ilovadan!"
    await bot.send_message(chat_id=user.id, text=f"📨 Ilovadan: {text}")
    return {"sent": True}


if __name__ == "__main__":
    # Server + bot polling birga ishlaydi
    server.run()
