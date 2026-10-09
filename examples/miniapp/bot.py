"""UZ: Zafather — Mini App namunasi (bot + backend).
RU: Zafather — пример Mini App (бот + backend).
EN: Zafather — Mini App example (bot + backend).

UZ: Ishga tushirish:
RU: Запуск:
EN: Run:

    pip install aiohttp
    export BOT_TOKEN="..."          # @BotFather bergan token
    export APP_URL="https://sizning-domeningiz.uz"   # HTTPS shart!
    python bot.py

UZ: Lokalda sinash uchun tunnel kerak (HTTPS majburiy):
RU: Для локальной проверки нужен tunnel (HTTPS обязателен):
EN: For local testing you need a tunnel (HTTPS is required):

    ngrok http 8080      →   export APP_URL="https://xxxx.ngrok-free.app"

UZ: Keyin @BotFather → /mybots → Bot Settings → Menu Button → APP_URL ni qo'ying,
yoki bot ishga tushganda menyu tugmasi avtomatik o'rnatiladi (pastga qarang).
RU: Затем в @BotFather → /mybots → Bot Settings → Menu Button задайте APP_URL,
либо при запуске бота кнопка меню будет настроена автоматически.
EN: Then in @BotFather → /mybots → Bot Settings → Menu Button set APP_URL,
or the menu button will be configured automatically when the bot starts.
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

# UZ: Oddiy "baza" — haqiqiy loyihada SQLite/Postgres bo'ladi.
# RU: Простая "база" — в реальном проекте это SQLite/Postgres.
# EN: A toy "database" — use SQLite/Postgres in a real project.
CLICKS: dict = {}


# === UZ: Bot tomoni / RU: Сторона бота / EN: Bot side ======================================
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
    """UZ: Reply-keyboard Mini App'dan `sendData()` orqali kelgan ma'lumot. Bu kanal
    imzolanmagan — muhim amallar uchun backend API'dan foydalaning.
    RU: Данные из Mini App reply-клавиатуры через `sendData()`. Канал не подписан —
    для важных действий используйте backend API.
    EN: Data sent by a reply-keyboard Mini App via `sendData()`. This channel is not
    signed — use the backend API for anything important.
    """
    await m.answer(f"Ilovadan keldi: <code>{web_app_data}</code>")


@bot.on_startup
async def setup_menu():
    """UZ: Menyu tugmasini Mini App'ga aylantiradi. RU: Делает кнопку меню кнопкой
    Mini App. EN: Turns the chat menu button into a Mini App button.
    """
    await bot.mini_app.set_menu_button("🚀 Ochish", APP_URL)


# === UZ/RU/EN: Backend API =================================================================
# UZ: index.html shu papkadan beriladi. RU: index.html отдаётся из этой папки.
# EN: index.html is served from this folder.
server = bot.serve_mini_app(
    static_dir=os.path.join(os.path.dirname(__file__), "webapp"),
    port=PORT,
    # UZ: 1 soatdan eski initData rad etiladi. RU: initData старше часа отклоняется.
    # EN: initData older than an hour is rejected.
    max_age=3600,
)


@server.api("/me")
async def me(user, init):
    """UZ: Kim kirganini qaytaradi; `user` — tekshirilgan ma'lumot.
    RU: Возвращает, кто вошёл; `user` — проверенные данные.
    EN: Returns who signed in; `user` is verified data.
    """
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
    """UZ: Har bosishda hisoblagichni oshiradi. RU: Увеличивает счётчик при каждом нажатии.
    EN: Increments a counter on every press.
    """
    CLICKS[user.id] = CLICKS.get(user.id, 0) + 1
    return {"clicks": CLICKS[user.id]}


@server.api("/notify")
async def notify(user, data, bot):
    """UZ: Ilovadan bot orqali xabar yuboradi. RU: Отправляет сообщение через бота из
    приложения. EN: Sends a message through the bot from the app.
    """
    text = str(data.get("text", "")).strip()[:400] or "Salom, ilovadan!"
    await bot.send_message(chat_id=user.id, text=f"📨 Ilovadan: {text}")
    return {"sent": True}


if __name__ == "__main__":
    # UZ: Server va bot polling birga ishlaydi. RU: Сервер и polling работают вместе.
    # EN: The server and bot polling run together.
    server.run()
