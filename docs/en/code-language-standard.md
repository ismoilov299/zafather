# Code Language Standard

Text in code that is visible to users and contributors must be available in
three languages.

## Scope

- Public module, class, and function docstrings.
- Meaningful comments inside the code.
- Example notes in README, docs, and docstrings.
- User-visible explanations in CLI templates or example bots.

## Order

Write text in this order:

```python
"""UZ: O'zbekcha tushuntirish.
RU: Русское пояснение.
EN: English explanation.
"""
```

For a short code comment:

```python
# UZ: Draft Telegram API uchun majburiy identifikator bilan yuboriladi.
# RU: Draft отправляется с обязательным идентификатором Telegram API.
# EN: The draft is sent with the identifier required by the Telegram API.
```

Do not add comments when they are unnecessary. Prefer code that explains itself.
