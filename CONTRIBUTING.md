# Zafather'ga hissa qo'shish

Loyiha ochiq — **pull request va takliflar mamnuniyat bilan qabul qilinadi.**

## Taklif yoki xatolik

[Issues](https://github.com/ismoilov299/zafather/issues) da yozing. Xatolik bo'lsa:
qanday takrorlash mumkinligini, kutilgan va haqiqiy natijani yozing.

## Kod yuborish

1. Repozitoriyni fork qiling, `main` dan alohida branch oching
   (`feat/callback-data`, `fix/regex-caption` kabi).
2. **Har bir yangi imkoniyat uchun test majburiy** — `test_zafather.py`,
   `test_miniapp.py`, `test_rich.py` uslubida (Telegram'ga ulanmasdan,
   `app.bot.request` / `app.bot.call` soxta funksiya bilan almashtiriladi).
3. Tekshiring:
   ```bash
   python -m compileall -q zafather
   python test_zafather.py
   python test_miniapp.py
   python test_rich.py
   ```
   Testlar soni kamaymasin.
4. Yangi modul qo'shsangiz: `zafather/__init__.py` ga eksport + `__all__` ga
   nom + `README.md` da bo'lim + `CHANGELOG.md` ga qator + versiya ko'tarish
   (`pyproject.toml` va `zafather/__init__.py` bir vaqtda).
5. Commit xabari: `feat:`, `fix:`, `docs:`, `test:`, `refactor:` + o'zbekcha
   tavsif. Har bir imkoniyat alohida commit.
6. `main` ga pull request oching.

## Kod uslubi

- Izohlar va docstring'lar — **o'zbekcha**, kod nomlari — inglizcha.
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
