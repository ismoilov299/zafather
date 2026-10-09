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
2. **Har bir yangi imkoniyat uchun test majburiy** — `tests/` ichida, pytest
   uslubida va Telegram'ga ulanmasdan: Bot API uchun `tests/support.py` dagi
   `FakeSession`, MTProto uchun `tests/mtproto/fake_server.py` dagi soxta server
   (`server` fixture).
3. Docs'ni uch tilda yangilang: o'zbekcha, ruscha, inglizcha.
4. Tekshiring:
   ```bash
   pip install -e ".[dev]"
   pytest -q
   ruff check zafather tests examples
   ruff format --check zafather tests examples
   mypy
   ```
   Testlar soni kamaymasin.
5. Yangi modul qo'shsangiz: `zafather/__init__.py` ga eksport + `__all__` ga
   nom + `README.md` da bo'lim + `CHANGELOG.md` ga qator + versiya ko'tarish
   (versiya faqat `zafather/__init__.py` dagi `__version__` da; `pyproject.toml`
   uni avtomatik o'qiydi).
6. Commit xabari: `feat:`, `fix:`, `docs:`, `test:`, `refactor:` + o'zbekcha
   tavsif. Har bir imkoniyat alohida commit.
7. `main` ga pull request oching.

## Kod uslubi

- Public docstring, mazmunli comment va example izohlari — **uch tilda**:
  `UZ:`, `RU:`, `EN:` tartibida. Kod nomlari — inglizcha.
- Juda qisqa ichki comment kerak bo'lsa ham shu tartibga amal qiling; comment
  zarur bo'lmasa, kodni o'zi tushunarli qilib yozing.
- Public API uchun type hint majburiy (`mypy` xatosiz o'tadi).
- SOLID: yangi imkoniyat mavjud interfeyslar orqali qo'shiladi (`BaseSession`,
  `BaseStorage`, `Filter`, `BaseMiddleware`, `SessionStorage`, `Transport`);
  yadroni o'zgartirishdan oldin kengaytirish nuqtasini qidiring
  ([docs/uz/architecture.md](docs/uz/architecture.md)).
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
