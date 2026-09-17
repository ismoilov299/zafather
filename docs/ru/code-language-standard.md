# Языковой стандарт кода

Тексты в коде, которые видят пользователи и contributor'ы, должны быть на трех
языках.

## Область применения

- Public docstring модулей, классов и функций.
- Содержательные комментарии внутри кода.
- Пояснения к примерам в README, docs и docstring.
- Пояснения в CLI template или примерных ботах, которые видит пользователь.

## Порядок

Тексты пишутся в таком порядке:

```python
"""UZ: O'zbekcha tushuntirish.
RU: Русское пояснение.
EN: English explanation.
"""
```

Короткий комментарий внутри кода:

```python
# UZ: Draft Telegram API uchun majburiy identifikator bilan yuboriladi.
# RU: Draft отправляется с обязательным идентификатором Telegram API.
# EN: The draft is sent with the identifier required by the Telegram API.
```

Если комментарий не нужен, не добавляйте его. Лучше писать код так, чтобы он
был понятен сам по себе.
