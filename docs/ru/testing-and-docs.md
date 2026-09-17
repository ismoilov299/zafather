# Правило тестов и документации

Любой feature, bugfix или изменение поведения требует:

1. Тест для нового или измененного поведения.
2. Полный проход существующих тестов.
3. Обновление документации на трех языках: `docs/uz/`, `docs/ru/`, `docs/en/`.
4. Public docstring, комментарии в коде и пояснения к примерам на трех языках.
5. Запись в `CHANGELOG.md`.

Минимальная проверка:

```bash
python -m compileall -q zafather
python test_zafather.py
python test_miniapp.py
python test_rich.py
```

Тесты не должны обращаться к реальному Telegram. Методы bot-клиента заменяются
fake-функциями, а тест проверяет отправляемый payload.
