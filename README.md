# Zafather

[![PyPI](https://img.shields.io/pypi/v/zafather.svg)](https://pypi.org/project/zafather/)
[![Python](https://img.shields.io/pypi/pyversions/zafather.svg)](https://pypi.org/project/zafather/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-FFDD00?logo=buymeacoffee&logoColor=black)](https://www.buymeacoffee.com/ismoilov299)

## UZ / RU / EN

### O'zbekcha
**Zafather** — Telegram botlar yozish uchun yengil, async va tashqi bog'liqliklari kam framework.
Faqat bitta kutubxonaga (`aiohttp`) tayanadi, ichini o'qib tushunish oson.

**Bot API 10.3** darajasida: rangli tugmalar, premium emoji, bot yaratadigan botlar,
ephemeral xabarlar, guest mode, reaksiyalar, obunalar.

### Русский
**Zafather** — лёгкий async-фреймворк для создания Telegram-ботов с минимальными зависимостями.
Поддерживает только одну библиотеку (`aiohttp`), код читабелен и прост в изучении.

**Bot API 10.3**: цветные кнопки, premium emoji, боты, создающие ботов,
 ephemeral-сообщения, guest mode, реакции, подписки.

### English
**Zafather** — a lightweight async framework for building Telegram bots with minimal dependencies.
It relies on only one library (`aiohttp`) and is designed to be easy to read and understand.

**Bot API 10.3** support includes colored buttons, premium emoji, bots that create bots,
 ephemeral messages, guest mode, reactions, and subscriptions.

Muallif va yetakchi dasturchi — [**ismoilov299**](https://github.com/ismoilov299).

Hujjatlar: [O'zbekcha](docs/uz/index.md) · [Русский](docs/ru/index.md) · [English](docs/en/index.md)


```python
from zafather import Zafather, Message, F

bot = Zafather("TOKEN")

@bot.command("start")
async def start(m: Message):
    await m.answer(f"Salom, <b>{m.from_user.first_name}</b>!")

@bot.message(F.text)
async def echo(m: Message):
    await m.answer(m.text)

bot.run()
```

---

## O'rnatish

```bash
pip install zafather
# Mini App'ning uchinchi-tomon (Ed25519) tekshiruvi kerak bo'lsa:
pip install "zafather[miniapp]"
# Mustaqil MTProto userbot kerak bo'lsa:
pip install "zafather[userbot]"
```

Repozitoriydan (ishlab chiqish uchun):

```bash
pip install -e ".[miniapp]"
```

Yangi loyiha yaratish:

```bash
python -m zafather new mening_botim
cd mening_botim
python bot.py
```

---

## Imkoniyatlar

| Imkoniyat | Tavsif |
|---|---|
| Router | Handlerlarni modullarga bo'lish (`bot.include(admin_router)`) |
| Filtrlar | `Command`, `Text`, `Regex`, `ChatType`, `ContentType`, `UserFilter` |
| `F` sehrli filtr | `F.text == "salom"`, `F.data.startswith("menu:")`, `~F.photo` |
| FSM | `StatesGroup`, `State`, `FSMContext`, Memory/JSON storage |
| **i18n** | `I18n` middleware, `language_code` asosida tarjimalar va fallback |
| **Userbot** | Mustaqil MTProto client orqali akkauntlar bilan ishlash |
| **TL protocol** | Telethon'siz TL binary serializer, request builder va reader |
| Klaviaturalar | `InlineKeyboard`, `ReplyKeyboard`, `RemoveKeyboard`, `ForceReply` |
| Middleware | Har bir update oldidan/keyin kod ishlatish |
| To'liq API | Har qanday Telegram metodi: `bot.bot.any_method(...)` |
| **Rangli tugmalar** | `.primary()` / `.success()` / `.danger()` (Bot API 9.4+) |
| **Premium emoji** | `emoji(id, "🔥")` va tugma ikonkalari (`icon=`) |
| **Managed bots** | Bot yaratadigan bot: `ManagedBots`, `BotFarm`, `bot.spawn()` |
| **Ephemeral** | `m.answer_ephemeral(...)` — guruhda bitta odamga ko'rinadi (10.2/10.3) |
| Yangi update'lar | `@bot.managed_bot`, `@bot.guest`, `@bot.subscription`, `@bot.reaction` |
| Xatolar | Avtomatik qayta urinish, 429 flood-limit, `@bot.errors` |
| Webhook | `await bot.handle_webhook(payload)` (FastAPI/aiohttp bilan) |
| **Mini App** | `initData` tekshiruvi (HMAC + Ed25519), tayyor backend server |
| **Rich Messages** | Sarlavha, jadval, kod, yig'iladigan bo'lim + AI javobini oqim bilan |

---

## Bot API 10.2/10.3 imkoniyatlari

### Rangli tugmalar (9.4+)

Uch xil rang mavjud: `primary` (ko'k), `success` (yashil), `danger` (qizil).

```python
kb = InlineKeyboard()
kb.success("✅ Tasdiqlash", "ok")
kb.danger("🗑 O'chirish", "del")
kb.row()
kb.primary("⭐️ Asosiy", "main", icon="5370870893004203704")  # + premium emoji ikonka
kb.copy("📋 Nusxalash", "PROMO2026")
await m.answer("Tanlang", reply_markup=kb)

# tayyor tasdiqlash klaviaturasi
from zafather import confirm_keyboard
await m.answer("Rostdanmi?", reply_markup=confirm_keyboard())
```

`ReplyKeyboard` ham bir xil ishlaydi: `rk.danger("Bekor qilish")`.

### Premium (custom) emoji

```python
from zafather import emoji, bold

await m.answer(f"{emoji('5368324170671202286', '🔥')} {bold('Chegirma!')}")
```

> Bot custom emoji yuborishi uchun **bot egasida Telegram Premium** bo'lishi
> kerak (Bot API 9.4), yoki bot Fragment'da username sotib olgan bo'lishi kerak.
> `fallback` — emoji ko'rinmasa chiqadigan oddiy emoji.

`parse_mode` ishlatmasdan, entity orqali (`date_time` kabi HTML'da yo'q turlar uchun):

```python
tb = TextBuilder("Uchrashuv: ").bold("ertaga").text(" ").emoji("5368324170671202286", "🔥")
await m.answer(tb.text_value, entities=tb.entities, parse_mode=None)
```

### Bot yaratadigan bot (Managed Bots, 9.6+)

```python
from zafather import BotFarm, ManagedBots, Router

child = Router("child")            # yaratilgan botlar uchun handlerlar

@child.command("start")
async def child_start(m):
    await m.answer("Men siz uchun yaratilgan botman!")

farm = BotFarm(child)

@bot.command("newbot")
async def new_bot(m):
    url = ManagedBots.create_link("MyManagerBot", "yangi_bot", name="Mening botim")
    await m.answer("Bot ochamizmi?", reply_markup=InlineKeyboard().primary("🤖 Yaratish", url=url))

@bot.managed_bot()                 # bot yaratilganda keladi
async def on_managed_bot(event, bot):
    token = await ManagedBots(bot).token(event.bot_id)
    await farm.add(token)          # yangi bot shu zahoti ishga tushadi
```

Talab: @BotFather'da manager botga *Bot Management Mode* yoqilgan bo'lishi kerak.

### Ephemeral xabarlar (10.2/10.3)

```python
@bot.command("secret")
async def secret(m):
    await m.answer_ephemeral("Buni faqat siz ko'rasiz 🤫")   # guruhda ham

@bot.callback(F.data == "info")
async def info(c):
    await c.answer_ephemeral("Faqat sizga")
```

### Reaksiyalar, guest mode, obunalar

```python
await m.react("🔥")                              # reaksiya qo'yish
await m.react(custom_emoji_id="5368324170671202286")   # premium reaksiya

@bot.reaction()        # kimdir reaksiya qo'ydi
@bot.guest()           # bot a'zo bo'lmagan chatdagi murojaat (10.0)
@bot.subscription()    # obuna holati o'zgardi (10.2)
@bot.business_message()
@bot.boost()
@bot.service("managed_bot_created", "gift")      # xizmat xabarlari
```

> Muhim: yangi update turlari (`managed_bot`, `guest_message`, `subscription`,
> `message_reaction`) aniq so'ralmasa Telegram ularni yubormaydi. Zafather
> `allowed_updates` ni avtomatik to'liq ro'yxatga qo'yadi.

---

## Asosiy tushunchalar

### i18n

`I18n` middleware foydalanuvchining Telegram `language_code` maydonidan tilni
tanlaydi va handlerga `_` tarjima funksiyasini uzatadi. `ru-RU` kabi qiymatlar
`ru` tiliga normallashtiriladi; tarjima topilmasa `default_locale` ishlatiladi.

```python
from zafather import I18n

i18n = I18n({
    "uz": {"welcome": "Salom, {name}!"},
    "ru": {"welcome": "Привет, {name}!"},
    "en": {"welcome": "Hello, {name}!"},
}, default_locale="en")
bot.middleware(i18n)

@bot.command("start")
async def start(m, _):
    await m.answer(_("welcome", name=m.from_user.first_name))
```

Handler kerak bo'lsa `locale` yoki `i18n` argumentlarini ham qabul qilishi mumkin.

### Userbot (MTProto)

Bot API userbotlarga kira olmaydi, shuning uchun Zafather alohida mustaqil
MTProto client beradi. O'rnatish: `pip install "zafather[userbot]"`.

```python
from zafather import UserBot

userbot = UserBot(
    api_id=12345,
    api_hash="API_HASH",
    session="my_account",
)

@userbot.on_message(pattern="/hello")
async def hello(event):
    await event.respond("Salom!")

await userbot.run()
```

Event decoratorlari uchun `on_new_message()` va `on_callback_query()` aliaslari,
manual boshqaruv uchun `add_handler()` / `remove_handler()` ham mavjud. Sessionni
avtomatik yopish uchun `async with UserBot(...) as userbot:` ishlatish mumkin.

Universal MTProto request uchun:

```python
result = await userbot.invoke(request)
```

TL requestlar uchun past darajadagi builderlar ham mavjud:

```python
from zafather import TLRequest

request = TLRequest(0x12345678).int32(7).string("hello")
result = await userbot.invoke(request.to_bytes())
```

`api_id` va `api_hash` Telegram my.telegram.org saytidan olinadi. Session faylini
maxfiy saqlang; uni repositoryga qo'shmang. MTProto auth, encryption va TL schema
qatlamlari mustaqil ravishda rivojlantirilmoqda; custom transport backendini
`transport=` orqali ulash mumkin. Default transport MTProto Abridged TCP bo'lib,
DC host/port `dc_host=` va `dc_port=` bilan almashtiriladi.
Auth key, DC, server salt va user ID `MTProtoSession` orqali session faylida
saqlanadi.

MTProto 2.0 uchun `AuthKey` AES-IGE encryption, `auth_key_id` va `msg_key`
derivationni bajaradi. Kriptografiya faqat userbot extra orqali o'rnatiladi:
`pip install "zafather[userbot]"`. Session fayli imkon qadar `0600` permission
bilan yoziladi.

### 1. Handler e'lon qilish

```python
@bot.command("start", "boshla")        # /start yoki /boshla
async def h(m: Message, command, args):
    ...

@bot.message(F.text == "salom")        # aniq matn
@bot.message(Regex(r"^\d+$"))          # regex, handlerga `match` keladi
@bot.content("photo", "video")         # media turi
@bot.callback(F.data.startswith("x:")) # inline tugma
@bot.on("my_chat_member")              # xohlagan update turi
```

Handler faqat **o'ziga kerak bo'lgan argumentlarni** so'raydi — framework avtomatik uzatadi:

| Argument | Nima |
|---|---|
| `state` | `FSMContext` |
| `bot` | `Bot` klienti |
| `command`, `args` | `Command` filtridan |
| `match` | `Regex` filtridan |
| `chat_id`, `user_id` | Qulaylik uchun |
| `app` | `Zafather` obyekti |

### 2. `F` sehrli filtri

```python
F.text                       # matn bor
F.text == "salom"            # teng
F.data.startswith("menu:")   # boshlanadi
F.chat.type == "private"     # shaxsiy chat
F.text.func(str.isdigit)     # ixtiyoriy funksiya
F.photo | F.video            # yoki
F.text & (F.chat.type == "private")   # va
~F.text                      # inkor
```

### 3. FSM (ko'p bosqichli suhbat)

```python
class Anketa(StatesGroup):
    ism = State()
    yosh = State()

@bot.command("anketa")
async def s1(m: Message, state: FSMContext):
    await state.set_state(Anketa.ism)
    await m.answer("Ismingiz?")

@bot.message(state=Anketa.ism)
async def s2(m: Message, state: FSMContext):
    await state.update_data(ism=m.text)
    await state.set_state(Anketa.yosh)
    await m.answer("Yoshingiz?")

@bot.message(state=Anketa.yosh)
async def s3(m: Message, state: FSMContext):
    data = await state.update_data(yosh=m.text)
    await state.clear()
    await m.answer(f"{data['ism']} — {data['yosh']}")
```

> `state=None` — "faqat holatsiz foydalanuvchilar", `state="*"` — "istalgan holat".

Saqlash joyini almashtirish:

```python
from zafather import JSONStorage
bot = Zafather(TOKEN, storage=JSONStorage("holatlar.json"))
```

### 4. Klaviaturalar

```python
kb = InlineKeyboard()
kb.add("Ha", callback_data="yes").add("Yo'q", callback_data="no")
kb.row().add("Sayt", url="https://example.com")
await m.answer("Tanlang", reply_markup=kb)

rk = ReplyKeyboard(one_time=True).add("1").add("2").add("3").adjust(2)
```

### 5. Router (kodni bo'lish)

```python
# handlers/admin.py
from zafather import Router, Message
admin = Router("admin")

@admin.command("stats")
async def stats(m: Message): ...

# bot.py
from handlers.admin import admin
bot.include(admin)
```

### 6. Middleware

```python
@bot.middleware
async def auth(event, data, next_):
    data["db"] = my_db          # handlerga `db` argumenti sifatida keladi
    return await next_(event, data)
```

### 7. Xom API metodlari

Har qanday Telegram metodi snake_case bilan ishlaydi:

```python
await bot.bot.send_dice(chat_id=123)
await bot.bot.ban_chat_member(chat_id=1, user_id=2)
await bot.bot.set_my_commands(commands=[{"command": "start", "description": "Boshlash"}])
```

Fayl yuborish:

```python
from zafather import InputFile
await m.answer_photo(InputFile("rasm.jpg"), caption="Salom")
```

### 8. Webhook

```python
# FastAPI bilan
@app.post("/webhook")
async def webhook(payload: dict):
    await bot.handle_webhook(payload)
    return {"ok": True}
```

---

## Mini App (Telegram Web App)

Mini App'ning eng muhim qismi — **`initData` ni tekshirish**. Uni brauzerda
istalgan odam o'zgartira oladi, shuning uchun server tomonda tekshirilmagan
`user` ga hech qachon ishonmang.

### 1. Tekshirish

```python
from zafather import validate, WebAppAuthError

try:
    init = validate(init_data_string, TOKEN, max_age=3600)
    print(init.user.id, init.user.full_name, init.start_param)
except WebAppAuthError as exc:
    print("Ishonchsiz:", exc)      # hash mos kelmadi / eskirgan / hash yo'q
```

- `validate()` — HMAC-SHA256, bot tokeni bilan (asosiy usul)
- `is_valid()` — `True/False` qaytaradi
- `validate_third_party(init_data, bot_id)` — **token'siz** tekshirish
  (Bot API 8.0+), Telegram'ning Ed25519 ochiq kaliti orqali. Ma'lumotni
  boshqa xizmatga berayotganda kerak. `pip install cryptography` talab qiladi.
- `parse_init_data()` — faqat o'qish, tekshirmasdan (debug uchun)

`max_age` (soniya) eskirgan ma'lumotni rad etadi — o'g'irlangan `initData` ni
qayta ishlatishdan himoya qiladi. Standart: 1 kun, tavsiya: 1 soat yoki kamroq.

### 2. Tayyor backend server

```python
server = bot.serve_mini_app(static_dir="webapp", port=8080)

@server.api("/me")
async def me(user, init):
    return {"id": user.id, "name": user.full_name}

@server.api("/notify")
async def notify(user, data, bot):
    await bot.send_message(chat_id=user.id, text=data["text"])
    return {"sent": True}

server.run()          # static fayllar + API + bot polling birga
```

Har bir `/api/...` so'rovi avtomatik tekshiriladi — `initData`
`X-Telegram-Init-Data` sarlavhasida (yoki `Authorization: tma <initData>`)
kelishi kerak. O'tmasa handler **umuman chaqirilmaydi**, 401 qaytadi.

Handler kerakli argumentlarni so'raydi: `user`, `init`, `data` (so'rov tanasi),
`bot`, `app`, `request`.

Webhook rejimi ham shu serverga ulanadi:

```python
server.add_webhook("/webhook", secret_token=os.getenv("SECRET"))
```

### 3. Frontend

`initData` har so'rovda sarlavhada yuboriladi:

```js
fetch("/api/me", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Telegram-Init-Data": Telegram.WebApp.initData
  },
  body: JSON.stringify({})
});
```

To'liq ishlaydigan namuna: `examples/miniapp/` (bot + backend + sahifa).

### 4. Bot tomonidagi metodlar

```python
await bot.mini_app.set_menu_button("🚀 Ochish", "https://example.com/app")
await bot.mini_app.answer_text(init.query_id, "Ilovadan yuborildi")   # answerWebAppQuery
await bot.mini_app.save_prepared_message(user_id, result)             # shareMessage uchun
await bot.mini_app.set_emoji_status(user_id, "5368324170671202286")
```

Ilovani ochadigan tugmalar va havolalar:

```python
InlineKeyboard().primary("Ochish", web_app="https://example.com/app")
ReplyKeyboard().app("Ochish", "https://example.com/app")   # bunda sendData() ishlaydi
direct_link("MyBot", "shop", "ref_42", mode="fullscreen")  # t.me/MyBot/shop?startapp=...
main_app_link("MyBot", "ref_42")                           # asosiy Mini App
```

Reply-keyboard ilovasi `sendData()` orqali yuborgan ma'lumot:

```python
@bot.message(WebAppData())
async def on_data(m, web_app_data):     # JSON bo'lsa avtomatik dict bo'ladi
    await m.answer(f"Qabul qilindi: {web_app_data}")
```

> Bu kanal **imzolanmagan** — muhim amallar uchun backend API'dan foydalaning.

### Eslatmalar

- Mini App URL'i **HTTPS** bo'lishi shart. Lokalda `ngrok http 8080` ishlatiladi.
- Bot API 10.2 dan (20-iyul, 2026) Mini App metodlari boshqa domenlardan
  chaqirilishi bloklandi. Ilovangizda ishonchsiz saytlarga havolalar bo'lmasin.

---

## Rich Messages (Bot API 10.1 / 10.3)

Oddiy xabarda sarlavha, jadval yoki yig'iladigan bo'lim yasab bo'lmaydi —
rich message aynan shuning uchun. AI botlar javobni oqim bilan yuborishi ham
shu orqali.

### Tuzilgan xabar

```python
from zafather import RichMessage, bold, emoji

rm = RichMessage()
rm.heading("Avgust hisoboti")
rm.paragraph(emoji("5368324170671202286", "🔥"), " Oy ", bold("rejadan oshiq"), " yakunlandi.")
rm.table([["Ko'rsatkich", "Reja", "Fakt"],
          ["Sotuv", "10 000", "12 400"]], header=True)
rm.checklist([("Hisobotni yuborish", True), ("Narxni ko'rish", False)])
rm.code("SELECT * FROM sales;", "sql")
rm.details("Hisoblash usuli", "Qaytarilgan buyurtmalar chiqarib tashlandi.")
rm.divider()

await m.answer_rich(rm)
```

Mavjud bloklar: `heading()`, `paragraph()`, `bullets()`, `numbered()`,
`checklist()`, `code()`, `table()`, `quote()`, `details()`, `divider()`,
`thinking()`, `math()`, `image()`.

Matn ichidagi formatlash `bold()`, `italic()`, `link()`, `emoji()` bilan
beriladi — ular ikki marta ekranlanmaydi, oddiy satrlar esa avtomatik
xavfsizlanadi.

### AI javobini oqim bilan yuborish

```python
from zafather import RichStream

async with RichStream(bot.bot, m.chat_id, min_interval=0.7) as stream:
    async for chunk in llm_stream():
        await stream.push(chunk)
# chiqishda yakuniy sendRichMessage avtomatik yuboriladi
```

`min_interval` — qoralamalar orasidagi eng kam vaqt (soniya). Har bir token
uchun so'rov yuborilsa flood-limitga tushasiz, shuning uchun oqim tejab
yuboradi. Qoralama yuborishdagi tarmoq xatosi oqimni to'xtatmaydi.

### Boshqa yo'llar

```python
# Markdown bilan
from zafather import markdown_rich
await bot.bot.send_rich(chat_id, markdown_rich("# Sarlavha\n\nMatn"))

# Bloklar bilan (10.2 usuli)
rm.block("paragraph", text="Blok obyekti sifatida")

# Hujjatdagi yangi teg uchun
rm.tag("tg-map", "Toshkent", latitude=41.3, longitude=69.2)
rm.raw("<p>Tayyor HTML</p>")
```

`RichMessage` HTML yasaydi — `InputRichMessage` ning `html` maydoni. Kamroq
uchraydigan bloklar (xarita, kollaj, matematik ifoda) uchun teg nomini
rasmiy hujjatdan tekshiring: matematik ifoda tegi
`RichMessage.MATH_TAG` orqali sozlanadi.

---

## Loyiha tuzilishi

```
zafather/
├── __init__.py      # eksportlar
├── enums.py         # ButtonStyle, UpdateType, ContentType ...
├── __main__.py      # CLI (python -m zafather new ...)
├── app.py           # Zafather: polling, dispatch, hooks
├── bot.py           # Telegram API klienti
├── router.py        # Router, handler, middleware
├── filters.py       # Command, Text, Regex, StateFilter ...
├── magic.py         # F sehrli filtri
├── fsm.py           # State, StatesGroup, FSMContext, storage
├── text.py          # premium emoji, HTML yorliqlari, TextBuilder
├── managed.py       # ManagedBots, BotFarm (bot yaratadigan bot)
├── rich.py          # Rich Messages: HTML quruvchi, oqim (stream)
├── webapp.py        # Mini App: initData tekshiruvi, havolalar, metodlar
├── webserver.py     # Mini App backend serveri (aiohttp)
├── types.py         # Message, User, Chat, CallbackQuery ...
└── keyboards.py     # InlineKeyboard, ReplyKeyboard ...
```

## Testlar

```bash
python test_zafather.py     # yadro: 34 ta test
python test_miniapp.py      # Mini App: 21 ta test
python test_rich.py         # Rich Messages: 23 ta test
```

## Hissa qo'shish

Loyiha **ochiq** — pull request va takliflar mamnuniyat bilan qabul qilinadi.

- Xatolik yoki taklif: [Issues](https://github.com/ismoilov299/zafather/issues) da yozing.
- Kod yubormoqchi bo'lsangiz:
  1. Repozitoriyni fork qiling, alohida branch oching.
  2. Har bir yangi imkoniyat uchun **test** yozing (`test_*.py` uslubida).
  3. `python -m compileall -q zafather` va uchala test fayli o'tishini tekshiring.
  4. Commit xabari: `feat:`, `fix:`, `docs:`, `test:`, `refactor:` + o'zbekcha tavsif.
  5. `main` ga pull request oching.
- Kod konvensiyalari va arxitektura qarorlari [CONTRIBUTING.md](CONTRIBUTING.md) da.

Savol yoki muhokama uchun: [regnad299@gmail.com](mailto:regnad299@gmail.com).

## Muallif

[**ismoilov299**](https://github.com/ismoilov299) — g'oya, arxitektura va asosiy kod.

## Loyihani qo'llab-quvvatlash

Zafather bepul va ochiq. Yoqqan bo'lsa:

<a href="https://www.buymeacoffee.com/ismoilov299" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png"
       alt="Buy Me A Coffee" height="48" width="174">
</a>

## Litsenziya

MIT — xohlagancha o'zgartiring va ishlating. © 2026 ismoilov299.
