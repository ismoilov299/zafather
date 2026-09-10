# O'zgarishlar tarixi

Format: [Keep a Changelog](https://keepachangelog.com/), versiyalash: [SemVer](https://semver.org/).

## [0.4.1]
### Qo'shildi
- **PyPI nashri**: `pyproject.toml` to'ldirildi (classifiers, urls, authors),
  `py.typed` (PEP 561), `MANIFEST.in`.
- GitHub Actions: `ci.yml` (3.9–3.13 da testlar), `publish.yml` (tag qo'yilganda
  PyPI Trusted Publishing orqali avtomatik nashr).
- `CONTRIBUTING.md` — loyiha ochiq, PR va takliflar qabul qilinadi.
- README: muallif (**ismoilov299**), hissa qo'shish va muhokama bo'limlari,
  PyPI/Python/litsenziya badge'lari.
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
