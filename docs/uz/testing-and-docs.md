# Test va docs qoidasi

Har qanday yangi feature, bugfix yoki behavior o'zgarishi quyidagilarni talab qiladi:

1. Yangi yoki o'zgargan behavior uchun test.
2. Mavjud testlarning to'liq o'tishi.
3. Hujjatlarning uch tilda yangilanishi: `docs/uz/`, `docs/ru/`, `docs/en/`.
4. Public docstring, kod commentlari va example izohlarining uch tilda bo'lishi.
5. `CHANGELOG.md` yozuvi.

Minimal tekshiruv:

```bash
python -m compileall -q zafather
python test_zafather.py
python test_miniapp.py
python test_rich.py
```

Telegram'ga ulanadigan real chaqiriqlar testda ishlatilmaydi. Bot klient metodlari
fake funksiya bilan almashtiriladi va yuboriladigan payload tekshiriladi.
