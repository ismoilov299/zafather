"""UZ: Oddiy Telegram modellari (foydalanuvchi, chat, media va boshqalar).
RU: Простые модели Telegram (пользователь, чат, медиа и другие).
EN: Plain Telegram models (user, chat, media and others).
"""

from __future__ import annotations

import html
from typing import Any

from .base import TelegramObject


def _join_name(first: str | None, last: str | None) -> str:
    return " ".join(part for part in (first, last) if part)


class User(TelegramObject):
    """UZ: Telegram foydalanuvchisi yoki boti. RU: Пользователь или бот Telegram.
    EN: A Telegram user or bot.
    """

    __slots__ = ()

    @property
    def full_name(self) -> str:
        return _join_name(self.first_name, self.last_name)

    @property
    def url(self) -> str:
        return f"tg://user?id={self.id}"

    def mention_html(self, name: str | None = None) -> str:
        """UZ: Foydalanuvchiga HTML havola (ism ekranlanadi).
        RU: HTML-ссылка на пользователя (имя экранируется).
        EN: HTML link to the user (the name is escaped).
        """
        label = html.escape(name if name is not None else self.full_name, quote=False)
        return f'<a href="{self.url}">{label}</a>'

    @property
    def mention(self) -> str:
        return self.mention_html()


class Chat(TelegramObject):
    """UZ: Chat (shaxsiy, guruh, superguruh yoki kanal).
    RU: Чат (личный, группа, супергруппа или канал).
    EN: A chat (private, group, supergroup or channel).
    """

    __slots__ = ()

    @property
    def full_name(self) -> str:
        if self.title:
            return str(self.title)
        return _join_name(self.first_name, self.last_name)


class PhotoSize(TelegramObject):
    __slots__ = ()


class Animation(TelegramObject):
    __slots__ = ()


class Audio(TelegramObject):
    __slots__ = ()


class Document(TelegramObject):
    __slots__ = ()


class Video(TelegramObject):
    __slots__ = ()


class VideoNote(TelegramObject):
    __slots__ = ()


class Voice(TelegramObject):
    __slots__ = ()


class Sticker(TelegramObject):
    __slots__ = ()


class Contact(TelegramObject):
    __slots__ = ()


class Location(TelegramObject):
    __slots__ = ()


class Venue(TelegramObject):
    __slots__ = ()


class Dice(TelegramObject):
    __slots__ = ()


class File(TelegramObject):
    """UZ: `getFile` natijasi. RU: Результат `getFile`. EN: The result of `getFile`."""

    __slots__ = ()


class MessageEntity(TelegramObject):
    __slots__ = ()


class WebAppData(TelegramObject):
    """UZ: Mini App `sendData()` orqali yuborgan ma'lumot.
    RU: Данные, отправленные Mini App через `sendData()`.
    EN: Data sent by a Mini App via `sendData()`.
    """

    __slots__ = ()


class PollOption(TelegramObject):
    __slots__ = ()


class Poll(TelegramObject):
    __slots__ = ()


class PollAnswer(TelegramObject):
    __slots__ = ()


class ChatMember(TelegramObject):
    __slots__ = ()


class ChatMemberUpdated(TelegramObject):
    __slots__ = ()


class ChatJoinRequest(TelegramObject):
    """UZ: Chatga qo'shilish so'rovi. RU: Заявка на вступление в чат.
    EN: A request to join a chat.
    """

    __slots__ = ()

    async def approve(self) -> Any:
        return await self._client().request(
            "approveChatJoinRequest", chat_id=self.chat.id, user_id=self.from_user.id
        )

    async def decline(self) -> Any:
        return await self._client().request(
            "declineChatJoinRequest", chat_id=self.chat.id, user_id=self.from_user.id
        )


class ChatBoostUpdated(TelegramObject):
    __slots__ = ()


class ChatBoostRemoved(TelegramObject):
    __slots__ = ()


class MessageReactionUpdated(TelegramObject):
    __slots__ = ()


class MessageReactionCountUpdated(TelegramObject):
    __slots__ = ()


class BusinessConnection(TelegramObject):
    __slots__ = ()


class BusinessMessagesDeleted(TelegramObject):
    __slots__ = ()


class PaidMediaPurchased(TelegramObject):
    __slots__ = ()


class ManagedBotUpdated(TelegramObject):
    """UZ: Boshqariladigan bot yaratildi yoki tokeni almashdi (Bot API 9.6+).
    RU: Управляемый бот создан или его токен изменён (Bot API 9.6+).
    EN: A managed bot was created or its token changed (Bot API 9.6+).
    """

    __slots__ = ()

    @property
    def bot_id(self) -> int | None:
        managed = self._data.get("bot")
        return managed.get("id") if isinstance(managed, dict) else None


class BotSubscriptionUpdated(TelegramObject):
    """UZ: Foydalanuvchi obunasi o'zgardi (Bot API 10.2).
    RU: Изменилась подписка пользователя (Bot API 10.2).
    EN: A user's subscription changed (Bot API 10.2).
    """

    __slots__ = ()


class MessageGenerationStopped(TelegramObject):
    """UZ: Foydalanuvchi xabar generatsiyasini to'xtatishni so'radi (Bot API 10.3).
    RU: Пользователь попросил остановить генерацию сообщения (Bot API 10.3).
    EN: The user asked to stop message generation (Bot API 10.3).
    """

    __slots__ = ()


PollAnswer.FIELD_TYPES = {"user": User, "voter_chat": Chat}
Poll.FIELD_TYPES = {"options": PollOption}
ChatMember.FIELD_TYPES = {"user": User}
ChatMemberUpdated.FIELD_TYPES = {
    "from": User,
    "chat": Chat,
    "old_chat_member": ChatMember,
    "new_chat_member": ChatMember,
}
ChatJoinRequest.FIELD_TYPES = {"from": User, "chat": Chat}
ChatBoostUpdated.FIELD_TYPES = {"chat": Chat}
ChatBoostRemoved.FIELD_TYPES = {"chat": Chat}
MessageReactionUpdated.FIELD_TYPES = {"chat": Chat, "user": User, "actor_chat": Chat}
MessageReactionCountUpdated.FIELD_TYPES = {"chat": Chat}
BusinessConnection.FIELD_TYPES = {"user": User}
BusinessMessagesDeleted.FIELD_TYPES = {"chat": Chat}
PaidMediaPurchased.FIELD_TYPES = {"from": User}
ManagedBotUpdated.FIELD_TYPES = {"user": User, "bot": User, "from": User}
BotSubscriptionUpdated.FIELD_TYPES = {"from": User, "user": User, "chat": Chat}
MessageGenerationStopped.FIELD_TYPES = {"chat": Chat, "from": User, "user": User}
MessageEntity.FIELD_TYPES = {"user": User}

__all__ = [
    "Animation",
    "Audio",
    "BotSubscriptionUpdated",
    "BusinessConnection",
    "BusinessMessagesDeleted",
    "Chat",
    "ChatBoostRemoved",
    "ChatBoostUpdated",
    "ChatJoinRequest",
    "ChatMember",
    "ChatMemberUpdated",
    "Contact",
    "Dice",
    "Document",
    "File",
    "Location",
    "ManagedBotUpdated",
    "MessageEntity",
    "MessageGenerationStopped",
    "MessageReactionCountUpdated",
    "MessageReactionUpdated",
    "PaidMediaPurchased",
    "PhotoSize",
    "Poll",
    "PollAnswer",
    "PollOption",
    "Sticker",
    "User",
    "Venue",
    "Video",
    "VideoNote",
    "Voice",
    "WebAppData",
]
