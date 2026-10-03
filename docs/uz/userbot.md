# Userbot (MTProto)

Bot API foydalanuvchi akkaunti nomidan ishlay olmaydi. Buning uchun Zafather o'z
MTProto 2.0 mijozini (Telethon yoki Pyrogram'siz) va uning ustidagi `UserBot`
fasadini beradi.

```bash
pip install "zafather[userbot]"
```

`api_id` va `api_hash` ni <https://my.telegram.org> saytidan oling.

## Kirish

```python
import asyncio

from zafather import UserBot

userbot = UserBot(12345, "API_HASH", session="my_account")

@userbot.on_message(pattern=r"^\.ping$", outgoing=True)
async def ping(event):
    await event.edit("pong")

asyncio.run(userbot.run())
```

Birinchi ishga tushishda `start()` telefon raqam, kirish kodi va (akkauntda
bo'lsa) 2FA parolini so'raydi. Har birini satr, funksiya yoki async funksiya
sifatida ham berish mumkin:

```python
await userbot.start(
    phone="998901234567",
    code_callback=lambda: input("Kod: "),
    password="2fa-parol",
)
await userbot.start(bot_token="123456:ABC")    # MTProto orqali bot akkaunti
```

Alohida qadamlar ham mavjud: `client.send_code()`, `client.sign_in()`,
`client.check_password()`, `client.sign_in_bot()` va `client.log_out()`.

## Sessiyalar

| `session=` qiymati | Saqlanishi |
|---|---|
| `"nom"` yoki yo'l | `FileSession`: `nom.session.json`, atomik va `0600` ruxsati bilan yoziladi |
| `StringSession()` | muhit o'zgaruvchisida saqlanadigan satr (`session.value`) |
| `None` yoki `MemorySession()` | faqat xotirada, chiqishda unutiladi |

Sessiya akkauntga to'liq kirish huquqini beradi: uni hech qachon repozitoriyga
qo'shmang va hech kimga bermang. `MTProtoClient(..., test_mode=True)` Telegram
test serverlariga ulanadi; bir muhit sessiyasini ikkinchisi rad etadi.

## Eventlar

```python
from zafather.mtproto import events

@userbot.on_message(pattern=r"^/start", incoming=True)   # events.NewMessage
async def start(event):
    await event.reply("Salom!")          # yana: respond(), edit(), delete()

@userbot.on_edited()                                     # events.MessageEdited
@userbot.on_deleted()                                    # events.MessageDeleted: event.deleted_ids
@userbot.on_callback(data=b"yes")                        # events.CallbackQuery (bot akkauntlari)
@userbot.on(events.Raw(types=["updateUserStatus"]))      # istalgan xom update
```

`NewMessage` filtrlari: `pattern` (matn boshidan tekshiriladigan regex, satr
yoki funksiya; moslik `event.pattern_match` da), `incoming`/`outgoing`,
`from_users`, `forwards`, `chats` va `blacklist_chats`, `func`.
`events.StopPropagation` ko'tarilsa qolgan handlerlar chaqirilmaydi. O'z
so'rovlaringiz natijasida kelgan update'lar holatni yangilaydi, lekin event
chiqarmaydi, shuning uchun handler o'zini o'zi qo'zg'atmaydi.

O'tkazib yuborilgan update'lar avtomatik olinadi: `pts` bo'shlig'i topilganda,
qayta ulangandan keyin va `start(catch_up=True)` bilan oflayn paytdagilari ham.

## Xabar yuborish va xom so'rovlar

```python
client = userbot.client                                    # MTProtoClient
await client.send_message("@username", "<b>Salom</b>", parse_mode="html")
await client.edit_message(chat_id, message_id, "tahrirlandi")
await client.delete_messages(chat_id, [message_id])
history = await client.get_messages("username", limit=10)
me = await client.get_me()
```

Layer 229 dagi har bir TL metod xom so'rov sifatida mavjud:

```python
from zafather.mtproto import functions, types

config = await userbot.invoke(functions.help.getConfig())
await userbot.invoke(functions.account.updateStatus(offline=False))
peer = await client.get_input_entity("@username")
```

Obyektlar sxema bo'yicha tekshiriladi: maydon nomi yoki tipi noto'g'ri bo'lsa,
xato o'sha maydonni nomlaydi.

## Xatolar va ishonchlilik

- `flood_sleep_threshold` (standart 60 soniya) dan qisqa `FloodWaitError` da
  avtomatik kutiladi; `UserBot` uzunroqlarini ham `max_retries` martagacha
  qayta urinadi.
- `PHONE_MIGRATE`, `USER_MIGRATE` va `NETWORK_MIGRATE` da data-markaz sezdirmasdan
  almashtiriladi.
- Uzilgan ulanish avtomatik tiklanadi (`reconnect_retries`, `reconnect_delay`) va
  javobsiz so'rovlar o'sha xabar sifatida qayta yuboriladi, shuning uchun hech
  narsa ikki marta yuborilmaydi. Shu sababli `UserBot.send_message()` ulanish
  uzilganidan keyin takrorlanmaydi.
- RPC xatolari sinflarga mos keladi: `SessionPasswordNeededError`,
  `PhoneCodeInvalidError`, `PeerIdInvalidError` va boshqalar; hammasi `RPCError`
  (`error_code`, `message`) dan meros oladi.

## Cheklovlar

Mijoz kirish, xabarlar, update'lar va xom so'rovlarni qamraydi. Fayl yuklash va
yuklab olish, maxfiy chatlar va qo'ng'iroqlar hozircha amalga oshirilmagan;
qolgan hamma narsa uchun xom TL so'rovlari (`invoke`) mavjud.
