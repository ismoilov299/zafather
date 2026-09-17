"""UZ: Zafather — Telegram API obyektlari (Bot API 10.3).
RU: Zafather — объекты Telegram API (Bot API 10.3).
EN: Zafather — Telegram API objects (Bot API 10.3).
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .enums import UpdateType


class TelegramObject:
    """Telegram'dan kelgan har qanday JSON obyektining ustidagi yengil qobiq.

    Har qanday maydonga atribut orqali murojaat qilish mumkin:
        message.text, message.chat.id, message.from_user.first_name
    Mavjud bo'lmagan maydon `None` qaytaradi (KeyError emas).
    """

    __fields__: Dict[str, type] = {}

    def __init__(self, data: Optional[dict] = None, bot: Any = None) -> None:
        self._data: dict = data or {}
        self._bot = bot

    # --- asosiy xatti-harakat -------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        data = self.__dict__.get("_data") or {}
        if name not in data:
            return None
        value = data[name]
        cls = type(self).__fields__.get(name)
        if cls is None:
            return value
        if isinstance(value, list):
            return [cls(v, self._bot) if isinstance(v, dict) else v for v in value]
        if isinstance(value, dict):
            return cls(value, self._bot)
        return value

    @property
    def bot(self):
        return self._bot

    @property
    def raw(self) -> dict:
        """Xom (raw) JSON dict."""
        return self._data

    def get(self, name: str, default: Any = None) -> Any:
        return self._data.get(name, default)

    def to_dict(self) -> dict:
        return self._data

    def __contains__(self, item: str) -> bool:
        return item in self._data

    def __repr__(self) -> str:
        body = json.dumps(self._data, ensure_ascii=False)
        if len(body) > 240:
            body = body[:240] + "…"
        return f"{type(self).__name__}({body})"


class User(TelegramObject):
    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p)

    @property
    def mention(self) -> str:
        return f'<a href="tg://user?id={self.id}">{self.full_name}</a>'


class Chat(TelegramObject):
    @property
    def full_name(self) -> str:
        if self.title:
            return self.title
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p)


class PhotoSize(TelegramObject):
    pass


class Document(TelegramObject):
    pass


class Video(TelegramObject):
    pass


class Audio(TelegramObject):
    pass


class Voice(TelegramObject):
    pass


class Contact(TelegramObject):
    pass


class Location(TelegramObject):
    pass


class MessageEntity(TelegramObject):
    pass


class Message(TelegramObject):
    """Xabar + qulay yorliqlar (answer / reply / edit / delete)."""

    @property
    def chat_id(self) -> Optional[int]:
        return self.chat.id if self.chat else None

    @property
    def user_id(self) -> Optional[int]:
        return self.from_user.id if self.from_user else None

    @property
    def content(self) -> Optional[str]:
        """text yoki caption."""
        return self.text or self.caption

    # --- yorliqlar ------------------------------------------------------------
    async def answer(self, text: str, **kwargs) -> "Message":
        return await self._bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

    async def reply(self, text: str, **kwargs) -> "Message":
        kwargs.setdefault("reply_to_message_id", self.message_id)
        return await self._bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

    async def answer_photo(self, photo, caption: str = None, **kwargs) -> "Message":
        return await self._bot.send_photo(
            chat_id=self.chat_id, photo=photo, caption=caption, **kwargs
        )

    async def answer_document(self, document, caption: str = None, **kwargs) -> "Message":
        return await self._bot.send_document(
            chat_id=self.chat_id, document=document, caption=caption, **kwargs
        )

    async def edit(self, text: str, **kwargs) -> "Message":
        return await self._bot.edit_message_text(
            chat_id=self.chat_id, message_id=self.message_id, text=text, **kwargs
        )

    async def delete(self) -> bool:
        return await self._bot.delete_message(
            chat_id=self.chat_id, message_id=self.message_id
        )

    # --- Bot API 10.1: rich message ------------------------------------------
    async def answer_rich(self, rich, **kwargs) -> "Message":
        """Tuzilgan (rich) xabar yuboradi: sarlavha, ro'yxat, jadval, kod bloki."""
        payload = rich.to_dict() if hasattr(rich, "to_dict") else rich
        return await self._bot.request(
            "sendRichMessage", chat_id=self.chat_id, rich_message=payload, **kwargs
        )

    async def edit_rich(self, rich, **kwargs):
        """Rich xabarni tahrirlaydi (`editMessageText` + `rich_message`)."""
        payload = rich.to_dict() if hasattr(rich, "to_dict") else rich
        return await self._bot.request(
            "editMessageText",
            chat_id=self.chat_id,
            message_id=self.message_id,
            rich_message=payload,
            **kwargs,
        )

    # UZ: Bot API 10.2/10.3 ephemeral xabar helperlari.
    # RU: helper'ы ephemeral-сообщений Bot API 10.2/10.3.
    # EN: Bot API 10.2/10.3 ephemeral message helpers.
    async def answer_ephemeral(self, text: str, **kwargs) -> "Message":
        """UZ: Guruhda faqat shu foydalanuvchiga ko'rinadigan xabar yuboradi.
        RU: Отправляет сообщение, видимое только этому пользователю в группе.
        EN: Sends a message visible only to this user in a group.
        """
        params = dict(kwargs.pop("ephemeral_message_parameters", {}) or {})
        receiver_user_id = kwargs.pop("receiver_user_id", self.user_id)
        if receiver_user_id is not None:
            params.setdefault("receiver_user_id", receiver_user_id)
        if params:
            kwargs["ephemeral_message_parameters"] = params
        return await self._bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

    async def edit_ephemeral(self, text: str, **kwargs):
        return await self._bot.edit_ephemeral_message_text(
            chat_id=self.chat_id,
            ephemeral_message_id=self.ephemeral_message_id,
            text=text,
            **kwargs,
        )

    async def delete_ephemeral(self, **kwargs):
        return await self._bot.delete_ephemeral_message(
            chat_id=self.chat_id,
            ephemeral_message_id=self.ephemeral_message_id,
            **kwargs,
        )

    @property
    def is_ephemeral(self) -> bool:
        return self.ephemeral_message_id is not None

    # --- reaksiyalar ----------------------------------------------------------
    async def react(self, emoji: str = "👍", big: bool = False, **kwargs):
        """Xabarga reaksiya qo'yish. Premium emoji uchun `custom_emoji_id=` bering."""
        custom = kwargs.pop("custom_emoji_id", None)
        reaction = (
            [{"type": "custom_emoji", "custom_emoji_id": custom}]
            if custom
            else [{"type": "emoji", "emoji": emoji}]
        )
        return await self._bot.set_message_reaction(
            chat_id=self.chat_id,
            message_id=self.message_id,
            reaction=reaction,
            is_big=big,
            **kwargs,
        )

    async def unreact(self, **kwargs):
        return await self._bot.set_message_reaction(
            chat_id=self.chat_id, message_id=self.message_id, reaction=[], **kwargs
        )

    async def pin(self, **kwargs):
        return await self._bot.pin_chat_message(
            chat_id=self.chat_id, message_id=self.message_id, **kwargs
        )

    async def forward(self, to_chat_id, **kwargs):
        return await self._bot.forward_message(
            chat_id=to_chat_id,
            from_chat_id=self.chat_id,
            message_id=self.message_id,
            **kwargs,
        )


