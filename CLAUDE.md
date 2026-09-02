# CLAUDE.md — Zafather loyihasi bo'yicha qo'llanma

Bu fayl Claude Code uchun. Loyihaga o'zgartirish kiritishdan oldin **to'liq o'qing**.

---

## 1. Loyiha nima

**Zafather** — Telegram botlar yozish uchun async framework. Noldan yozilgan,
aiogram'ga bog'liq emas (undan faqat g'oyalar olingan).

**Maqsad:** aiogram darajasidagi imkoniyat, lekin kodi kichik va o'qib
tushunarli bo'lsin. Foydalanuvchi framework ichiga kirib, nima bo'layotganini
30 daqiqada tushuna olsin.

**Mos keladigan Bot API versiyasi:** 10.2 (14-iyul, 2026).

**Bog'liqliklar:** faqat `aiohttp`. `cryptography` — ixtiyoriy (Mini App
uchinchi tomon tekshiruvi uchun). **Yangi majburiy bog'liqlik qo'shmang.**

---

## 2. Tez boshlash

```bash
pip install aiohttp cryptography
python test_zafather.py      # yadro: 34 ta test
python test_miniapp.py       # Mini App: 21 ta test
python test_rich.py          # Rich Messages: 23 ta test
python -m compileall -q zafather
```

Testlar Telegram'ga **ulanmaydi** — `app.bot.request` / `app.bot.call`
soxta funksiya bilan almashtiriladi.

---

## 3. Arxitektura

```
zafather/
├── __init__.py    # barcha eksportlar (89 ta nom) — yangi nom qo'shsangiz shu yerga ham
├── __main__.py    # CLI: python -m zafather new <loyiha>
├── enums.py       # ButtonStyle, UpdateType (26 ta), ContentType, BOT_API_VERSION
├── bot.py         # Bot: HTTP klient, retry, 429, InputFile, dinamik metodlar
├── types.py       # Message, User, Chat, CallbackQuery, Update + yorliq metodlar
├── router.py      # Router, Handler, middleware, argument injection
├── filters.py     # Command, Text, Regex, StateFilter, Service, Ephemeral...
├── magic.py       # F sehrli filtri
├── fsm.py         # State, StatesGroup, FSMContext, Memory/JSON storage
├── keyboards.py   # InlineKeyboard, ReplyKeyboard (rangli tugmalar bilan)
├── text.py        # premium emoji, HTML yorliqlari, SafeHTML, TextBuilder
├── rich.py        # RichMessage (HTML quruvchi), RichStream (oqim)
├── managed.py     # ManagedBots, BotFarm (bot yaratadigan botlar)
├── webapp.py      # Mini App: initData tekshiruvi (HMAC + Ed25519), havolalar
├── webserver.py   # MiniAppServer: static + himoyalangan API + webhook
└── app.py         # Zafather: polling, dispatch, hooks, spawn, farm
```

### Update qanday oqadi

```
getUpdates → Update(raw) → app.feed_update()
   ├── event_type aniqlanadi (message / callback_query / managed_bot ...)
   ├── data yig'iladi: bot, app, state, raw_state, chat_id, user_id, ...
   ├── router.trigger() → middleware zanjiri → _propagate()
   │      └── har bir Handler.check() → filtrlar → mos kelsa chaqiriladi
   └── xato bo'lsa → error handlerlar
```

Handler **faqat o'zi so'ragan argumentlarni** oladi — `router.call_handler()`
imzoni tekshirib kerakligini uzatadi. Yangi kontekst maydoni qo'shsangiz,
`app.feed_update()` dagi `data` lug'atiga qo'shing va README'dagi jadvalni
yangilang.

---

## 4. Muhim dizayn qarorlari — buzmang

| Qaror | Sabab |
|---|---|
| `Bot.__getattr__` snake_case → camelCase | Har qanday API metodi kod yozmasdan ishlaydi: `bot.send_dice(...)` |
| Filtr `dict` qaytarsa — handlerga argument bo'ladi | `Command` → `command`, `args`; `Regex` → `match` |
| `UNSET` sentinel (`router.py`) | `state=None` ("holatsiz") va "holat ko'rsatilmagan" farqlanishi kerak |
| `allowed_updates` standart = 26 turning hammasi | Aks holda Telegram `managed_bot`, `guest_message`, `subscription` yubormaydi |
| `SafeHTML` (`text.py`) | `bold()` chiqishi rich builder ichida ikki marta ekranlanmasligi uchun |
| `TelegramObject.__getattr__` yo'q maydonda `None` qaytaradi | Bot API tez o'zgaradi — yangi maydonlar kod o'zgarmasdan ishlaydi |
| Middleware imzosi: `async def mw(event, data, next_)` | `await next_(event, data)` chaqirilmasa handler ishlamaydi |
| Storage kaliti: `(chat_id, user_id)` | Guruhda har bir odam alohida FSM holatida bo'ladi |
| `RichStream.min_interval` | Har token uchun so'rov = flood limit |

