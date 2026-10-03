# Testing and Docs Rule

Every feature, bugfix, or behavior change requires:

1. A test for the new or changed behavior.
2. The full existing test suite passing.
3. Documentation updates in three languages: `docs/uz/`, `docs/ru/`, `docs/en/`.
4. Public docstrings, code comments, and example notes in three languages.
5. A `CHANGELOG.md` entry.

## Running the checks

```bash
pip install -e ".[dev]"
pytest -q                        # tests (offline)
ruff check zafather tests examples
ruff format --check zafather tests examples
mypy                             # type checking of the zafather package
python -m build                  # optional: build the sdist and wheel
```

CI runs the same commands on Python 3.10–3.14.

## How the tests stay offline

Tests never call the real Telegram servers.

- **Bot API**: `tests/support.py` provides `FakeSession`, a `BaseSession` that
  records every request and returns queued answers
  (`session.respond("getMe", {...})`, `session.fail("sendMessage", 400, "...")`).
  Pass it as `Zafather(TOKEN, session=FakeSession())` and assert on
  `session.last("sendMessage").params`.
- **MTProto**: `tests/mtproto/fake_server.py` is a small Telegram server that
  speaks real MTProto 2.0 over TCP: key exchange, encryption, containers, salts,
  sign-in with code and 2FA, DC migration, flood waits and updates. The `server`
  fixture starts it on a free local port.
- **Examples**: `tests/test_examples.py` and `tests/mtproto/test_userbot.py` run
  the scripts from `examples/`, so the documentation cannot drift from the code.
