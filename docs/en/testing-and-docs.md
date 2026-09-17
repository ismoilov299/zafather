# Testing and Docs Rule

Every feature, bugfix, or behavior change requires:

1. A test for the new or changed behavior.
2. The full existing test suite passing.
3. Documentation updates in three languages: `docs/uz/`, `docs/ru/`, `docs/en/`.
4. Public docstrings, code comments, and example notes in three languages.
5. A `CHANGELOG.md` entry.

Minimum verification:

```bash
python -m compileall -q zafather
python test_zafather.py
python test_miniapp.py
python test_rich.py
```

Tests must not call the real Telegram API. Replace bot client methods with fake
functions and assert the outgoing payload.