---

## 5. Kod konvensiyalari

- **Izohlar va docstring'lar — o'zbekcha.** Kod nomlari — inglizcha.
- Type hint'lar majburiy (public API uchun).
- Xato xabarlari o'zbekcha va aniq: `"style faqat (...) dan biri bo'lishi mumkin, berildi: 'pushti'"`.
- Kutubxona kodida `print()` yo'q — faqat `logging.getLogger("zafather.<modul>")`.
- Har bir public sinf/funksiya docstring'ida qisqa foydalanish namunasi bo'lsin.
- Satr uzunligi ~100 belgi.
- Yangi modul qo'shsangiz: `__init__.py` ga eksport + `__all__` ga nom + README'da bo'lim.

### Bot API bilan ishlashda

**Maydon nomini o'ylab topmang.** Aniq bilmasangiz:
1. `https://core.telegram.org/bots/api` yoki `api-changelog` ni tekshiring.
2. Baribir noaniq bo'lsa — `**params` / `**kwargs` orqali o'tkazib yuboring va
   docstring'da "rasmiy hujjat bo'yicha beriladi" deb yozing.

Shu yondashuv allaqachon ishlatilgan joylar (**tekshirilishi kerak**):

| Joy | Nima noaniq |
|---|---|
| `rich.py` → `MATH_TAG`, `THINKING_TAG` | Matematik ifoda va thinking teglarining aniq nomi |
| `rich.py` → `image()`, `add_media()` | 10.2 `InputRichMessageMedia` bilan bog'lanish tartibi |
| `managed.py` → `token()`, `replace_token()` | `getManagedBotToken` parametr nomi (`bot_id` deb taxmin qilingan) |
| `text.py` → `TextBuilder.date_time()` | `date_time` entity qo'shimcha maydoni (`timestamp=`?) |
| `types.py` → `answer_ephemeral()` | `receiver_user_id` / `callback_query_id` nomlari |

Bularni tasdiqlagach: taxminni olib tashlang, testga aniq qiymat yozing va bu
jadvaldan qatorni o'chiring.

---

## 6. Testlar

Har bir yangi imkoniyat uchun test **majburiy**. Uslub:

```python
app = Zafather("123456:AA-TEST-TOKEN")
sent = []
async def fake(method, **kwargs):
    sent.append((method, kwargs))
    return {"ok": True}
app.bot.request = fake
app.bot.call = fake
# ... feed_update() yoki metodni chaqirib, sent[] ni tekshirasiz
```

- Tarmoqqa chiqmang (`test_miniapp.py` dagi lokal server bundan mustasno).
- Har bir tekshiruv `check(shart, "o'zbekcha tavsif")` orqali.
- Fayl oxirida `Natija: N ta test o'tdi` chiqishi kerak.
- Testlar soni kamayib ketmasin — README'dagi raqamlarni ham yangilang.

---

## 7. Hozirgi holat (v0.4.0)

