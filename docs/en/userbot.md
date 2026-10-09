# Userbot (MTProto)

The Bot API cannot act as a user account. For that, Zafather ships its own
MTProto 2.0 client (no Telethon or Pyrogram) and the `UserBot` facade on top of it.

```bash
pip install "zafather[userbot]"
```

Get `api_id` and `api_hash` at <https://my.telegram.org>.

## Signing in

```python
import asyncio

from zafather import UserBot

userbot = UserBot(12345, "API_HASH", session="my_account")

@userbot.on_message(pattern=r"^\.ping$", outgoing=True)
async def ping(event):
    await event.edit("pong")

asyncio.run(userbot.run())
```

On the first run `start()` asks for the phone number, the login code and, if
the account has one, the 2FA password. Each prompt can also be passed in as a
string, a function or an async function:

```python
await userbot.start(
    phone="998901234567",
    code_callback=lambda: input("Code: "),
    password="2fa-password",
)
await userbot.start(bot_token="123456:ABC")    # a bot account over MTProto
```

The individual steps are available too: `client.send_code()`,
`client.sign_in()`, `client.check_password()`, `client.sign_in_bot()` and
`client.log_out()`.

## Sessions

| Value of `session=` | Storage |
|---|---|
| `"name"` or a path | `FileSession`: `name.session.json`, written atomically with `0600` permissions |
| `StringSession()` | a string to keep in an environment variable (`session.value`) |
| `None` or `MemorySession()` | memory only, forgotten on exit |

A session grants full access to the account: never commit or share it.
`MTProtoClient(..., test_mode=True)` connects to Telegram's test servers; a
session from one environment is rejected by the other.

## Events

```python
from zafather.mtproto import events

@userbot.on_message(pattern=r"^/start", incoming=True)   # events.NewMessage
async def start(event):
    await event.reply("Hello!")          # also: respond(), edit(), delete()

@userbot.on_edited()                                     # events.MessageEdited
@userbot.on_deleted()                                    # events.MessageDeleted: event.deleted_ids
@userbot.on_callback(data=b"yes")                        # events.CallbackQuery (bot accounts)
@userbot.on(events.Raw(types=["updateUserStatus"]))      # any raw update
```

`NewMessage` filters: `pattern` (a regex matched from the start of the text, a
string or a callable; the match is stored in `event.pattern_match`),
`incoming`/`outgoing`, `from_users`, `forwards`, `chats` with
`blacklist_chats`, and `func`. Raising `events.StopPropagation` skips the
remaining handlers. Updates that arrive inside the results of your own requests
update the state but do not fire events, so a handler cannot trigger itself.

Missed updates are fetched automatically: when a `pts` gap is detected, after a
reconnect, and, with `start(catch_up=True)`, those missed while offline.

## Sending messages and raw requests

```python
client = userbot.client                                    # MTProtoClient
await client.send_message("@username", "<b>Hi</b>", parse_mode="html")
await client.edit_message(chat_id, message_id, "edited")
await client.delete_messages(chat_id, [message_id])
history = await client.get_messages("username", limit=10)
me = await client.get_me()
```

Every TL method of layer 229 is available as a raw request:

```python
from zafather.mtproto import functions, types

config = await userbot.invoke(functions.help.getConfig())
await userbot.invoke(functions.account.updateStatus(offline=False))
peer = await client.get_input_entity("@username")
```

Objects are validated against the schema: a wrong field name or type raises an
error that names the field.

## Errors and reliability

- A `FloodWaitError` shorter than `flood_sleep_threshold` (60 s by default) is
  slept through automatically; `UserBot` also retries longer ones up to
  `max_retries` times.
- `PHONE_MIGRATE`, `USER_MIGRATE` and `NETWORK_MIGRATE` switch the data center
  transparently.
- A lost connection is restored automatically (`reconnect_retries`,
  `reconnect_delay`) and pending requests are resent as the same message, so
  nothing is sent twice. For the same reason `UserBot.send_message()` is never
  repeated after a dropped connection.
- RPC errors map to classes such as `SessionPasswordNeededError`,
  `PhoneCodeInvalidError` and `PeerIdInvalidError`; all of them inherit
  `RPCError` (`error_code`, `message`).

## Limitations

The client covers authorization, messaging, updates and raw requests. File
uploads and downloads, secret chats and calls are not implemented yet; raw TL
requests (`invoke`) stay available for everything else.
