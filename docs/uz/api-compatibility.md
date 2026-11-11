# Bot API mosligi

Zafather qo'llab-quvvatlanayotgan Telegram Bot API darajasini `BOT_API_VERSION`
orqali, MTProto sxema layer'ini esa `zafather.mtproto.schema_layer()` orqali
e'lon qiladi.

| Zafather | Bot API | MTProto layer | Holat |
|---|---:|---:|---|
| 0.6.0 | 10.4 | 229 | Joriy |
| 0.5.0 | 10.3 | 229 | Oldingi |
| 0.4.2 | 10.2 | tajribaviy | Nashr qilingan |
| 0.4.1 | 10.2 | — | Nashr qilingan |

## 10.4 widgetlari

Widget metodlari, modellari, routing va tekshiruvlar [Widgetlar](widgets.md) da.
Production'da shaxsiy chat; guruh, inline va forward test serverida ishlaydi.
Boshqa yangi 10.4 metodlari dinamik Bot API proksi orqali chaqiriladi.

## 10.3 uchun qoidalar

- Ephemeral xabarlar `ephemeral_message_parameters` orqali yuboriladi.
- Rich draft oqimlarida `draft_id` doim yuboriladi.
- `stopped_message_generation` update turi router orqali qabul qilinadi.

## Hali o'ralmagan metodlar

Zafather yordamchi metod qo'shishidan oldin ham har bir Bot API metodini
chaqirish mumkin: `await bot.bot.any_method_name(chat_id=..., ...)` `snake_case`
nomni `camelCase` metod nomiga aylantiradi va argumentlarni serializatsiya
qiladi. Rasmiy hujjatda aniq nomi belgilanmagan maydonlar kodga qotirilmaydi,
`**params` orqali uzatiladi.

## MTProto sxemasini yangilash

TL sxema paket bilan birga keladi (`zafather/mtproto/tl/data/api.tl`) va ishlash
vaqtida o'qiladi, shuning uchun kod generatsiyasi kerak emas. Yangi layer'ga
o'tish uchun shu faylni rasmiy sxema bilan almashtiring (`// LAYER N` qatorini
saqlang), `tests/mtproto/test_tl.py` dagi kutilgan layer raqamini yangilang va
testlarni ishga tushiring; ular har bir konstruktor ID si e'lonining CRC32 iga
mosligini ham tekshiradi.
