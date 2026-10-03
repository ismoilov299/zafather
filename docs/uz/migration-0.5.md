# 0.5 ga o'tish

0.5.0 versiyasida kutubxona toza va almashtiriladigan qatlamlar asosida qayta
yozildi ([Arxitektura](architecture.md) ga qarang). Ko'p bot kodi o'zgarishsiz
ishlayveradi; bu sahifada o'zgargan joylar sanab o'tilgan.

## Talablar

- Python **3.10+** (3.9 endi qo'llab-quvvatlanmaydi).
- `requirements.txt` olib tashlandi: bog'liqliklar `pyproject.toml` da
  (ishlab chiqish uchun `pip install "zafather[dev]"`).

## Bot API

- Xatolar: har bir Bot API xatosi `TelegramAPIError` vorisi (`BadRequest`,
  `Unauthorized`, `Forbidden`, `NotFound`, `Conflict`, `RetryAfter`,
  `ServerError`, `MigrateToChat`). `TelegramError` taxallus sifatida qoldi,
  `method`, `code`, `description` va `parameters` nomlari o'zgarmadi.
- `parse_mode=None` endi shu chaqiriq uchun formatlashni haqiqatan o'chiradi,
  `entities=` bilan yuborilgan xabarga esa parse mode qo'shilmaydi.
- Javobi yo'qolgan yozuvchi so'rovlar avtomatik qayta yuborilmaydi
  (`RetryPolicy(retry_unsafe_methods=True)` eski xatti-harakatni qaytaradi).
- Managed bot update'larida bot `event.bot_id` orqali beriladi; `event.bot` doim
  update'ni qabul qilgan mijoz.

## FSM

- `StorageKey` endi dataclass: `StorageKey(bot_id, chat_id, user_id,
  thread_id=None)`. O'z storage'laringiz `(chat_id, user_id)` kortej o'rniga
  shuni qabul qilishi kerak; satr kalit uchun `key.to_string()` dan foydalaning.
- `JSONStorage` atomik yozadi va 0.4 formatidagi fayllarni ham o'qiydi: eski
  yozuv kaliti birinchi marta ishlatilganda ko'chiriladi.
- `RedisStorage` `zafather.fsm.storage` ga ko'chdi (`zafather` dan eksport
  qilinishi saqlangan). Eski `zafather.storage` yo'li ishlaydi, lekin
  `DeprecationWarning` beradi.
- `Zafather(fsm_strategy=...)` holat kimga tegishli ekanini tanlaydi:
  `FSMStrategy.USER_IN_CHAT` (standart), `CHAT`, `GLOBAL_USER`, `USER_IN_TOPIC`
  yoki `CHAT_TOPIC`.

## Userbot (MTProto)

0.4 dagi tajribaviy MTProto bo'laklari to'liq mijoz bilan almashtirildi:

| 0.4 | 0.5 |
|---|---|
| `MTProtoSession` | `zafather.mtproto.FileSession`, `StringSession`, `MemorySession` (eski JSON sessiya fayllari o'qiladi) |
| `AbridgedTransport`, `MTProtoTransportError` | `TcpTransport` + `AbridgedCodec`, `TransportError` |
| `TLRequest`, `TLReader`, `TLWriter` (yuqori daraja) | `zafather.mtproto.functions` / `types`; past darajadagi `TLReader`/`TLWriter` — `zafather.mtproto` da |
| `AuthHandshake`, `DHExchange`, `ResPQ`, `ServerDHParamsOk`, `DHGenOk` | ichki: avtorizatsiya kalitlari `connect()` da avtomatik yaratiladi |
| `AuthKey`, `RSAPublicKey` (yuqori daraja) | `zafather.mtproto.AuthKey`, `zafather.mtproto.RSAPublicKey` |
| `UserBot(..., transport=..., dc_host=..., dc_port=...)` | `UserBot(..., transport_factory=..., dc_overrides=...)` |
| `userbot.invoke(raw_bytes)` | `userbot.invoke(functions.<metod>(...))` |

`UserBot`, `MTProtoClient`, `Events` va `EventBuilder` hamon `zafather` dan
eksport qilinadi.

## Testlar

Test fayllari `tests/` ga ko'chdi va `pytest` bilan ishga tushadi
([Test va docs qoidasi](testing-and-docs.md) ga qarang).
