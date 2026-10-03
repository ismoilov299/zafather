# Arxitektura

Zafather kichik qatlamlarga bo'lingan. Har bir qatlamning bitta vazifasi bor va
u quyi qatlamning abstraksiyalariga tayanadi, shuning uchun istalgan qismni
almashtirish yoki alohida testlash mumkin.

## Bot API tomoni

```text
Zafather (app.py)               fasad: router + dispatcher + polling/webhook + hayot sikli
 ├─ Router (router.py)          handlerlar, filtrlar, middleware'lar, ichki routerlar
 ├─ Dispatcher (dispatcher.py)  bitta update konteksti, FSM, xato handlerlari
 ├─ LongPolling / WebhookServer update'larni qabul qilish
 └─ Bot (bot.py)                Bot API metodlari
     └─ api/                    BaseSession, PayloadBuilder, RetryPolicy, TelegramAPIServer
```

| Modul | Mas'uliyati |
|---|---|
| `api/session.py` | `BaseSession` interfeysi va standart `AiohttpSession` (faqat HTTP) |
| `api/request.py` | `PayloadBuilder`: Python qiymatlarini forma maydonlari va fayllarga aylantiradi |
| `api/retry.py` | `RetryPolicy`: tarmoq xatolari, `retry_after`, 5xx javoblar |
| `api/server.py` | `TelegramAPIServer`: Bot API manzillari, o'z serveringiz ham |
| `bot.py` | `Bot`: tiplangan yordamchilar va istalgan metod `bot.method_name(...)` ko'rinishida |
| `exceptions.py` | `TelegramAPIError` ierarxiyasi (`BadRequest`, `Forbidden`, `RetryAfter`, ...) |
| `types/` | `TelegramObject` o'ramlari (`Message`, `CallbackQuery`, ...) va qisqa metodlar |
| `handler.py` | `CallableSpec`: handler imzosi bir marta tahlil qilinadi, argumentlar nomi bo'yicha uzatiladi |
| `filters.py`, `magic.py` | `Filter` sinflari va `F` sehrli filtri |
| `router.py` | handlerlarni ro'yxatga olish, tashqi va ichki middleware'lar, ichki routerlar |
| `dispatcher.py` | har bir update konteksti, FSM konteksti, xato handlerlari |
| `polling.py`, `webhook.py` | update manbalari: muloyim `stop()` va parallel ishlov chegarasi |
| `fsm/` | `State`, `StatesGroup`, `FSMContext`, kalit strategiyalari va storage'lar |

Javobi yo'qolgan yozuvchi so'rovlar (masalan, `sendMessage`) standart holatda
takrorlanmaydi (`RetryPolicy(retry_unsafe_methods=False)`), shuning uchun tarmoq
uzilishi xabarni ikki marta yubora olmaydi. Faqat o'qiydigan `get*` metodlari
qayta uriniladi.

### SOLID amalda

- **Yagona mas'uliyat**: HTTP, so'rov yasash, qayta urinish va server manzillari
  alohida sinflarda; `Bot` ularni faqat birlashtiradi.
- **Ochiq/yopiq**: yangi filtr, middleware, storage, sessiya va FSM strategiyalari
  meros orqali qo'shiladi; yadro o'zgarmaydi.
- **Liskov almashtirishi**: har qanday `BaseStorage` va `BaseSession` amalga
  oshirilishi o'zaro almashinadi; testlar `Bot` ga tegmasdan `FakeSession` qo'yadi.
- **Interfeyslarni ajratish**: bitta katta asos sinf o'rniga kichik interfeyslar
  (`BaseSession`: `request`, `stream`, `close`; `BaseStorage`: holat va ma'lumot).
- **Bog'liqlik inversiyasi**: `Bot(token, session=...)` va
  `Zafather(token, storage=..., session=..., retry=...)` abstraksiyalarni qabul qiladi.

## MTProto tomoni (userbotlar)

```text
UserBot (userbot.py)                   fasad: FLOOD_WAIT, qayta ulanish, handler yordamchilari
 └─ MTProtoClient (mtproto/client.py)  kirish, xabarlar, entity'lar, eventlar
     ├─ UpdateProcessor (updates.py)   pts/qts kuzatuvi, bo'shliqlar, getDifference
     ├─ EntityCache (entities.py)      access hash'lar va username'lar
     └─ MTProtoSender (sender.py)      shifrlangan sessiya, ack, konteynerlar, qayta ulanish
         ├─ AuthKeyGenerator (auth.py) Diffie-Hellman kalit almashuvi
         ├─ MTProtoState (state.py)    msg_id, seq_no, salt, AES-IGE qadoqlash
         ├─ Transport (transport/)     Abridged yoki Intermediate ramkali TCP
         └─ TL (tl/)                   sxema parseri va serializer (layer 229)
```

| Modul | Mas'uliyati |
|---|---|
| `tl/` | paket ichidagi `.tl` sxemani ishlash vaqtida o'qiydi; `functions` va `types` tekshirilgan obyektlar yasaydi |
| `crypto/` | AES-IGE, RSA (barmoq izlari, RSA_PAD), DH tekshiruvlari, 2FA uchun SRP |
| `transport/` | `Transport` interfeysi, `TcpTransport`, `AbridgedCodec`, `IntermediateCodec` |
| `session/` | `SessionStorage` interfeysi: `MemorySession`, `FileSession` (0600, atomik), `StringSession` |
| `dc.py` | data-markazlar jadvali, `help.getConfig` dan yangilanadi |
| `errors.py` | `RPCError` ierarxiyasi (`FloodWaitError`, `PhoneMigrateError`, ...) |
| `parse.py` | HTML dan UTF-16 ofsetli `MessageEntity` larga |
| `events.py` | `NewMessage`, `MessageEdited`, `MessageDeleted`, `CallbackQuery`, `Raw` |

## Kengaytirish nuqtalari

| Ehtiyoj | Nima qilinadi |
|---|---|
| Boshqa HTTP mijoz | `BaseSession` dan meros olib, `session=` ga bering |
| Boshqacha qayta urinish | `RetryPolicy(...)` va `retry=` |
| Doimiy FSM | `BaseStorage` dan meros oling (`RedisStorage` ga qarang) |
| O'z filtringiz | `Filter` dan meros oling yoki istalgan funksiyani bering |
| Middleware | `BaseMiddleware` yoki `(event, data, next_)` funksiyasi |
| Userbot sessiyasi saqlanishi | `SessionStorage` dan meros oling |
| Proksi yoki boshqa transport | `Transport` qaytaradigan `MTProtoClient(transport_factory=...)` |
