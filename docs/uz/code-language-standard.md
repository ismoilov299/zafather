# Kod tili standarti

Koddagi foydalanuvchiga va contributorlarga ko'rinadigan matnlar uch tilda
bo'lishi kerak.

## Qamrov

- Public class, function va module docstringlari.
- Kod ichidagi mazmunli commentlar.
- README, docs va docstring ichidagi example izohlari.
- CLI template yoki namuna botlarda foydalanuvchi ko'radigan tushuntirishlar.

## Tartib

Matnlar quyidagi tartibda yoziladi:

```python
"""UZ: O'zbekcha tushuntirish.
RU: Русское пояснение.
EN: English explanation.
"""
```

Qisqa ichki comment kerak bo'lsa:

```python
# UZ: Draft Telegram API uchun majburiy identifikator bilan yuboriladi.
# RU: Draft отправляется с обязательным идентификатором Telegram API.
# EN: The draft is sent with the identifier required by the Telegram API.
```

Comment kerak bo'lmasa, uni qo'shmang. Kodning o'zi tushunarli bo'lishi afzal.
