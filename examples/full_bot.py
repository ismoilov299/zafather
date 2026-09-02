"""Zafather — to'liq namuna: FSM, klaviaturalar, router, middleware, xatolar."""
import logging
import os

from zafather import (
    F,
    FSMContext,
    InlineKeyboard,
    Message,
    CallbackQuery,
    RemoveKeyboard,
    ReplyKeyboard,
    Router,
    State,
    StatesGroup,
    Zafather,
)

bot = Zafather(os.getenv("BOT_TOKEN", "TOKENNI_SHU_YERGA"), parse_mode="HTML")

ADMINS = {123456789}


# ---------------------------------------------------------------- FSM holatlar
class Anketa(StatesGroup):
    ism = State()
    yosh = State()
    shahar = State()


# ---------------------------------------------------------------- middleware
@bot.middleware
async def logger(event, data, next_):
    user = getattr(event, "from_user", None)
    logging.info("update: %s | user=%s", data["event_type"], user.id if user else "?")
    return await next_(event, data)


# ---------------------------------------------------------------- asosiy menyu
def main_menu() -> InlineKeyboard:
    kb = InlineKeyboard()
    kb.add("📝 Anketa", callback_data="menu:anketa")
    kb.add("ℹ️ Ma'lumot", callback_data="menu:info")
    kb.row()
    kb.add("🌐 Sayt", url="https://core.telegram.org/bots/api")
    return kb


@bot.command("start")
async def start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(
        f"Assalomu alaykum, <b>{m.from_user.first_name}</b>!\nQuyidagidan tanlang:",
        reply_markup=main_menu(),
    )


@bot.callback(F.data == "menu:info")
async def info(c: CallbackQuery):
    await c.answer()
    await c.edit("Bu bot <b>Zafather</b> frameworkida yozilgan.", reply_markup=main_menu())


# ---------------------------------------------------------------- anketa (FSM)
@bot.callback(F.data == "menu:anketa")
async def anketa_start(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(Anketa.ism)
    await c.answer_message("Ismingizni yozing:")


@bot.message(state=Anketa.ism)
async def anketa_ism(m: Message, state: FSMContext):
    await state.update_data(ism=m.text)
    await state.set_state(Anketa.yosh)
    await m.answer("Yoshingiz nechida?")


@bot.message(F.text.func(str.isdigit), state=Anketa.yosh)
async def anketa_yosh(m: Message, state: FSMContext):
    await state.update_data(yosh=int(m.text))
    await state.set_state(Anketa.shahar)
    kb = ReplyKeyboard(one_time=True, placeholder="Shaharni tanlang")
    kb.add("Toshkent").add("Samarqand").add("Buxoro").adjust(2)
    await m.answer("Qaysi shahardansiz?", reply_markup=kb)


@bot.message(state=Anketa.yosh)
async def anketa_yosh_xato(m: Message):
    await m.answer("Yoshni faqat raqam bilan yozing 🙂")


@bot.message(state=Anketa.shahar)
async def anketa_tugadi(m: Message, state: FSMContext):
    data = await state.update_data(shahar=m.text)
    await state.clear()
    await m.answer(
        "✅ Anketa qabul qilindi:\n"
        f"👤 {data['ism']}\n🎂 {data['yosh']}\n🏙 {data['shahar']}",
        reply_markup=RemoveKeyboard(),
    )


# ---------------------------------------------------------------- admin router
admin = Router("admin")


@admin.command("stats")
async def stats(m: Message):
    if m.from_user.id not in ADMINS:
        await m.answer("Bu buyruq faqat adminlar uchun.")
        return
    await m.answer("Statistika: bot ishlayapti ✅")


bot.include(admin)


# ---------------------------------------------------------------- media va xato
@bot.content("photo")
async def photo(m: Message):
    await m.reply(f"Rasm qabul qilindi ({len(m.photo)} o'lchamda).")


@bot.errors
async def on_error(event, exception: Exception):
    logging.exception("Xato: %s", exception)


@bot.on_startup
async def startup():
    me = await bot.bot.me()
    logging.info("Bot tayyor: @%s", me.username)


if __name__ == "__main__":
    bot.run()
