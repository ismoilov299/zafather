"""UZ: Userbot eventlari: yangi/tahrirlangan/o'chirilgan xabarlar, callback va xom update.
RU: События userbot: новые/изменённые/удалённые сообщения, callback и сырые update.
EN: Userbot events: new/edited/deleted messages, callbacks and raw updates.

    @client.on(events.NewMessage(pattern=r"^\\.ping$", outgoing=True))
    async def ping(event: events.NewMessage.Event):
        await event.edit("pong")
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from .entities import CHANNEL, marked_id, peer_id
from .tl import TLObject

if TYPE_CHECKING:
    from .client import MTProtoClient

Pattern = str | re.Pattern[str] | Callable[[str], Any] | None


class StopPropagation(Exception):
    """UZ: Handler ichida ko'tarilsa, keyingi handlerlar chaqirilmaydi.
    RU: Если выброшено в обработчике, следующие обработчики не вызываются.
    EN: Raised inside a handler to stop the remaining handlers.
    """


def _compile(pattern: Pattern) -> Callable[[str], Any] | None:
    if pattern is None or callable(pattern):
        return pattern
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
    return compiled.match


class Event:
    """UZ: Barcha eventlarning asosi. RU: Основа всех событий. EN: The base of every event."""

    def __init__(self, client: MTProtoClient, update: TLObject) -> None:
        self.client = client
        self.original_update = update

    @property
    def chat_id(self) -> int | None:
        """UZ: Belgilangan chat ID (kanallar uchun -100...). RU: Помеченный ID чата
        (-100... для каналов). EN: The marked chat ID (-100... for channels).
        """
        return None


class EventBuilder(ABC):
    """UZ: Update'dan event yasaydi va filtrlarni qo'llaydi.
    RU: Создаёт событие из update и применяет фильтры.
    EN: Builds an event from an update and applies filters.

    UZ: `chats` — belgilangan ID'lar ro'yxati; `blacklist_chats=True` bo'lsa ular
    istisno qilinadi; `func(event)` — qo'shimcha shart.
    RU: `chats` — список помеченных ID; при `blacklist_chats=True` они исключаются;
    `func(event)` — дополнительное условие.
    EN: `chats` is a list of marked IDs; with `blacklist_chats=True` they are excluded;
    `func(event)` adds a custom condition.
    """

    def __init__(
        self,
        *,
        chats: Iterable[int] | None = None,
        blacklist_chats: bool = False,
        func: Callable[[Any], Any] | None = None,
    ) -> None:
        self.chats = frozenset(chats) if chats is not None else None
        self.blacklist_chats = blacklist_chats
        self.func = func

    @abstractmethod
    def build(self, update: TLObject, client: MTProtoClient) -> Event | None:
        """UZ: Mos update uchun event, aks holda `None`. RU: Событие для подходящего update
        или `None`. EN: An event for a matching update, otherwise `None`.
        """

    def filter(self, event: Event) -> bool:
        """UZ: `chats` va `func` shartlarini tekshiradi. RU: Проверяет условия `chats` и
        `func`. EN: Checks the `chats` and `func` conditions.
        """
        if self.chats is not None:
            inside = event.chat_id in self.chats
            if inside == self.blacklist_chats:
                return False
        return not (self.func is not None and not self.func(event))


class _MessageEvent(Event):
    """UZ: Xabarga oid event. RU: Событие, связанное с сообщением. EN: A message-based event."""

    def __init__(self, client: MTProtoClient, update: TLObject, message: TLObject) -> None:
        super().__init__(client, update)
        self.message = message
        self.pattern_match: Any = None

    @property
    def id(self) -> int:
        """UZ: Xabar ID si. RU: ID сообщения. EN: The message ID."""
        return int(self.message.id)

    @property
    def text(self) -> str:
        """UZ: Xabar matni (formatlashsiz). RU: Текст сообщения (без форматирования).
        EN: The message text (without formatting).
        """
        return str(self.message.values.get("message") or "")

    raw_text = text

    @property
    def out(self) -> bool:
        """UZ: Xabarni o'zingiz yuborganmisiz. RU: Отправлено ли сообщение вами.
        EN: Whether you sent the message.
        """
        return bool(self.message.values.get("out"))

    @property
    def chat_id(self) -> int:
        """UZ: Belgilangan chat ID. RU: Помеченный ID чата. EN: The marked chat ID."""
        return peer_id(self.message.peer_id)

    @property
    def sender_id(self) -> int | None:
        """UZ: Yuboruvchi ID si (kanal postlarida None bo'lishi mumkin). RU: ID отправителя
        (в постах каналов может быть None). EN: The sender ID (may be None for channel posts).
        """
        sender = self.message.values.get("from_id")
        if sender is not None:
            return peer_id(sender)
        if self.out:
            return self.client.self_id
        return self.chat_id if self.is_private else None

    @property
    def is_private(self) -> bool:
        """UZ: Shaxsiy chat. RU: Личный чат. EN: A private chat."""
        return self.message.peer_id.tl_name == "peerUser"

    @property
    def is_group(self) -> bool:
        """UZ: Oddiy guruh. RU: Обычная группа. EN: A basic group."""
        return self.message.peer_id.tl_name == "peerChat"

    @property
    def is_channel(self) -> bool:
        """UZ: Kanal yoki superguruh. RU: Канал или супергруппа. EN: A channel or supergroup."""
        return self.message.peer_id.tl_name == "peerChannel"

    async def respond(self, text: str, **kwargs: Any) -> TLObject:
        """UZ: Shu chatga yangi xabar. RU: Новое сообщение в этот чат. EN: A new message here."""
        return await self.client.send_message(self.chat_id, text, **kwargs)

    async def reply(self, text: str, **kwargs: Any) -> TLObject:
        """UZ: Shu xabarga javob. RU: Ответ на это сообщение. EN: A reply to this message."""
        return await self.client.send_message(self.chat_id, text, reply_to=self.id, **kwargs)

    async def edit(self, text: str, **kwargs: Any) -> TLObject:
        """UZ: Xabarni tahrirlaydi (faqat o'zingizniki). RU: Редактирует (только свои).
        EN: Edits the message (only your own messages).
        """
        return await self.client.edit_message(self.chat_id, self.id, text, **kwargs)

    async def delete(self, revoke: bool = True) -> Any:
        """UZ: Xabarni o'chiradi (`revoke` — hamma uchun). RU: Удаляет сообщение (`revoke` —
        для всех). EN: Deletes the message (`revoke` deletes it for everyone).
        """
        return await self.client.delete_messages(self.chat_id, [self.id], revoke=revoke)

    async def get_chat(self) -> TLObject:
        """UZ: Chat obyekti. RU: Объект чата. EN: The chat object."""
        return await self.client.get_entity(self.chat_id)

    async def get_sender(self) -> TLObject | None:
        """UZ: Yuboruvchi obyekti. RU: Объект отправителя. EN: The sender object."""
        sender = self.sender_id
        return None if sender is None else await self.client.get_entity(sender)

    def __repr__(self) -> str:
        return (
            f"<{type(self).__qualname__} chat={self.chat_id} id={self.id} text={self.text[:30]!r}>"
        )


class NewMessage(EventBuilder):
    """UZ: Yangi xabar. `pattern` — regex (matnning boshidan), satr yoki funksiya;
    `incoming`/`outgoing` — yo'nalish; `from_users` — yuboruvchilar.
    RU: Новое сообщение. `pattern` — regex (с начала текста), строка или функция;
    `incoming`/`outgoing` — направление; `from_users` — отправители.
    EN: A new message. `pattern` is a regex (matched from the start), string or callable;
    `incoming`/`outgoing` set the direction; `from_users` limits senders.
    """

    UPDATES: frozenset[str] = frozenset({"updateNewMessage", "updateNewChannelMessage"})

    class Event(_MessageEvent):
        pass

    def __init__(
        self,
        pattern: Pattern = None,
        *,
        incoming: bool | None = None,
        outgoing: bool | None = None,
        from_users: Iterable[int] | None = None,
        forwards: bool | None = None,
        chats: Iterable[int] | None = None,
        blacklist_chats: bool = False,
        func: Callable[[Any], Any] | None = None,
    ) -> None:
        super().__init__(chats=chats, blacklist_chats=blacklist_chats, func=func)
        if incoming and outgoing:
            incoming = outgoing = None
        elif incoming is False:
            outgoing, incoming = True, None
        elif outgoing is False:
            incoming, outgoing = True, None
        self.incoming = incoming
        self.outgoing = outgoing
        self.from_users = frozenset(from_users) if from_users is not None else None
        self.forwards = forwards
        self.pattern = _compile(pattern)

    def _event_class(self) -> type[_MessageEvent]:
        return self.Event

    def build(self, update: TLObject, client: MTProtoClient) -> _MessageEvent | None:
        if update.tl_name not in self.UPDATES:
            return None
        message = update.values.get("message")
        if not isinstance(message, TLObject) or message.tl_name != "message":
            return None
        event = self._event_class()(client, update, message)
        if (self.incoming and event.out) or (self.outgoing and not event.out):
            return None
        if self.forwards is not None and bool(message.values.get("fwd_from")) != self.forwards:
            return None
        if self.from_users is not None and event.sender_id not in self.from_users:
            return None
        if self.pattern is not None:
            match = self.pattern(event.text)
            if not match:
                return None
            event.pattern_match = match
        return event


class MessageEdited(NewMessage):
    """UZ: Xabar tahrirlandi. RU: Сообщение отредактировано. EN: A message was edited."""

    UPDATES = frozenset({"updateEditMessage", "updateEditChannelMessage"})

    class Event(_MessageEvent):
        pass


class MessageDeleted(EventBuilder):
    """UZ: Xabarlar o'chirildi (shaxsiy chat va guruhlarda `chat_id` noma'lum).
    RU: Сообщения удалены (в личных чатах и группах `chat_id` неизвестен).
    EN: Messages were deleted (`chat_id` is unknown for private chats and groups).
    """

    class Event(Event):
        """UZ: `deleted_ids` — o'chirilgan xabarlar ID'lari. RU: `deleted_ids` — ID удалённых
        сообщений. EN: `deleted_ids` holds the deleted message IDs.
        """

        def __init__(self, client: MTProtoClient, update: TLObject) -> None:
            super().__init__(client, update)
            self.deleted_ids: list[int] = list(update.messages)
            channel = update.values.get("channel_id")
            self._chat_id = marked_id(CHANNEL, channel) if channel else None

        @property
        def chat_id(self) -> int | None:
            return self._chat_id

    def build(self, update: TLObject, client: MTProtoClient) -> Event | None:
        if update.tl_name in ("updateDeleteMessages", "updateDeleteChannelMessages"):
            return self.Event(client, update)
        return None


class CallbackQuery(EventBuilder):
    """UZ: Inline tugma bosildi (bot akkauntlari uchun). `data` — baytlar yoki regex.
    RU: Нажата inline-кнопка (для бот-аккаунтов). `data` — байты или regex.
    EN: An inline button was pressed (bot accounts). `data` is bytes or a regex.
    """

    class Event(Event):
        """UZ: `data` — tugma ma'lumoti, `data_match` — regex natijasi.
        RU: `data` — данные кнопки, `data_match` — результат regex.
        EN: `data` is the button payload and `data_match` the regex match.
        """

        def __init__(self, client: MTProtoClient, update: TLObject) -> None:
            super().__init__(client, update)
            self.query = update
            self.data: bytes = update.values.get("data") or b""
            self.data_match: Any = None

        @property
        def chat_id(self) -> int | None:
            peer = self.query.values.get("peer")
            return peer_id(peer) if peer is not None else None

        @property
        def sender_id(self) -> int:
            """UZ: Tugmani bosgan foydalanuvchi. RU: Нажавший пользователь. EN: Who pressed it."""
            return int(self.query.user_id)

        @property
        def message_id(self) -> int | None:
            """UZ: Tugmali xabar ID si. RU: ID сообщения с кнопкой. EN: The button's message ID."""
            return self.query.values.get("msg_id")

        async def answer(
            self,
            message: str | None = None,
            *,
            alert: bool = False,
            url: str | None = None,
            cache_time: int = 0,
        ) -> Any:
            """UZ: Bosishga javob (bildirishnoma yoki `alert=True` bilan oyna).
            RU: Ответ на нажатие (уведомление или окно при `alert=True`).
            EN: Answers the press (a toast, or a dialog with `alert=True`).
            """
            from .tl import functions

            return await self.client.invoke(
                functions.messages.setBotCallbackAnswer(
                    query_id=self.query.query_id,
                    message=message,
                    alert=alert,
                    url=url,
                    cache_time=cache_time,
                )
            )

        async def respond(self, text: str, **kwargs: Any) -> TLObject:
            """UZ: Shu chatga yangi xabar. RU: Новое сообщение в этот чат.
            EN: Sends a new message to the same chat.
            """
            if self.chat_id is None:
                raise ValueError("This callback query has no chat")
            return await self.client.send_message(self.chat_id, text, **kwargs)

        async def edit(self, text: str, **kwargs: Any) -> TLObject:
            """UZ: Tugmali xabarni tahrirlaydi. RU: Редактирует сообщение с кнопкой.
            EN: Edits the message that carries the button.
            """
            if self.chat_id is None or self.message_id is None:
                raise ValueError("Inline-message callbacks cannot be edited here")
            return await self.client.edit_message(self.chat_id, self.message_id, text, **kwargs)

    def __init__(
        self,
        data: bytes | str | re.Pattern[bytes] | None = None,
        *,
        chats: Iterable[int] | None = None,
        blacklist_chats: bool = False,
        func: Callable[[Any], Any] | None = None,
    ) -> None:
        super().__init__(chats=chats, blacklist_chats=blacklist_chats, func=func)
        if isinstance(data, str):
            data = re.compile(data.encode())
        self.data = data

    def build(self, update: TLObject, client: MTProtoClient) -> Event | None:
        if update.tl_name != "updateBotCallbackQuery":
            return None
        event = self.Event(client, update)
        if isinstance(self.data, bytes):
            if event.data != self.data:
                return None
        elif self.data is not None:
            match = self.data.match(event.data)
            if not match:
                return None
            event.data_match = match
        return event


