# Zafather Documentation

Zafather is a lightweight async framework for Telegram bots (Bot API 10.3) and
userbots (MTProto 2.0, TL layer 229). The only required dependency is
`aiohttp`; `cryptography` is optional (Mini App Ed25519 checks and userbots),
and `redis` is optional too (`RedisStorage`).

## Sections

- [Architecture](architecture.md): layers, responsibilities and extension points.
- [Userbot (MTProto)](userbot.md): signing in, events, requests and sessions.
- [Migrating to 0.5](migration-0.5.md): what changed and how to update.
- [Bot API compatibility](api-compatibility.md)
- [Testing and docs rule](testing-and-docs.md)
- [Code language standard](code-language-standard.md)

## Quick start

```bash
pip install zafather                 # bots
pip install "zafather[userbot]"      # + userbots (MTProto)
python -m zafather new my_bot        # a project template (--userbot for a userbot)
```

```python
from zafather import F, Message, Zafather

app = Zafather("TOKEN")

@app.command("start")
async def start(message: Message):
    await message.answer(f"Hello, <b>{message.from_user.first_name}</b>!")

@app.message(F.text)
async def echo(message: Message):
    await message.answer(message.text)

app.run()
```

Runnable examples live in [`examples/`](../../examples); the test suite runs
every one of them offline.

## Project Standard

Every new feature or behavior change must ship with tests, documentation in
three languages, and a `CHANGELOG.md` entry.
