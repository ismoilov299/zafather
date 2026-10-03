"""UZ: `Message` modeli va javob yorliqlari.
RU: Модель `Message` и методы-ярлыки для ответа.
EN: The `Message` model and reply shortcuts.
"""

from __future__ import annotations

from typing import Any

from ..enums import ContentType
from .base import TelegramObject
from .models import (
    Animation,
    Audio,
    Chat,
    Contact,
    Dice,
    Document,
    Location,
    MessageEntity,
    PhotoSize,
    Poll,
    Sticker,
    User,
    Venue,
    Video,
    VideoNote,
    Voice,
    WebAppData,
)

_CONTENT_TYPES = tuple(
    value for name, value in vars(ContentType).items() if name.isupper() and isinstance(value, str)
)


class Message(TelegramObject):
    """UZ: Xabar va unga javob berish yorliqlari.
    RU: Сообщение и ярлыки для ответа на него.
    EN: A message plus shortcuts for replying to it.

    UZ: Javob metodlari forum mavzusi (`message_thread_id`) va biznes ulanishini
    (`business_connection_id`) avtomatik saqlaydi.
    RU: Методы ответа автоматически сохраняют тему форума (`message_thread_id`) и
    бизнес-подключение (`business_connection_id`).
    EN: Reply helpers keep the forum topic (`message_thread_id`) and the business
    connection (`business_connection_id`) automatically.
    """

    __slots__ = ()

    # --- UZ: qulay xususiyatlar / RU: удобные свойства / EN: convenience properties ---
    @property
    def chat_id(self) -> int | None:
        chat = self._data.get("chat")
        return chat.get("id") if isinstance(chat, dict) else None

    @property
    def user_id(self) -> int | None:
        sender = self._data.get("from")
        return sender.get("id") if isinstance(sender, dict) else None

    @property
    def content(self) -> str | None:
        """UZ: `text` yoki `caption`. RU: `text` или `caption`. EN: `text` or `caption`."""
        return self.text or self.caption

    @property
    def content_type(self) -> str | None:
        """UZ: Birinchi topilgan kontent turi (`ContentType` qiymati).
        RU: Первый найденный тип контента (значение `ContentType`).
        EN: The first matching content type (a `ContentType` value).
        """
        return next((name for name in _CONTENT_TYPES if name in self._data), None)

    @property
    def is_ephemeral(self) -> bool:
        return self._data.get("ephemeral_message_id") is not None

    @property
    def is_command(self) -> bool:
        text = self._data.get("text")
        return isinstance(text, str) and text.startswith("/")

    def _send_defaults(self) -> dict[str, Any]:
        thread_id = (
            self._data.get("message_thread_id") if self._data.get("is_topic_message") else None
        )
        return {
            "chat_id": self.chat_id,
            "message_thread_id": thread_id,
            "business_connection_id": self._data.get("business_connection_id"),
        }

    async def _send(self, method: str, **params: Any) -> Any:
        return await self._client().request(method, **{**self._send_defaults(), **params})

    def _target(self) -> dict[str, Any]:
        return {"chat_id": self.chat_id, "message_id": self.message_id}

    # --- UZ: yuborish / RU: отправка / EN: sending ---------------------------------------
    async def answer(self, text: str, **kwargs: Any) -> Any:
        """UZ: Shu chatga matn yuboradi. RU: Отправляет текст в этот чат.
        EN: Sends a text message to this chat.
        """
        return await self._send("sendMessage", text=text, **kwargs)

    async def reply(self, text: str, **kwargs: Any) -> Any:
        """UZ: Shu xabarga javob (reply) sifatida matn yuboradi.
        RU: Отправляет текст ответом (reply) на это сообщение.
        EN: Sends a text message as a reply to this message.
        """
        kwargs.setdefault("reply_parameters", {"message_id": self.message_id})
        return await self.answer(text, **kwargs)

    async def answer_photo(self, photo: Any, caption: str | None = None, **kwargs: Any) -> Any:
        return await self._send("sendPhoto", photo=photo, caption=caption, **kwargs)

    async def answer_document(
        self, document: Any, caption: str | None = None, **kwargs: Any
    ) -> Any:
        return await self._send("sendDocument", document=document, caption=caption, **kwargs)

    async def answer_video(self, video: Any, caption: str | None = None, **kwargs: Any) -> Any:
        return await self._send("sendVideo", video=video, caption=caption, **kwargs)

    async def answer_audio(self, audio: Any, caption: str | None = None, **kwargs: Any) -> Any:
        return await self._send("sendAudio", audio=audio, caption=caption, **kwargs)

    async def answer_voice(self, voice: Any, caption: str | None = None, **kwargs: Any) -> Any:
        return await self._send("sendVoice", voice=voice, caption=caption, **kwargs)

    async def answer_animation(
        self, animation: Any, caption: str | None = None, **kwargs: Any
    ) -> Any:
        return await self._send("sendAnimation", animation=animation, caption=caption, **kwargs)

    async def answer_sticker(self, sticker: Any, **kwargs: Any) -> Any:
        return await self._send("sendSticker", sticker=sticker, **kwargs)

    async def answer_location(self, latitude: float, longitude: float, **kwargs: Any) -> Any:
        return await self._send("sendLocation", latitude=latitude, longitude=longitude, **kwargs)

    async def answer_dice(self, emoji: str = "🎲", **kwargs: Any) -> Any:
        return await self._send("sendDice", emoji=emoji, **kwargs)

    async def answer_media_group(self, media: list[Any], **kwargs: Any) -> Any:
        return await self._send("sendMediaGroup", media=media, **kwargs)

    async def answer_chat_action(self, action: str = "typing", **kwargs: Any) -> Any:
        return await self._send("sendChatAction", action=action, **kwargs)

    async def answer_rich(self, rich: Any, **kwargs: Any) -> Any:
        """UZ: Tuzilgan (rich) xabar yuboradi (Bot API 10.1+).
        RU: Отправляет структурированное (rich) сообщение (Bot API 10.1+).
        EN: Sends a structured (rich) message (Bot API 10.1+).
        """
        return await self._send("sendRichMessage", rich_message=rich, **kwargs)

    async def answer_ephemeral(self, text: str, **kwargs: Any) -> Any:
        """UZ: Guruhda faqat shu foydalanuvchiga ko'rinadigan xabar (Bot API 10.3).
        RU: Сообщение, видимое в группе только этому пользователю (Bot API 10.3).
        EN: A message visible only to this user inside a group (Bot API 10.3).
        """
        params = dict(kwargs.pop("ephemeral_message_parameters", None) or {})
        receiver_user_id = kwargs.pop("receiver_user_id", self.user_id)
        if receiver_user_id is not None:
            params.setdefault("receiver_user_id", receiver_user_id)
        if params:
            kwargs["ephemeral_message_parameters"] = params
        return await self.answer(text, **kwargs)

    # --- UZ: tahrirlash / RU: редактирование / EN: editing --------------------------------
    async def edit_text(self, text: str, **kwargs: Any) -> Any:
        return await self._client().request(
            "editMessageText", **self._target(), text=text, **kwargs
        )

    #: UZ: Eski nom. RU: Старое имя. EN: Legacy name.
    edit = edit_text

    async def edit_caption(self, caption: str, **kwargs: Any) -> Any:
        return await self._client().request(
            "editMessageCaption", **self._target(), caption=caption, **kwargs
        )

    async def edit_reply_markup(self, reply_markup: Any = None, **kwargs: Any) -> Any:
        return await self._client().request(
            "editMessageReplyMarkup", **self._target(), reply_markup=reply_markup, **kwargs
        )

    async def edit_rich(self, rich: Any, **kwargs: Any) -> Any:
        return await self._client().request(
            "editMessageText", **self._target(), rich_message=rich, **kwargs
        )

    async def edit_ephemeral(self, text: str, **kwargs: Any) -> Any:
        return await self._client().request(
            "editEphemeralMessageText",
            chat_id=self.chat_id,
            ephemeral_message_id=self.ephemeral_message_id,
            text=text,
            **kwargs,
        )

    async def delete_ephemeral(self, **kwargs: Any) -> Any:
        return await self._client().request(
            "deleteEphemeralMessage",
            chat_id=self.chat_id,
            ephemeral_message_id=self.ephemeral_message_id,
            **kwargs,
        )

    # --- UZ: boshqa amallar / RU: прочие действия / EN: other actions --------------------
    async def delete(self) -> Any:
        return await self._client().request("deleteMessage", **self._target())

    async def forward(self, chat_id: int | str, **kwargs: Any) -> Any:
        return await self._client().request(
            "forwardMessage",
            chat_id=chat_id,
            from_chat_id=self.chat_id,
            message_id=self.message_id,
            **kwargs,
        )

    async def copy_to(self, chat_id: int | str, **kwargs: Any) -> Any:
        return await self._client().request(
            "copyMessage",
            chat_id=chat_id,
            from_chat_id=self.chat_id,
            message_id=self.message_id,
            **kwargs,
        )

    async def pin(self, **kwargs: Any) -> Any:
        return await self._client().request("pinChatMessage", **self._target(), **kwargs)

    async def unpin(self, **kwargs: Any) -> Any:
        return await self._client().request("unpinChatMessage", **self._target(), **kwargs)

    async def react(
        self,
        emoji: str = "👍",
        big: bool = False,
        custom_emoji_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """UZ: Reaksiya qo'yadi; premium emoji uchun `custom_emoji_id` bering.
        RU: Ставит реакцию; для premium emoji передайте `custom_emoji_id`.
        EN: Sets a reaction; pass `custom_emoji_id` for a premium emoji.
        """
        reaction = (
            {"type": "custom_emoji", "custom_emoji_id": custom_emoji_id}
            if custom_emoji_id
            else {"type": "emoji", "emoji": emoji}
        )
        return await self._client().request(
            "setMessageReaction", **self._target(), reaction=[reaction], is_big=big, **kwargs
        )

    async def unreact(self, **kwargs: Any) -> Any:
        return await self._client().request(
            "setMessageReaction", **self._target(), reaction=[], **kwargs
        )


Message.FIELD_TYPES = {
    "from": User,
    "sender_chat": Chat,
    "sender_business_bot": User,
    "chat": Chat,
    "via_bot": User,
    "reply_to_message": Message,
    "pinned_message": Message,
    "photo": PhotoSize,
    "animation": Animation,
    "audio": Audio,
    "document": Document,
    "sticker": Sticker,
    "video": Video,
    "video_note": VideoNote,
    "voice": Voice,
    "contact": Contact,
    "location": Location,
    "venue": Venue,
    "dice": Dice,
    "poll": Poll,
    "entities": MessageEntity,
    "caption_entities": MessageEntity,
    "new_chat_members": User,
    "left_chat_member": User,
    "web_app_data": WebAppData,
}

__all__ = ["Message"]
