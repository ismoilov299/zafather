# Правило тестов и документации

Любой feature, bugfix или изменение поведения требует:

1. Тест для нового или измененного поведения.
2. Полный проход существующих тестов.
3. Обновление документации на трех языках: `docs/uz/`, `docs/ru/`, `docs/en/`.
4. Public docstring, комментарии в коде и пояснения к примерам на трех языках.
5. Запись в `CHANGELOG.md`.

## Запуск проверок

```bash
pip install -e ".[dev]"
pytest -q                        # тесты (офлайн)
ruff check zafather tests examples
ruff format --check zafather tests examples
mypy                             # проверка типов пакета zafather
python -m build                  # необязательно: сборка sdist и wheel
```

CI запускает те же команды на Python 3.10–3.14.

## Как тесты остаются офлайн

Тесты никогда не обращаются к настоящим серверам Telegram.

- **Bot API**: `FakeSession` из `tests/support.py` — это `BaseSession`, которая
  записывает каждый запрос и возвращает ответы из очереди
  (`session.respond("getMe", {...})`, `session.fail("sendMessage", 400, "...")`).
  Передайте ее как `Zafather(TOKEN, session=FakeSession())` и проверяйте
  `session.last("sendMessage").params`.
- **MTProto**: `tests/mtproto/fake_server.py` — небольшой сервер Telegram,
  говорящий на настоящем MTProto 2.0 по TCP: обмен ключами, шифрование,
  контейнеры, соли, вход с кодом и 2FA, миграция DC, flood wait и update.
  Фикстура `server` запускает его на свободном локальном порту.
- **Примеры**: `tests/test_examples.py` и `tests/mtproto/test_userbot.py`
  запускают скрипты из `examples/`, поэтому документация не расходится с кодом.
