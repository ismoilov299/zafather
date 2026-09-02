"""Zafather — Bot API 10.2 namunasi.

Ko'rsatiladi:
  • rangli tugmalar (primary / success / danger) va premium emoji ikonkalari
  • xabarda premium (custom) emoji
  • ephemeral xabarlar (guruhda faqat bitta odamga ko'rinadi)
  • bot yaratadigan bot (managed bots + BotFarm)
  • reaksiyalar, guest mode, obunalar
"""
import logging
import os

from zafather import (
    BotFarm,
    ButtonStyle,
    CallbackQuery,
    InlineKeyboard,
    ManagedBots,
    Message,
    ReplyKeyboard,
    Router,
    Service,
    TextBuilder,
    Zafather,
    bold,
    emoji,
    quote,
)

bot = Zafather(os.getenv("BOT_TOKEN", "TOKENNI_SHU_YERGA"), parse_mode="HTML")

# Bot egangizning premium emoji id'lari (@idstickerbot orqali olinadi)
FIRE = "5368324170671202286"
STAR = "5370870893004203704"

MANAGER_USERNAME = os.getenv("MANAGER_USERNAME", "ZafatherManagerBot")


# ---------------------------------------------------------------- 1. Rangli tugmalar
@bot.command("start")
async def start(m: Message):
    kb = InlineKeyboard()
    kb.success("✅ Tasdiqlash", "act:ok")
    kb.danger("🗑 O'chirish", "act:del")
    kb.row()
    kb.primary("⭐️ Asosiy amal", "act:main", icon=STAR)   # ko'k + premium emoji ikonka
    kb.row()
    kb.copy("📋 Promokodni nusxalash", "ZAFATHER2026")
    kb.link("📖 Hujjat", "https://core.telegram.org/bots/api")

    note = quote("Tugmalar rangi Bot API 9.4 dan beri qo'llab-quvvatlanadi.", expandable=True)
    text = f"{emoji(FIRE, '🔥')} {bold('Zafather')} — Bot API 10.2\n\n{note}"
    await m.answer(text, reply_markup=kb)


@bot.callback(lambda c: c.data.startswith("act:"))
async def actions(c: CallbackQuery):
    action = c.data.split(":")[1]
    if action == "del":
        await c.answer("O'chirildi", show_alert=True)
        await c.message.delete()
    else:
        await c.answer(f"Tanlandi: {action}")


# ---------------------------------------------------------------- 2. Premium emoji + entity
@bot.command("emoji")
async def premium_emoji(m: Message):
    """Entity orqali — parse_mode kerak emas, `date_time` ham shu yo'l bilan."""
    tb = TextBuilder()
    tb.emoji(FIRE, "🔥").text(" ").bold("Premium emoji").line()
    tb.text("Oddiy matn, ").spoiler("yashirin qism").text(" va ").code("kod")
    await m.answer(tb.text_value, entities=tb.entities, parse_mode=None)


# ---------------------------------------------------------------- 3. Ephemeral (10.2)
@bot.command("secret")
async def secret(m: Message):
    """Guruhda faqat buyruq bergan odamga ko'rinadigan javob."""
    await m.answer_ephemeral("Bu xabarni faqat siz ko'rasiz 🤫")


@bot.command("like")
async def like(m: Message):
    await m.react("🔥")


# ---------------------------------------------------------------- 4. Bot yaratadigan bot
child = Router("child")          # yaratilgan botlar uchun handlerlar


@child.command("start")
async def child_start(m: Message):
    await m.answer(f"{emoji(STAR, '⭐️')} Salom! Men siz uchun yaratilgan botman.")


farm = BotFarm(child)


@bot.command("newbot")
async def new_bot(m: Message):
    """Foydalanuvchiga o'z botini yaratish taklifi."""
    suggested = f"{m.from_user.username or m.user_id}_zaf_bot"
    url = ManagedBots.create_link(MANAGER_USERNAME, suggested, name="Mening botim")

    kb = InlineKeyboard().primary("🤖 Bot yaratish", url=url)
    rk = ReplyKeyboard(one_time=True).request_bot("🤖 Mavjud botni tanlash")

    await m.answer("Yangi bot ochamizmi?", reply_markup=kb)
    await m.answer("Yoki mavjudini bering:", reply_markup=rk)


@bot.managed_bot()
async def on_managed_bot(event, bot):
    """Bot yaratilganda yoki tokeni almashganda ishlaydi."""
    token = await ManagedBots(bot).token(event.bot_id)
    if token:
        await farm.add(token)          # yangi bot shu zahoti ishga tushadi
        logging.info("Yangi bot fermaga qo'shildi. Jami: %s", farm.count)


@bot.service("managed_bot_created")
async def managed_created(m: Message, service_data):
    await m.answer("✅ Bot yaratildi va ishga tushdi!")


# ---------------------------------------------------------------- 5. Boshqa yangiliklar
@bot.reaction()
async def on_reaction(event):
    logging.info("Reaksiya o'zgardi: chat=%s", event.chat.id if event.chat else "?")


@bot.guest()
async def on_guest(event):
    """Guest mode (10.0) — bot a'zo bo'lmagan chatdagi murojaat."""
    await event.answer("Salom! Men mehmon rejimida javob beryapman.")


@bot.subscription()
async def on_subscription(event):
    """Obuna holati o'zgardi (10.2)."""
    logging.info("Obuna yangilandi: %s", event.raw)


@bot.on_shutdown
async def shutdown():
    await farm.stop_all()


if __name__ == "__main__":
    bot.run()
