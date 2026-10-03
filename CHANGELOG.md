# O'zgarishlar tarixi

Format: [Keep a Changelog](https://keepachangelog.com/), versiyalash: [SemVer](https://semver.org/).

## [Unreleased]

## [0.5.0]
Kutubxona toza arxitektura va SOLID tamoyillari asosida to'liq qayta yozildi.
O'tish qo'llanmasi: [docs/uz/migration-0.5.md](docs/uz/migration-0.5.md)
([RU](docs/ru/migration-0.5.md), [EN](docs/en/migration-0.5.md)).

### Qo'shildi
- `api/` qatlami: `BaseSession` / `AiohttpSession`, `PayloadBuilder`, `RetryPolicy`,
  `TelegramAPIServer` (o'z Bot API serveringiz ham); `Bot(session=..., retry=...)`.
- `TelegramAPIError` ierarxiyasi: `BadRequest`, `Unauthorized`, `Forbidden`,
  `NotFound`, `Conflict`, `RetryAfter`, `ServerError`, `MigrateToChat`.
- `Dispatcher`, `LongPolling`, `WebhookServer`, `Zafather.run_webhook()`, fayl
  yuklab olish (`Bot.download()`), parallel ishlov chegarasi
  (`max_concurrent_updates`), inner middleware, filtrli xato handlerlari
  (`ExceptionTypeFilter`).
- FSM: `FSMStrategy` (`USER_IN_CHAT`, `CHAT`, `GLOBAL_USER`, `USER_IN_TOPIC`,
  `CHAT_TOPIC`), forum mavzulari uchun `StorageKey.thread_id`.
- `zafather.mtproto` — to'liq MTProto 2.0 mijozi: TL layer 229 sxemasi ishlash
  vaqtida o'qiladi (`functions.*`, `types.*` maydon tekshiruvi bilan),
  avtorizatsiya kaliti almashuvi, AES-IGE, kod / 2FA (SRP) / bot token bilan kirish,
  DC migratsiyasi, FLOOD_WAIT, konteynerlar, salt va vaqt sinxronizatsiyasi,
  uzilishda qayta ulanish va so'rovlarni qayta yuborish.
- Update'lar: `pts` bo'shliqlarini aniqlash, `getDifference`, qayta ulangandan
  keyin o'tkazib yuborilgan update'larni olish; eventlar: `NewMessage`,
  `MessageEdited`, `MessageDeleted`, `CallbackQuery`, `Raw`, `StopPropagation`.
- Entity keshi (access hash, username), HTML -> `MessageEntity` (UTF-16),
  `FileSession` (0600, atomik), `StringSession`, `MemorySession`.
- `UserBot`: `on_edited()`, `on_deleted()`, Telethon/Pyrogram FLOOD_WAIT
  xatolarini tanish, TL obyektlari bilan `invoke()`.
- CLI: `python -m zafather new NOM --userbot`, `python -m zafather version`.
- `examples/userbot.py`; barcha namunalar testlarda oflayn ishga tushiriladi.
- Hujjatlar: arxitektura, userbot va 0.5 ga o'tish bo'limlari (uz/ru/en).
- `I18n` middleware: `language_code` asosida locale tanlash va tarjimalar.
- Optional `RedisStorage`, Stars payments, `CallbackData` va middleware yordamchilari.
- `RichStream` draftlari uchun `draft_id`, `can_stop`, `keep_on_stop`;
  Bot API 10.3 dagi `stopped_message_generation` update turi va router helperi.
- Uch tilli hujjatlar tuzilmasi (`docs/uz/`, `docs/ru/`, `docs/en/`) va public
  docstring, kod commentlari hamda example izohlari uchun uch tilli standart.

### O'zgardi
- Minimal Python versiyasi 3.10; bog'liqliklar `pyproject.toml` da
  (`requirements.txt` o'rniga, ishlab chiqish uchun `[dev]` extra).
- `StorageKey` — `bot_id`, `chat_id`, `user_id`, `thread_id` maydonli dataclass;
  `JSONStorage` atomik yozadi va 0.4 formatidagi fayllarni o'qiydi.
- `RedisStorage` `zafather.fsm.storage` ga ko'chdi; `zafather.storage` eskirgan
  (`DeprecationWarning`).
- Javobi yo'qolgan yozuvchi so'rovlar standart holatda takrorlanmaydi
  (`RetryPolicy(retry_unsafe_methods=...)`).
- `parse_mode=None` formatlashni aniq o'chiradi; `entities=` bilan parse mode
  yuborilmaydi.
- Handler imzosi bir marta tahlil qilinadi; filtrlar oldindan kompilyatsiya qilinadi.
- `answer_ephemeral()` Bot API 10.3 dagi `ephemeral_message_parameters`
  formatini yuboradi; `BOT_API_VERSION` 10.3 ga yangilandi.
- Loyiha qoidasi rasmiylashtirildi: har bir feature yoki behavior o'zgarishi test,
  uch tilli docs va changelog bilan keladi.

### Olib tashlandi
- 0.4 dagi tajribaviy MTProto bo'laklari: `TLRequest`, `MTProtoSession`,
  `AbridgedTransport`, `MTProtoTransportError`, `AuthHandshake`, `DHExchange`,
  `ResPQ`, `ServerDHParamsOk`, `DHGenOk` (o'rnini `zafather.mtproto` egalladi).
  `AuthKey`, `RSAPublicKey`, `TLReader`, `TLWriter` endi `zafather.mtproto` dan
  import qilinadi.
- `test_zafather.py`, `test_miniapp.py`, `test_rich.py` — testlar `tests/` ga ko'chdi.

### Tuzatildi
- `TelegramObject` ning `bot` maydoni bilan to'qnashuvi (`ManagedBotUpdated.bot_id`).
- `getUpdates` timeouti to'g'ri hisoblanadi; `stop()` polling boshlanishidan oldin
  chaqirilsa ham ishlaydi.
- Webhook maxfiy tokeni vaqt bo'yicha xavfsiz solishtiriladi.
- `CallbackData`: prefiks tekshiruvi va 64 bayt chegarasi; Stars metodlari.

### Testlar
- pytest'ga o'tildi: oflayn testlar (Bot API — `FakeSession`, MTProto — haqiqiy
  protokolda gaplashadigan lokal soxta Telegram serveri); ruff va mypy CI'da,
  Python 3.10–3.14.

## [0.4.2]
### Qo'shildi
- `UserBot` — mustaqil MTProto client, retry/reconnect va event registry.

## [0.4.1]
### Qo'shildi
- **PyPI nashri**: `pyproject.toml` to'ldirildi (classifiers, urls, authors),
  `py.typed` (PEP 561), `MANIFEST.in`.
- GitHub Actions: `ci.yml` (3.9–3.13 da testlar), `publish.yml` (tag qo'yilganda
  PyPI Trusted Publishing orqali avtomatik nashr).
- `CONTRIBUTING.md` — loyiha ochiq, PR va takliflar qabul qilinadi.
- README: muallif (**ismoilov299**), hissa qo'shish va muhokama bo'limlari,
  PyPI/Python/litsenziya badge'lari, "Buy Me A Coffee" qo'llab-quvvatlash.
- `.github/FUNDING.yml` — GitHub Sponsor tugmasi.

### O'zgardi
- Lokal ishlab chiqish fayllari git kuzatuvidan chiqarildi;
  hissa qo'shish qo'llanmasi to'liq `CONTRIBUTING.md` da.
- `__author__`, `__license__` `zafather/__init__.py` da.

## [0.4.0]
### Qo'shildi
- **Rich Messages** (Bot API 10.1/10.2): `RichMessage` HTML quruvchisi
  (sarlavha, ro'yxat, checklist, jadval, kod, yig'iladigan bo'lim, thinking),
  `RichStream` — AI javobini oqim bilan yuborish (`sendRichMessageDraft`).
- `Message.answer_rich()`, `Message.edit_rich()`, `Bot.send_rich()`, `Bot.stream_rich()`.
- `markdown_rich()` — markdown orqali rich message.
- `SafeHTML` — ikki marta ekranlashning oldini oladi.

## [0.3.0]
### Qo'shildi
- **Mini App**: `validate()` (HMAC-SHA256), `validate_third_party()` (Ed25519),
  `parse_init_data()`, `direct_link()`, `main_app_link()`, `attach_link()`.
- `MiniAppServer` — static fayllar + avtomatik tekshiriladigan JSON API + webhook.
- `MiniApp` — menyu tugmasi, `answerWebAppQuery`, tayyor xabar/tugmalar, emoji status.
- `WebAppData` filtri; `examples/miniapp/` to'liq namunasi.

## [0.2.0]
### Qo'shildi
- Bot API 10.2 darajasi: 26 ta update turi, `allowed_updates` avtomatik to'liq.
- **Rangli tugmalar** (9.4+): `.primary()`, `.success()`, `.danger()`, `icon=`.
- **Premium emoji**: `emoji()`, `TextBuilder` (entity orqali, `date_time` bilan).
- **Managed bots** (9.6+): `ManagedBots`, `BotFarm`, `Zafather.spawn()`.
- Ephemeral xabarlar, reaksiyalar (`m.react()`), guest mode, obunalar.
- Yangi dekoratorlar: `@bot.managed_bot`, `@bot.guest`, `@bot.subscription`,
  `@bot.reaction`, `@bot.business_message`, `@bot.boost`, `@bot.service`.
- Yangi filtrlar: `Service`, `Ephemeral`, `Premium`, `HasCustomEmoji`.

## [0.1.0]
### Qo'shildi
- Yadro: `Zafather` (polling, dispatch, hooks, webhook), `Bot` (dinamik API
  metodlari, retry, 429, fayl yuklash), `Router` (middleware, sub-router).
- Filtrlar: `Command`, `Text`, `Regex`, `ChatType`, `ContentType`, `UserFilter`.
- `F` sehrli filtri, FSM (`StatesGroup`, `FSMContext`, Memory/JSON storage).
- Klaviaturalar, CLI (`python -m zafather new`), 3 ta namuna.
