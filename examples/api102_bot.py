"""UZ: Zafather — Bot API 10.2+ namunasi.
RU: Zafather — пример для Bot API 10.2+.
EN: Zafather — Bot API 10.2+ example.

UZ: Ko'rsatiladi:
RU: Показаны:
EN: Demonstrates:
  • rangli tugmalar (primary / success / danger) va premium emoji ikonkalari
  • цветные кнопки (primary / success / danger) и иконки premium emoji
  • colored buttons (primary / success / danger) and premium emoji icons
  • xabarda premium (custom) emoji
  • premium (custom) emoji в сообщениях
  • premium (custom) emoji in messages
  • ephemeral xabarlar (guruhda faqat bitta odamga ko'rinadi)
  • ephemeral-сообщения (видны только одному человеку в группе)
  • ephemeral messages (visible only to one person in a group)
  • bot yaratadigan bot (managed bots + BotFarm)
  • боты, создающие ботов (managed bots + BotFarm)
  • bots that create bots (managed bots + BotFarm)
  • reaksiyalar, guest mode, obunalar
  • реакции, guest mode, подписки
  • reactions, guest mode, subscriptions
"""

import logging
import os

from zafather import (
    BotFarm,
    CallbackQuery,
    InlineKeyboard,
    ManagedBots,
    Message,
    ReplyKeyboard,
    Router,
    TextBuilder,
    Zafather,
    bold,
    emoji,
    quote,
)

bot = Zafather(os.getenv("BOT_TOKEN", "TOKENNI_SHU_YERGA"), parse_mode="HTML")

# UZ: Premium emoji ID'lari (@idstickerbot orqali olinadi).
# RU: ID premium emoji (можно узнать через @idstickerbot).
# EN: Premium emoji IDs (look them up with @idstickerbot).
FIRE = "5368324170671202286"
STAR = "5370870893004203704"

MANAGER_USERNAME = os.getenv("MANAGER_USERNAME", "ZafatherManagerBot")


# --- 1. UZ: Rangli tugmalar / RU: Цветные кнопки / EN: Colored buttons ----------------
@bot.command("start")
async def start(m: Message):
    kb = InlineKeyboard()
    kb.success("✅ Tasdiqlash", "act:ok")
    kb.danger("🗑 O'chirish", "act:del")
    kb.row()
    # UZ: ko'k + premium emoji ikonka. RU: синяя + иконка premium emoji.
    # EN: blue + a premium emoji icon.
    kb.primary("⭐️ Asosiy amal", "act:main", icon=STAR)
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


# --- 2. UZ/RU/EN: Premium emoji + entities ----------------------------------------------
@bot.command("emoji")
async def premium_emoji(m: Message):
    """UZ: Entity orqali — parse_mode kerak emas (`date_time` ham shu yo'l bilan).
    RU: Через entities — parse_mode не нужен (так же работает `date_time`).
    EN: Via entities — no parse_mode needed (`date_time` works the same way).
    """
    tb = TextBuilder()
    tb.emoji(FIRE, "🔥").text(" ").bold("Premium emoji").line()
    tb.text("Oddiy matn, ").spoiler("yashirin qism").text(" va ").code("kod")
    await m.answer(tb.text_value, entities=tb.entities, parse_mode=None)


# --- 3. UZ/RU/EN: Ephemeral (10.2/10.3) ---------------------------------------------------
@bot.command("secret")
async def secret(m: Message):
    """UZ: Guruhda faqat buyruq bergan odamga ko'rinadigan javob.
    RU: Ответ, который в группе видит только автор команды.
    EN: A reply that only the command's author sees in a group.
    """
    await m.answer_ephemeral("Bu xabarni faqat siz ko'rasiz 🤫")


@bot.command("like")
async def like(m: Message):
    await m.react("🔥")


# --- 4. UZ: Bot yaratadigan bot / RU: Бот, создающий ботов / EN: Bots creating bots -----
# UZ: Yaratilgan botlar uchun handlerlar. RU: Обработчики для созданных ботов.
# EN: Handlers for the created bots.
child = Router("child")


@child.command("start")
async def child_start(m: Message):
    await m.answer(f"{emoji(STAR, '⭐️')} Salom! Men siz uchun yaratilgan botman.")


farm = BotFarm(child)


@bot.command("newbot")
async def new_bot(m: Message):
    """UZ: Foydalanuvchiga o'z botini yaratishni taklif qiladi.
    RU: Предлагает пользователю создать собственного бота.
    EN: Offers the user to create their own bot.
    """
    suggested = f"{m.from_user.username or m.user_id}_zaf_bot"
    url = ManagedBots.create_link(MANAGER_USERNAME, suggested, name="Mening botim")

    kb = InlineKeyboard().primary("🤖 Bot yaratish", url=url)
    rk = ReplyKeyboard(one_time=True).request_bot("🤖 Mavjud botni tanlash")

    await m.answer("Yangi bot ochamizmi?", reply_markup=kb)
    await m.answer("Yoki mavjudini bering:", reply_markup=rk)


@bot.managed_bot()
async def on_managed_bot(event, bot):
    """UZ: Bot yaratilganda yoki tokeni almashganda ishlaydi.
    RU: Срабатывает при создании бота или смене его токена.
    EN: Runs when a bot is created or its token changes.
    """
    token = await ManagedBots(bot).token(event.bot_id)
    if token:
        # UZ: Yangi bot shu zahoti ishga tushadi. RU: Новый бот запускается сразу.
        # EN: The new bot starts right away.
        await farm.add(token)
        logging.info("Yangi bot fermaga qo'shildi. Jami: %s", farm.count)


@bot.service("managed_bot_created")
async def managed_created(m: Message, service_data):
    await m.answer("✅ Bot yaratildi va ishga tushdi!")


# --- 5. UZ: Boshqa yangiliklar / RU: Другие новинки / EN: Other additions ----------------
@bot.reaction()
async def on_reaction(event):
    logging.info("Reaksiya o'zgardi: chat=%s", event.chat.id if event.chat else "?")


@bot.guest()
async def on_guest(event):
    """UZ: Guest mode (10.0) — bot a'zo bo'lmagan chatdagi murojaat.
    RU: Guest mode (10.0) — обращение в чате, где бот не состоит.
    EN: Guest mode (10.0) — a request from a chat the bot is not a member of.
    """
    await event.answer("Salom! Men mehmon rejimida javob beryapman.")


@bot.subscription()
async def on_subscription(event):
    """UZ: Obuna holati o'zgardi (10.2). RU: Изменился статус подписки (10.2).
    EN: A subscription status changed (10.2).
    """
    logging.info("Obuna yangilandi: %s", event.raw)


@bot.on_shutdown
async def shutdown():
    await farm.stop_all()


if __name__ == "__main__":
    bot.run()
