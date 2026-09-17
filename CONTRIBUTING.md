# Zafather'ga hissa qo'shish

Loyiha ochiq — **pull request va takliflar mamnuniyat bilan qabul qilinadi.**

## Taklif yoki xatolik

[Issues](https://github.com/ismoilov299/zafather/issues) da yozing. Xatolik bo'lsa:
qanday takrorlash mumkinligini, kutilgan va haqiqiy natijani yozing.

## Majburiy qoida: test + docs

Har qanday yangi imkoniyat, bugfix yoki xatti-harakat o'zgarishi quyidagilar
bilan birga keladi:

- test: yangi yoki o'zgargan behavior oflayn test bilan yopiladi;
- docs: `docs/uz/`, `docs/ru/`, `docs/en/` ichida tegishli hujjat yangilanadi;
- code text: public docstring, kod ichidagi mazmunli comment va example izohlari
  uch tilda bo'ladi: o'zbekcha, ruscha, inglizcha;
- changelog: `CHANGELOG.md` ga foydalanuvchi ko'radigan o'zgarish yoziladi;
- regression: mavjud tekshiruvlar to'liq o'tadi.

Docs tarjimalarining ma'nosi bir xil bo'lishi kerak. Bir tilda yangi qoida yoki
feature yozilsa, qolgan ikki tilda ham o'sha mazmun aks etadi.

## Kod yuborish

1. Repozitoriyni fork qiling, `main` dan alohida branch oching
   (`feat/callback-data`, `fix/regex-caption` kabi).
2. **Har bir yangi imkoniyat uchun test majburiy** — `test_zafather.py`,
   `test_miniapp.py`, `test_rich.py` uslubida (Telegram'ga ulanmasdan,
   `app.bot.request` / `app.bot.call` soxta funksiya bilan almashtiriladi).
3. Docs'ni uch tilda yangilang: o'zbekcha, ruscha, inglizcha.
4. Tekshiring:
   ```bash
   python -m compileall -q zafather
   python test_zafather.py
   python test_miniapp.py
   python test_rich.py
   ```
   Testlar soni kamaymasin.
5. Yangi modul qo'shsangiz: `zafather/__init__.py` ga eksport + `__all__` ga
   nom + `README.md` da bo'lim + `CHANGELOG.md` ga qator + versiya ko'tarish
   (`pyproject.toml` va `zafather/__init__.py` bir vaqtda).
6. Commit xabari: `feat:`, `fix:`, `docs:`, `test:`, `refactor:` + o'zbekcha
   tavsif. Har bir imkoniyat alohida commit.
7. `main` ga pull request oching.

## Kod uslubi

- Public docstring, mazmunli comment va example izohlari — **uch tilda**:
  `UZ:`, `RU:`, `EN:` tartibida. Kod nomlari — inglizcha.
- Juda qisqa ichki comment kerak bo'lsa ham shu tartibga amal qiling; comment
  zarur bo'lmasa, kodni o'zi tushunarli qilib yozing.
- Public API uchun type hint majburiy.
- Kutubxona kodida `print()` yo'q — `logging.getLogger("zafather.<modul>")`.
- Satr uzunligi ~100 belgi.
- Yangi majburiy bog'liqlik qo'shilmaydi (`aiohttp` dan boshqa;
  `cryptography` — ixtiyoriy).
- Bot API maydon nomlarini taxmin qilib kodga qotirmang — noaniq bo'lsa
  `**params` orqali o'tkazing va docstring'da belgilang.
- `Bot.__getattr__` snake_case→camelCase, filtr `dict` qaytarsa handlerga
  argument bo'ladi, `UNSET` sentinel `state=None` dan farqlanadi — mavjud
  namunalarga qarab yozing.

## Muhokama

Savol yoki g'oya uchun: [regnad299@gmail.com](mailto:regnad299@gmail.com)
yoki Issues'da `question` yorlig'i bilan.