class CallbackQuery(TelegramObject):
    """Inline tugma bosilganda keladigan event."""

    @property
    def chat_id(self) -> Optional[int]:
        return self.message.chat_id if self.message else None

    @property
    def user_id(self) -> Optional[int]:
        return self.from_user.id if self.from_user else None

    async def answer(self, text: str = None, show_alert: bool = False, **kwargs) -> bool:
        return await self._bot.answer_callback_query(
            callback_query_id=self.id, text=text, show_alert=show_alert, **kwargs
        )

    async def edit(self, text: str, **kwargs):
        return await self._bot.edit_message_text(
            chat_id=self.chat_id, message_id=self.message.message_id, text=text, **kwargs
        )

    async def answer_message(self, text: str, **kwargs):
        return await self._bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

    async def answer_ephemeral(self, text: str, **kwargs):
        """UZ: Tugmani bosgan foydalanuvchigagina ko'rinadigan xabar yuboradi.
        RU: Отправляет сообщение, видимое только пользователю, нажавшему кнопку.
        EN: Sends a message visible only to the user who pressed the button.
        """
        params = dict(kwargs.pop("ephemeral_message_parameters", {}) or {})
        params.setdefault("callback_query_id", kwargs.pop("callback_query_id", self.id))
        kwargs["ephemeral_message_parameters"] = params
        return await self._bot.send_message(chat_id=self.chat_id, text=text, **kwargs)


class InlineQuery(TelegramObject):
    pass


class ChatMemberUpdated(TelegramObject):
    pass


class Poll(TelegramObject):
    pass


class PollAnswer(TelegramObject):
    pass


class ManagedBotUpdated(TelegramObject):
    """Bot yaratildi yoki tokeni almashtirildi (Bot API 9.6+)."""

    @property
    def bot_id(self):
        return self.bot.id if self.bot else None


