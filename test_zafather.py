"""Zafather uchun oflayn testlar (Telegram'ga ulanmasdan)."""
import asyncio
import sys

from zafather import (
    BotFarm,
    ButtonStyle,
    Command,
    F,
    FSMContext,
    InlineKeyboard,
    Invoice,
    LabeledPrice,
    Message,
    Regex,
    ReplyKeyboard,
    Router,
    ManagedBots,
    State,
    StatesGroup,
    TextBuilder,
    Update,
    UpdateType,
    Zafather,
    emoji,
)

SENT = []


def make_app():
    app = Zafather("123456:TEST-TOKEN")

    async def fake_request(method, **kwargs):
        SENT.append((method, kwargs))
        return {"ok": True}

    app.bot.request = fake_request
    app.bot.send_message = lambda **kw: fake_request("sendMessage", **kw)
    app.bot.answer_callback_query = lambda **kw: fake_request("answerCallbackQuery", **kw)
    return app


def msg(text, chat_id=1, user_id=1, update_id=1):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 0,
            "text": text,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Ali", "last_name": "Valiev"},
        },
    }


def cb(data, chat_id=1, user_id=1, update_id=2):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": "cb1",
            "data": data,
            "from": {"id": user_id, "is_bot": False, "first_name": "Ali"},
            "message": {
                "message_id": 5,
                "date": 0,
                "chat": {"id": chat_id, "type": "private"},
            },
        },
    }


class Form(StatesGroup):
    name = State()
    age = State()


