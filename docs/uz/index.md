# Zafather hujjatlari

Zafather — Telegram botlar (Bot API 10.3) va userbotlar (MTProto 2.0, TL layer
229) uchun yengil async framework. Majburiy bog'liqlik faqat `aiohttp`;
`cryptography` ixtiyoriy (Mini App Ed25519 tekshiruvi va userbotlar uchun),
`redis` ham ixtiyoriy (`RedisStorage`).

## Bo'limlar

- [Arxitektura](architecture.md): qatlamlar, mas'uliyatlar va kengaytirish nuqtalari.
- [Userbot (MTProto)](userbot.md): kirish, eventlar, so'rovlar va sessiyalar.
- [0.5 ga o'tish](migration-0.5.md): nima o'zgardi va qanday yangilash kerak.
- [Bot API mosligi](api-compatibility.md)
- [Test va docs qoidasi](testing-and-docs.md)
- [Kod tili standarti](code-language-standard.md)

## Tez boshlash

```bash
pip install zafather                 # botlar
pip install "zafather[userbot]"      # + userbotlar (MTProto)
python -m zafather new mening_botim  # loyiha shabloni (userbot uchun --userbot)
```

```python
from zafather import F, Message, Zafather

app = Zafather("TOKEN")

@app.command("start")
async def start(message: Message):
    await message.answer(f"Salom, <b>{message.from_user.first_name}</b>!")

@app.message(F.text)
async def echo(message: Message):
    await message.answer(message.text)

app.run()
```

Ishlaydigan namunalar [`examples/`](../../examples) papkasida; testlar ularning
har birini oflayn ishga tushiradi.

## Loyiha standarti

Har bir yangi imkoniyat yoki xatti-harakat o'zgarishi test, uch tilli hujjat va
`CHANGELOG.md` yozuvi bilan birga keladi.