class BusinessConnection(TelegramObject):
    pass


class MessageReactionUpdated(TelegramObject):
    pass


class ChatBoostUpdated(TelegramObject):
    pass


class BotSubscriptionUpdated(TelegramObject):
    """Foydalanuvchi obunasi o'zgardi (Bot API 10.2)."""


class PaidMediaPurchased(TelegramObject):
    pass


class MessageGenerationStopped(TelegramObject):
    """UZ: Foydalanuvchi xabar generatsiyasini to'xtatishni so'radi.
    RU: Пользователь запросил остановку генерации сообщения.
    EN: The user requested message generation to stop.
    """


class Update(TelegramObject):
    """Bitta update. `event_type` va `event` orqali ichidagi obyekt olinadi."""

    EVENT_TYPES = UpdateType.ALL

    @property
    def event_type(self) -> Optional[str]:
        for name in self.EVENT_TYPES:
            if name in self._data:
                return name
        return None

    @property
    def event(self) -> Optional[TelegramObject]:
        name = self.event_type
        return getattr(self, name) if name else None


# --- ichma-ich maydonlar uchun tiplarni bog'lash ------------------------------
_MESSAGE_FIELDS = {
    "from": User,
    "from_user": User,
    "chat": Chat,
    "sender_chat": Chat,
    "photo": PhotoSize,
    "document": Document,
    "video": Video,
    "audio": Audio,
    "voice": Voice,
    "contact": Contact,
    "location": Location,
    "entities": MessageEntity,
    "caption_entities": MessageEntity,
    "left_chat_member": User,
    "new_chat_members": User,
}
Message.__fields__ = dict(_MESSAGE_FIELDS)
Message.__fields__["reply_to_message"] = Message
Message.__fields__["pinned_message"] = Message

CallbackQuery.__fields__ = {"from": User, "from_user": User, "message": Message}
InlineQuery.__fields__ = {"from": User, "from_user": User, "location": Location}
ChatMemberUpdated.__fields__ = {"from": User, "from_user": User, "chat": Chat}
PollAnswer.__fields__ = {"user": User}
ManagedBotUpdated.__fields__ = {"user": User, "from": User, "from_user": User, "bot": User}
BusinessConnection.__fields__ = {"user": User, "from": User, "from_user": User}
MessageReactionUpdated.__fields__ = {"chat": Chat, "user": User, "from": User, "from_user": User}
ChatBoostUpdated.__fields__ = {"chat": Chat}
BotSubscriptionUpdated.__fields__ = {"from": User, "from_user": User, "chat": Chat}
PaidMediaPurchased.__fields__ = {"from": User, "from_user": User}
MessageGenerationStopped.__fields__ = {
    "chat": Chat,
    "from": User,
    "from_user": User,
    "user": User,
}

Update.__fields__ = {
    "message": Message,
    "edited_message": Message,
    "channel_post": Message,
    "edited_channel_post": Message,
    "callback_query": CallbackQuery,
    "inline_query": InlineQuery,
    "my_chat_member": ChatMemberUpdated,
    "chat_member": ChatMemberUpdated,
    "chat_join_request": ChatMemberUpdated,
    "poll": Poll,
    "poll_answer": PollAnswer,
    "business_connection": BusinessConnection,
    "business_message": Message,
    "edited_business_message": Message,
    "deleted_business_messages": TelegramObject,
    "message_reaction": MessageReactionUpdated,
    "message_reaction_count": MessageReactionUpdated,
    "chat_boost": ChatBoostUpdated,
    "removed_chat_boost": ChatBoostUpdated,
    "purchased_paid_media": PaidMediaPurchased,
    "stopped_message_generation": MessageGenerationStopped,
    "guest_message": Message,          # 10.0 — guest mode
    "managed_bot": ManagedBotUpdated,  # 9.6  — bot yaratadigan botlar
    "subscription": BotSubscriptionUpdated,  # 10.2
    "chosen_inline_result": TelegramObject,
    "shipping_query": TelegramObject,
    "pre_checkout_query": TelegramObject,
}


def _from_user_alias(self):
    """Telegram'dagi `from` kaliti Python'da band, shuning uchun from_user."""
    data = self.__dict__.get("_data") or {}
    value = data.get("from")
    return User(value, self._bot) if value else None


for _cls in (
    Message,
    CallbackQuery,
    InlineQuery,
    ChatMemberUpdated,
    ManagedBotUpdated,
    BusinessConnection,
    MessageReactionUpdated,
    BotSubscriptionUpdated,
    PaidMediaPurchased,
    MessageGenerationStopped,
):
    _cls.from_user = property(_from_user_alias)