class Raw(EventBuilder):
    """UZ: Istalgan xom update (`types` — TL nomlari bilan cheklash).
    RU: Любой сырой update (`types` — ограничение по именам TL).
    EN: Any raw update (`types` limits it by TL names).
    """

    class Event(Event):
        @property
        def update(self) -> TLObject:
            return self.original_update

    def __init__(
        self, types: Iterable[str] | None = None, *, func: Callable[[Any], Any] | None = None
    ) -> None:
        super().__init__(func=func)
        self.types = frozenset(types) if types is not None else None

    def build(self, update: TLObject, client: MTProtoClient) -> Event | None:
        if self.types is not None and update.tl_name not in self.types:
            return None
        return self.Event(client, update)


class Events:
    """UZ: Eski uslubdagi nom fazosi: `Events.NewMessage(...)`. RU: Пространство имён в старом
    стиле: `Events.NewMessage(...)`. EN: A legacy-style namespace: `Events.NewMessage(...)`.
    """

    NewMessage = NewMessage
    MessageEdited = MessageEdited
    MessageDeleted = MessageDeleted
    CallbackQuery = CallbackQuery
    Raw = Raw


__all__ = [
    "CallbackQuery",
    "Event",
    "EventBuilder",
    "Events",
    "MessageDeleted",
    "MessageEdited",
    "NewMessage",
    "Raw",
    "StopPropagation",
]