| Bo'lim | Holat |
|---|---|
| Yadro (Bot, Router, filtrlar, FSM, klaviaturalar) | ✅ tayyor |
| Bot API 10.2: rangli tugmalar, premium emoji, ephemeral, reaksiyalar | ✅ tayyor |
| Managed bots (`ManagedBots`, `BotFarm`, `spawn`) | ✅ tayyor, parametr nomlari tekshirilmagan |
| Mini App (`validate`, `MiniAppServer`, namuna) | ✅ tayyor |
| Rich Messages (`RichMessage`, `RichStream`) | ✅ tayyor, ba'zi teglar tekshirilmagan |
| To'lovlar / Stars / sovg'alar | ❌ yo'q |
| `CallbackData` fabrikasi | ❌ yo'q |
| Throttling / anti-flood middleware | ❌ yo'q |
| Redis storage | ❌ yo'q |
| i18n (ko'p tillilik) | ❌ yo'q |
| Checklist, so'rovnoma 2.0, business akkaunt, suggested posts | ❌ yo'q |
| PyPI, CI, hujjat sayti | ❌ yo'q |

---

## 8. Keyingi vazifalar (tartib bo'yicha)

Har bir vazifa uchun **tugagan hisoblanadi** shartlari: kod + testlar +
README bo'limi + kerak bo'lsa `examples/` da namuna + `__init__.py` eksporti +
`CHANGELOG.md` ga qator + versiya ko'tarish.

### 8.1 `callback_data.py` — CallbackData fabrikasi (birinchi bo'lib qiling)

Muammo: `callback_data` 64 baytgacha, uni qo'lda `"user:42:delete"` qilib
yig'ish xatolarga olib keladi.

```python
class Action(CallbackData, prefix="act"):
    name: str
    item_id: int

kb.danger("O'chirish", Action(name="delete", item_id=42).pack())

@bot.callback(Action.filter(F.name == "delete"))
async def handler(c, callback_data: Action):
    ...
```

Talablar: `pack()` / `unpack()`, 64 bayt cheklovini tekshirish (oshsa aniq
xato), `int`/`str`/`bool`/`float`/`None` turlari, `filter()` metodi.

### 8.2 `middlewares.py` — throttling va yordamchilar

- `ThrottlingMiddleware(rate=0.5)` — bir foydalanuvchidan tez-tez kelgan
  update'larni tashlab yuboradi (kalit: `user_id`, ixtiyoriy `key_func`).
- `ChatActionMiddleware` — uzoq handlerlarda "yozmoqda…" ko'rsatadi.
- `AlbumMiddleware` — `media_group_id` bo'yicha rasm to'plamini bitta
  handlerga yig'ib beradi (0.5s kutish bilan).

### 8.3 `payments.py` — Stars, to'lovlar, sovg'alar

- `Invoice` quruvchi (`LabeledPrice`, `XTR` valyutasi).
- `bot.stars.balance()`, `transactions()`, `refund(user_id, charge_id)`.
- Sovg'alar: `available_gifts()`, `send_gift()`, `upgrade_gift()`, `transfer_gift()`.
- Obunalar: `create_subscription_link()`, `edit_user_star_subscription()`.
- `@bot.pre_checkout()` uchun avtomatik `answerPreCheckoutQuery(ok=True)`
  qiladigan yorliq — eng ko'p unutiladigan qadam.
- Namuna: `examples/stars_bot.py` — raqamli mahsulotni Stars'ga sotish.

### 8.4 `storage/redis.py` — Redis storage

`BaseStorage` ni meros qiling, `redis.asyncio` **ixtiyoriy** import bo'lsin
(yo'q bo'lsa tushunarli xato). TTL sozlamasi bo'lsin.

### 8.5 `i18n.py` — ko'p tillilik

`user.language_code` bo'yicha avtomatik til; `.ftl` yoki oddiy JSON lug'at;
middleware orqali handlerga `_` funksiyasi uzatiladi.

### 8.6 Qolgan Bot API imkoniyatlari

Checklist (`sendChecklist`), so'rovnomalar (9.6+ variant qo'shish/o'chirish),
business akkaunt metodlari, suggested posts, live photo, stories, forum
mavzulari, `sendMessageDraft`.

### 8.7 Nashr qilish

- `LICENSE` bor (MIT). `pyproject.toml` to'ldirilgan.
- GitHub Actions: `python -m compileall` + uchala test fayli, 3.9–3.13.
- PyPI: `python -m build && twine upload`.
- Hujjat: README yetarli, keyinroq mkdocs.

---

## 9. Git

- Commit xabarlari: `feat:`, `fix:`, `docs:`, `test:`, `refactor:` + o'zbekcha tavsif.
- Har bir imkoniyat alohida commit.
- Versiya `pyproject.toml` va `zafather/__init__.py` da bir vaqtda o'zgaradi.

```bash
git remote add origin https://github.com/<foydalanuvchi>/zafather.git
git push -u origin main
```

---

## 10. Nima qilmaslik kerak

- Yangi majburiy bog'liqlik qo'shmaslik (aiohttp'dan boshqa).
- Mavjud public API'ni sababsiz o'zgartirmaslik — `Zafather`, `Router`,
  `Message` metodlari barqaror bo'lishi kerak.
- Bot API maydon nomlarini taxmin qilib kodga qotirmaslik (5-bo'limga qarang).
- Kod hajmini keraksiz oshirmaslik: framework'ning asosiy qiymati — o'qish oson.
- Testsiz imkoniyat qo'shmaslik.
