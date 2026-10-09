"""UZ: Zafather — userbot namunasi (MTProto, shaxsiy akkaunt nomidan).
RU: Zafather — пример userbot (MTProto, от имени личного аккаунта).
EN: Zafather — userbot example (MTProto, acting as your personal account).

UZ: Ishga tushirish / RU: Запуск / EN: Run:

    pip install "zafather[userbot]"
    export API_ID=12345 API_HASH=...      # https://my.telegram.org
    python userbot.py

UZ: Birinchi ishga tushishda telefon raqam, kod va (bo'lsa) 2FA parol so'raladi.
Sessiya `my_account.session.json` fayliga saqlanadi — uni hech kimga bermang.
RU: При первом запуске запрашиваются номер телефона, код и (если есть) пароль 2FA.
Сессия сохраняется в `my_account.session.json` — никому её не передавайте.
EN: On the first run you are asked for the phone number, the code and (if set) the
2FA password. The session is saved to `my_account.session.json` — never share it.

UZ: Buyruqlar (o'zingiz yozgan xabarlarda):
RU: Команды (в ваших собственных сообщениях):
EN: Commands (in messages you send yourself):

    .ping         pong + kechikish / задержка / latency
    .id           chat va xabar ID / ID чата и сообщения / chat and message IDs
    .history 5    oxirgi xabarlar / последние сообщения / the latest messages
"""

import asyncio
import logging
import os
import time

from zafather import UserBot
from zafather.mtproto import events, functions

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("userbot")

userbot = UserBot(
    int(os.environ["API_ID"]),
    os.environ["API_HASH"],
    session=os.getenv("SESSION", "my_account"),
)


@userbot.on_message(pattern=r"^\.ping$", outgoing=True)
async def ping(event: events.NewMessage.Event) -> None:
    """UZ: Server bilan aloqa tezligi. RU: Скорость связи с сервером.
    EN: The round-trip time to the server.
    """
    started = time.perf_counter()
    await userbot.invoke(functions.updates.getState())
    await event.edit(f"pong — {(time.perf_counter() - started) * 1000:.0f} ms")


@userbot.on_message(pattern=r"^\.id$", outgoing=True)
async def show_ids(event: events.NewMessage.Event) -> None:
    await event.edit(
        f"chat_id: <code>{event.chat_id}</code>\nmessage_id: <code>{event.id}</code>",
        parse_mode="html",
    )


@userbot.on_message(pattern=r"^\.history (\d+)$", outgoing=True)
async def history(event: events.NewMessage.Event) -> None:
    # UZ: Ko'pi bilan 20 ta xabar. RU: Не больше 20 сообщений. EN: At most 20 messages.
    limit = min(int(event.pattern_match.group(1)), 20)
    messages = await userbot.client.get_messages(event.chat_id, limit=limit)
    lines = [f"{message.id}: {message.message[:40]}" for message in messages if message.message]
    await event.reply("\n".join(lines) or "—")


@userbot.on_message(incoming=True, func=lambda event: event.is_private)
async def auto_reply(event: events.NewMessage.Event) -> None:
    """UZ: Shaxsiy chatda "salom" ga avtomatik javob. RU: Автоответ на "salom" в личке.
    EN: Auto-replies to "salom" in private chats.
    """
    if "salom" in event.text.lower():
        await event.reply("Va alaykum assalom! (avto-javob / автоответ / auto-reply)")


@userbot.on_edited(outgoing=True)
async def edited(event: events.MessageEdited.Event) -> None:
    log.info("Tahrirlandi / Изменено / Edited: %s", event.id)


@userbot.on_deleted()
async def deleted(event: events.MessageDeleted.Event) -> None:
    log.info("O'chirildi / Удалено / Deleted: %s", event.deleted_ids)


async def main() -> None:
    # UZ: Telefon -> kod -> (2FA) so'raladi. RU: Запрашиваются телефон -> код -> (2FA).
    # EN: Prompts for the phone -> code -> (2FA).
    await userbot.start()
    me = await userbot.client.get_me()
    log.info("Kirildi / Вход выполнен / Logged in: %s", me.first_name)
    await userbot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
