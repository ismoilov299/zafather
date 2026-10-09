# Test va docs qoidasi

Har qanday yangi feature, bugfix yoki behavior o'zgarishi quyidagilarni talab qiladi:

1. Yangi yoki o'zgargan behavior uchun test.
2. Mavjud testlarning to'liq o'tishi.
3. Hujjatlarning uch tilda yangilanishi: `docs/uz/`, `docs/ru/`, `docs/en/`.
4. Public docstring, kod commentlari va example izohlarining uch tilda bo'lishi.
5. `CHANGELOG.md` yozuvi.

## Tekshiruvlarni ishga tushirish

```bash
pip install -e ".[dev]"
pytest -q                        # testlar (oflayn)
ruff check zafather tests examples
ruff format --check zafather tests examples
mypy                             # zafather paketining tip tekshiruvi
python -m build                  # ixtiyoriy: sdist va wheel yig'ish
```

CI xuddi shu buyruqlarni Python 3.10–3.14 da ishga tushiradi.

## Testlar qanday oflayn qoladi

Testlar haqiqiy Telegram serverlariga hech qachon murojaat qilmaydi.

- **Bot API**: `tests/support.py` dagi `FakeSession` — har bir so'rovni yozib
  oladigan va navbatdagi javoblarni qaytaradigan `BaseSession`
  (`session.respond("getMe", {...})`, `session.fail("sendMessage", 400, "...")`).
  Uni `Zafather(TOKEN, session=FakeSession())` ga bering va
  `session.last("sendMessage").params` ni tekshiring.
- **MTProto**: `tests/mtproto/fake_server.py` — TCP orqali haqiqiy MTProto 2.0
  da gaplashadigan kichik Telegram serveri: kalit almashuvi, shifrlash,
  konteynerlar, salt'lar, kod va 2FA bilan kirish, DC migratsiyasi, flood wait
  va update'lar. `server` fixture uni bo'sh lokal portda ishga tushiradi.
- **Namunalar**: `tests/test_examples.py` va `tests/mtproto/test_userbot.py`
  `examples/` dagi skriptlarni ishga tushiradi, shuning uchun hujjat koddan
  ajralib qolmaydi.
