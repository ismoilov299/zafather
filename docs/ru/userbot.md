# Userbot (MTProto)

Bot API не может действовать от имени пользовательского аккаунта. Для этого
Zafather поставляет собственный клиент MTProto 2.0 (без Telethon и Pyrogram) и
фасад `UserBot` поверх него.

```bash
pip install "zafather[userbot]"
```

`api_id` и `api_hash` можно получить на <https://my.telegram.org>.

## Вход

```python
import asyncio

from zafather import UserBot

userbot = UserBot(12345, "API_HASH", session="my_account")

@userbot.on_message(pattern=r"^\.ping$", outgoing=True)
async def ping(event):
    await event.edit("pong")

asyncio.run(userbot.run())
```

При первом запуске `start()` запрашивает номер телефона, код входа и (если он
есть у аккаунта) пароль 2FA. Каждое значение можно передать строкой, функцией
или async-функцией:

```python
await userbot.start(
    phone="998901234567",
    code_callback=lambda: input("Код: "),
    password="2fa-пароль",
)
await userbot.start(bot_token="123456:ABC")    # бот-аккаунт через MTProto
```

Отдельные шаги тоже доступны: `client.send_code()`, `client.sign_in()`,
`client.check_password()`, `client.sign_in_bot()` и `client.log_out()`.

## Сессии

| Значение `session=` | Хранение |
|---|---|
| `"имя"` или путь | `FileSession`: `имя.session.json`, пишется атомарно с правами `0600` |
| `StringSession()` | строка, которую можно хранить в переменной окружения (`session.value`) |
| `None` или `MemorySession()` | только память, забывается при выходе |

Сессия дает полный доступ к аккаунту: никогда не добавляйте ее в репозиторий и
никому не передавайте. `MTProtoClient(..., test_mode=True)` подключается к
тестовым серверам Telegram; сессию одного окружения другое отклонит.

## События

```python
from zafather.mtproto import events

@userbot.on_message(pattern=r"^/start", incoming=True)   # events.NewMessage
async def start(event):
    await event.reply("Привет!")         # также: respond(), edit(), delete()

@userbot.on_edited()                                     # events.MessageEdited
@userbot.on_deleted()                                    # events.MessageDeleted: event.deleted_ids
@userbot.on_callback(data=b"yes")                        # events.CallbackQuery (бот-аккаунты)
@userbot.on(events.Raw(types=["updateUserStatus"]))      # любой сырой update
```

Фильтры `NewMessage`: `pattern` (regex, проверяемый с начала текста, строка или
функция; совпадение сохраняется в `event.pattern_match`), `incoming`/`outgoing`,
`from_users`, `forwards`, `chats` с `blacklist_chats` и `func`. Исключение
`events.StopPropagation` пропускает оставшиеся обработчики. Update, пришедшие в
результатах ваших собственных запросов, обновляют состояние, но не порождают
событий, поэтому обработчик не может запустить сам себя.

Пропущенные update догружаются автоматически: при обнаружении пропуска `pts`,
после переподключения и, с `start(catch_up=True)`, пропущенные в офлайне.

## Отправка сообщений и сырые запросы

```python
client = userbot.client                                    # MTProtoClient
await client.send_message("@username", "<b>Привет</b>", parse_mode="html")
await client.edit_message(chat_id, message_id, "изменено")
await client.delete_messages(chat_id, [message_id])
history = await client.get_messages("username", limit=10)
me = await client.get_me()
```

Любой TL-метод layer 229 доступен как сырой запрос:

```python
from zafather.mtproto import functions, types

config = await userbot.invoke(functions.help.getConfig())
await userbot.invoke(functions.account.updateStatus(offline=False))
peer = await client.get_input_entity("@username")
```

Объекты проверяются по схеме: при неверном имени или типе поля ошибка называет
это поле.

## Ошибки и надежность

- `FloodWaitError` короче `flood_sleep_threshold` (по умолчанию 60 секунд)
  пережидается автоматически; `UserBot` повторяет и более длинные до
  `max_retries` раз.
- При `PHONE_MIGRATE`, `USER_MIGRATE` и `NETWORK_MIGRATE` дата-центр меняется
  прозрачно.
- Потерянное соединение восстанавливается автоматически (`reconnect_retries`,
  `reconnect_delay`), а запросы без ответа переотправляются тем же сообщением,
  поэтому ничего не отправляется дважды. По той же причине
  `UserBot.send_message()` не повторяется после обрыва соединения.
- RPC-ошибки сопоставлены классам: `SessionPasswordNeededError`,
  `PhoneCodeInvalidError`, `PeerIdInvalidError` и другим; все они наследуют
  `RPCError` (`error_code`, `message`).

## Ограничения

Клиент покрывает вход, сообщения, update и сырые запросы. Загрузка и скачивание
файлов, секретные чаты и звонки пока не реализованы; для всего остального
доступны сырые TL-запросы (`invoke`).