async def main():
    ok = 0
    app = make_app()

    # 1. command + argumentlar
    @app.command("start")
    async def start(m: Message, command: str, args):
        await m.answer(f"cmd={command} args={args} user={m.from_user.full_name}")

    # 2. F magic filtri
    @app.message(F.text == "salom")
    async def hello(m: Message):
        await m.answer("va alaykum")

    # 3. Regex + match
    @app.message(Regex(r"^\d+$"), state=None)
    async def digits(m: Message, match):
        await m.answer(f"raqam: {match.group(0)}")

    # 4. FSM
    @app.command("form")
    async def form_start(m: Message, state: FSMContext):
        await state.set_state(Form.name)
        await m.answer("Ismingiz?")

    @app.message(state=Form.name)
    async def form_name(m: Message, state: FSMContext):
        await state.update_data(name=m.text)
        await state.set_state(Form.age)
        await m.answer("Yoshingiz?")

    @app.message(state=Form.age)
    async def form_age(m: Message, state: FSMContext):
        data = await state.update_data(age=m.text)
        await state.clear()
        await m.answer(f"{data['name']}, {data['age']} yosh")

    # 5. sub-router + callback
    admin = Router("admin")

    @admin.callback(F.data.startswith("menu:"))
    async def menu(c):
        await c.answer("ok")

    app.include(admin)

    # 6. middleware
    trace = []

    @app.middleware
    async def logger(event, data, next_):
        trace.append(getattr(event, "text", None) or getattr(event, "data", None))
        return await next_(event, data)

    async def feed(raw):
        SENT.clear()
        return await app.feed_update(Update(raw, app.bot))

    def expect(cond, label):
        nonlocal ok
        if cond:
            ok += 1
            print(f"  ok  — {label}")
        else:
            print(f"  XATO — {label} | SENT={SENT}")

    print("Zafather testlari:")

    await feed(msg("/start salom dunyo"))
    expect(SENT and "cmd=start args=salom dunyo" in SENT[0][1]["text"], "Command + args")
    expect("Ali Valiev" in SENT[0][1]["text"], "from_user.full_name")

    await feed(msg("salom"))
    expect(SENT and SENT[0][1]["text"] == "va alaykum", "F.text == 'salom'")

    await feed(msg("12345"))
    expect(SENT and SENT[0][1]["text"] == "raqam: 12345", "Regex + match injection")

    handled = await feed(msg("mos kelmaydigan matn"))
    expect(handled is False, "mos handler yo'q -> False")

    await feed(msg("/form"))
    expect(SENT and SENT[0][1]["text"] == "Ismingiz?", "FSM: boshlanish")
    await feed(msg("Ali"))
    expect(SENT and SENT[0][1]["text"] == "Yoshingiz?", "FSM: name holati")
    await feed(msg("20"))
    expect(SENT and SENT[0][1]["text"] == "Ali, 20 yosh", "FSM: data saqlandi")
    expect(await FSMContext(app.storage, (1, 1)).get_state() is None, "FSM: clear()")

    await feed(cb("menu:main"))
    expect(SENT and SENT[0][0] == "answerCallbackQuery", "sub-router callback")

    expect(len(trace) >= 8, f"middleware ishladi ({len(trace)} ta)")

    # klaviaturalar
    kb = InlineKeyboard().add("Ha", callback_data="yes").add("Yo'q", callback_data="no")
    kb.row().add("Sayt", url="https://example.com")
    expect(kb.to_dict()["inline_keyboard"] == [
        [{"text": "Ha", "callback_data": "yes"}, {"text": "Yo'q", "callback_data": "no"}],
        [{"text": "Sayt", "url": "https://example.com"}],
    ], "InlineKeyboard qatorlari")

    rk = ReplyKeyboard(placeholder="Tanlang").add("1").add("2").add("3").adjust(2)
    expect([len(r) for r in rk.to_dict()["keyboard"]] == [2, 1], "ReplyKeyboard.adjust")

    # F filtrlarining mantiqiy amallari
    m = Message(msg("salom")["message"])
    expect(bool(F.text(m)) and not bool((~F.text)(m)), "F.text va ~F.text")
    expect(bool((F.text & (F.chat.type == "private"))(m)), "F & F")
    expect(bool(F.text.startswith("sa")(m)), "F.text.startswith")
    expect(bool(F.photo.is_none()(m)), "F.photo.is_none()")

    # Command filtri prefiks/mention
    c = Command("start")
    expect(bool(await c(Message(msg("/start@ZafatherBot")["message"]))), "Command + @mention")
    expect(not await c(Message(msg("start")["message"])), "prefiksiz -> mos emas")

    # --- Bot API 10.3 imkoniyatlari ---
    kb2 = InlineKeyboard()
    kb2.success("Ha", "yes").danger("Yo'q", "no").row().primary("Asosiy", "main", icon="123")
    rows = kb2.to_dict()["inline_keyboard"]
    expect(rows[0][0]["style"] == ButtonStyle.SUCCESS and rows[0][1]["style"] == "danger",
           "rangli tugmalar (success/danger)")
    expect(rows[1][0] == {"text": "Asosiy", "callback_data": "main",
                          "style": "primary", "icon_custom_emoji_id": "123"},
           "primary + premium emoji ikonka")

    kb3 = InlineKeyboard().copy("Nusxalash", "KOD2026")
    expect(kb3.to_dict()["inline_keyboard"][0][0]["copy_text"] == {"text": "KOD2026"},
           "copy_text tugmasi")

    rb = ReplyKeyboard().request_bot("Bot tanlash", request_id=7)
    expect(rb.to_dict()["keyboard"][0][0]["request_managed_bot"] == {"request_id": 7},
           "request_managed_bot tugmasi (9.6)")

    try:
        InlineKeyboard().add("X", "x", style="pushti")
        bad_style = False
    except ValueError:
        bad_style = True
    expect(bad_style, "noto'g'ri style -> ValueError")

    expect(emoji("5368324170671202286", "🔥") ==
           '<tg-emoji emoji-id="5368324170671202286">🔥</tg-emoji>', "premium emoji HTML")

    tb = TextBuilder("Salom ").bold("dunyo").text(" ").emoji("777", "⭐️")
    ents = {e["type"]: e for e in tb.entities}
    expect(tb.text_value == "Salom dunyo ⭐️", "TextBuilder matni")
    expect(ents["bold"]["offset"] == 6 and ents["bold"]["length"] == 5, "entity offset/length")
    expect(ents["custom_emoji"]["custom_emoji_id"] == "777", "custom_emoji entity")

    expect(ManagedBots.create_link("Manager", "@yangi_bot", name="Mening botim") ==
           "https://t.me/newbot/Manager/yangi_bot?name=Mening%20botim",
           "managed bot yaratish havolasi")

    expect(len(UpdateType.ALL) == 27 and "managed_bot" in UpdateType.ALL
           and "guest_message" in UpdateType.ALL and "subscription" in UpdateType.ALL
           and "stopped_message_generation" in UpdateType.ALL,
           f"27 ta update turi ({len(UpdateType.ALL)})")

    app2 = make_app()
    handled_types = []

    @app2.managed_bot()
    async def _mb(event):
        handled_types.append("managed_bot")

    @app2.guest()
    async def _g(event):
        handled_types.append("guest_message")

    @app2.subscription()
    async def _s(event):
        handled_types.append("subscription")

    @app2.stopped_generation()
    async def _stop(event):
        handled_types.append("stopped_message_generation")

    await app2.feed_update(Update({"update_id": 9, "managed_bot": {
        "user": {"id": 1, "is_bot": False, "first_name": "A"},
        "bot": {"id": 555, "is_bot": True, "first_name": "Child"}}}, app2.bot))
    await app2.feed_update(Update({"update_id": 10, "guest_message": {
        "message_id": 1, "date": 0, "text": "hi", "chat": {"id": 5, "type": "group"}}}, app2.bot))
    await app2.feed_update(Update({"update_id": 11, "subscription": {
        "from": {"id": 1, "is_bot": False, "first_name": "A"}}}, app2.bot))
    await app2.feed_update(Update({"update_id": 12, "stopped_message_generation": {
        "chat": {"id": 1, "type": "private"}}}, app2.bot))
    expect(handled_types == [
        "managed_bot", "guest_message", "subscription", "stopped_message_generation"
    ],
           f"yangi update turlari yo'naltirildi: {handled_types}")

    farm = BotFarm(Router("child"))
    expect(farm.count == 0 and farm._key("123456:ABC") == "123456", "BotFarm asoslari")

    m2 = Message({"message_id": 1, "date": 0, "text": "x",
                  "chat": {"id": 5, "type": "group"}, "ephemeral_message_id": 42,
                  "from": {"id": 3, "is_bot": False, "first_name": "A"}}, app.bot)
    expect(m2.is_ephemeral and m2.ephemeral_message_id == 42, "ephemeral xabar (10.2/10.3)")

    SENT.clear()
    await m2.answer_ephemeral("sir")
    expect(SENT and SENT[0][1]["ephemeral_message_parameters"] == {"receiver_user_id": 3},
           "message.answer_ephemeral(): 10.3 parametri")

    SENT.clear()
    c2 = Update(cb("x"), app.bot).event
    await c2.answer_ephemeral("sir")
    expect(SENT and SENT[0][1]["ephemeral_message_parameters"] == {"callback_query_id": "cb1"},
           "callback.answer_ephemeral(): 10.3 parametri")

    SENT.clear()
    await m2.react("🔥")
    expect(SENT and SENT[0][1]["reaction"] == [{"type": "emoji", "emoji": "🔥"}],
           "message.react()")

    invoice = Invoice(
        title="VIP access",
        description="One month access",
        start_parameter="stars_1",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=250)],
        provider_data=None,
        payload="vip_1",
    )
    expect(invoice.to_dict()["currency"] == "XTR", "Invoice currency is XTR")
    expect(invoice.to_dict()["prices"][0]["amount"] == 250, "Invoice price is serialized")

    app3 = make_app()
    SENT.clear()
    await app3.bot.stars.balance(user_id=42)
    expect(SENT and SENT[0][0] == "getStarBalance" and SENT[0][1]["user_id"] == 42,
           "bot.stars.balance() calls getStarBalance")

    SENT.clear()
    await app3.bot.answer_pre_checkout_query(pre_checkout_query_id="pcq_1", ok=True)
    expect(SENT and SENT[0][0] == "answerPreCheckoutQuery" and SENT[0][1]["ok"] is True,
           "bot.answer_pre_checkout_query() calls answerPreCheckoutQuery")

    print(f"\nNatija: {ok} ta test o'tdi.")
    return ok


if __name__ == "__main__":
    total = asyncio.run(main())
    sys.exit(0 if total >= 36 else 1)
