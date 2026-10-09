# Документация Zafather

Zafather — легкий async-фреймворк для Telegram-ботов (Bot API 10.3) и userbot
(MTProto 2.0, TL layer 229). Единственная обязательная зависимость — `aiohttp`;
`cryptography` опциональна (проверка Ed25519 для Mini App и userbot), `redis`
тоже опционален (`RedisStorage`).

## Разделы

- [Архитектура](architecture.md): слои, ответственность и точки расширения.
- [Userbot (MTProto)](userbot.md): вход, события, запросы и сессии.
- [Переход на 0.5](migration-0.5.md): что изменилось и как обновиться.
- [Совместимость с Bot API](api-compatibility.md)
- [Правило тестов и документации](testing-and-docs.md)
- [Языковой стандарт кода](code-language-standard.md)

## Быстрый старт

```bash
pip install zafather                 # боты
pip install "zafather[userbot]"      # + userbot (MTProto)
python -m zafather new my_bot        # шаблон проекта (--userbot для userbot)
```

```python
from zafather import F, Message, Zafather

app = Zafather("TOKEN")

@app.command("start")
async def start(message: Message):
    await message.answer(f"Привет, <b>{message.from_user.first_name}</b>!")

@app.message(F.text)
async def echo(message: Message):
    await message.answer(message.text)

app.run()
```

Рабочие примеры лежат в [`examples/`](../../examples); тесты запускают каждый из
них офлайн.

## Стандарт проекта

Любая новая возможность или изменение поведения должны сопровождаться тестом,
документацией на трех языках и записью в `CHANGELOG.md`.
