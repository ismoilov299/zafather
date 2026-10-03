"""UZ: So'rov turidagi update'lar: callback, inline, to'lov so'rovlari.
RU: Update-запросы: callback, inline, платёжные запросы.
EN: Query updates: callback, inline and payment queries.
"""

from __future__ import annotations

from typing import Any

from .base import TelegramObject
from .message import Message
from .models import Location, User


class CallbackQuery(TelegramObject):
    """UZ: Inline tugma bosildi. RU: Нажата inline-кнопка. EN: An inline button was pressed."""

    __slots__ = ()

    @property
    def chat_id(self) -> int | None:
        message = self.message
        return message.chat_id if isinstance(message, Message) else None

    @property
    def user_id(self) -> int | None:
        sender = self._data.get("from")
        return sender.get("id") if isinstance(sender, dict) else None

    def _target(self) -> dict[str, Any]:
        inline_id = self._data.get("inline_message_id")
        if inline_id:
            return {"inline_message_id": inline_id}
        message = self.message
        return {
            "chat_id": self.chat_id,
            "message_id": message.message_id if isinstance(message, Message) else None,
        }

    async def answer(self, text: str | None = None, show_alert: bool = False, **kwargs: Any) -> Any:
        """UZ: Tugma bosilishiga javob (bildirishnoma yoki alert).
        RU: Ответ на нажатие кнопки (уведомление или alert).
        EN: Answers the button press (toast notification or alert).
        """
        return await self._client().request(
            "answerCallbackQuery",
            callback_query_id=self.id,
            text=text,
            show_alert=show_alert,
            **kwargs,
        )

    async def edit_text(self, text: str, **kwargs: Any) -> Any:
        return await self._client().request(
            "editMessageText", **self._target(), text=text, **kwargs
        )

    #: UZ: Eski nom. RU: Старое имя. EN: Legacy name.
    edit = edit_text

    async def edit_reply_markup(self, reply_markup: Any = None, **kwargs: Any) -> Any:
        return await self._client().request(
            "editMessageReplyMarkup", **self._target(), reply_markup=reply_markup, **kwargs
        )

    async def delete_message(self) -> Any:
        return await self._client().request("deleteMessage", **self._target())

    async def answer_message(self, text: str, **kwargs: Any) -> Any:
        """UZ: Tugma joylashgan chatga yangi xabar yuboradi.
        RU: Отправляет новое сообщение в чат с кнопкой.
        EN: Sends a new message to the chat that holds the button.
        """
        return await self._client().request(
            "sendMessage", chat_id=self.chat_id, text=text, **kwargs
        )

    async def answer_ephemeral(self, text: str, **kwargs: Any) -> Any:
        """UZ: Faqat tugmani bosgan foydalanuvchiga ko'rinadigan xabar (Bot API 10.3).
        RU: Сообщение, видимое только нажавшему кнопку (Bot API 10.3).
        EN: A message visible only to the user who pressed the button (Bot API 10.3).
        """
        params = dict(kwargs.pop("ephemeral_message_parameters", None) or {})
        params.setdefault("callback_query_id", kwargs.pop("callback_query_id", self.id))
        return await self.answer_message(text, ephemeral_message_parameters=params, **kwargs)


class InlineQuery(TelegramObject):
    """UZ: Inline rejimdagi so'rov. RU: Запрос в inline-режиме. EN: An inline-mode query."""

    __slots__ = ()

    async def answer(self, results: list[Any], **kwargs: Any) -> Any:
        return await self._client().request(
            "answerInlineQuery", inline_query_id=self.id, results=results, **kwargs
        )


class ChosenInlineResult(TelegramObject):
    __slots__ = ()


class ShippingQuery(TelegramObject):
    """UZ: Yetkazib berish manzili so'rovi. RU: Запрос адреса доставки.
    EN: A shipping address query.
    """

    __slots__ = ()

    async def answer(
        self,
        ok: bool,
        shipping_options: list[Any] | None = None,
        error_message: str | None = None,
    ) -> Any:
        return await self._client().request(
            "answerShippingQuery",
            shipping_query_id=self.id,
            ok=ok,
            shipping_options=shipping_options,
            error_message=error_message,
        )


class PreCheckoutQuery(TelegramObject):
    """UZ: To'lovdan oldingi tasdiq so'rovi. RU: Запрос подтверждения перед оплатой.
    EN: A pre-checkout confirmation query.
    """

    __slots__ = ()

    async def answer(self, ok: bool = True, error_message: str | None = None) -> Any:
        return await self._client().request(
            "answerPreCheckoutQuery",
            pre_checkout_query_id=self.id,
            ok=ok,
            error_message=error_message,
        )


CallbackQuery.FIELD_TYPES = {"from": User, "message": Message}
InlineQuery.FIELD_TYPES = {"from": User, "location": Location}
ChosenInlineResult.FIELD_TYPES = {"from": User, "location": Location}
ShippingQuery.FIELD_TYPES = {"from": User}
PreCheckoutQuery.FIELD_TYPES = {"from": User}

__all__ = [
    "CallbackQuery",
    "ChosenInlineResult",
    "InlineQuery",
    "PreCheckoutQuery",
    "ShippingQuery",
]
