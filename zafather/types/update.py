"""UZ: `Update` modeli va API natijalarini o'rash.
RU: Модель `Update` и обёртка результатов API.
EN: The `Update` model and API result wrapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..enums import UpdateType
from .base import TelegramObject
from .message import Message
from .models import (
    BotSubscriptionUpdated,
    BusinessConnection,
    BusinessMessagesDeleted,
    ChatBoostRemoved,
    ChatBoostUpdated,
    ChatJoinRequest,
    ChatMemberUpdated,
    File,
    ManagedBotUpdated,
    MessageGenerationStopped,
    MessageReactionCountUpdated,
    MessageReactionUpdated,
    PaidMediaPurchased,
    Poll,
    PollAnswer,
    User,
)
from .queries import (
    CallbackQuery,
    ChosenInlineResult,
    InlineQuery,
    PreCheckoutQuery,
    ShippingQuery,
)

if TYPE_CHECKING:
    from ..bot import Bot


class Update(TelegramObject):
    """UZ: Bitta update. `event_type` — turi, `event` — ichidagi obyekt.
    RU: Один update. `event_type` — тип, `event` — вложенный объект.
    EN: A single update. `event_type` is its type and `event` the inner object.
    """

    __slots__ = ()

    @property
    def event_type(self) -> str | None:
        return next((name for name in UpdateType.ALL if name in self._data), None)

    @property
    def event(self) -> TelegramObject | None:
        name = self.event_type
        return getattr(self, name) if name else None


Update.FIELD_TYPES = {
    UpdateType.MESSAGE: Message,
    UpdateType.EDITED_MESSAGE: Message,
    UpdateType.CHANNEL_POST: Message,
    UpdateType.EDITED_CHANNEL_POST: Message,
    UpdateType.BUSINESS_CONNECTION: BusinessConnection,
    UpdateType.BUSINESS_MESSAGE: Message,
    UpdateType.EDITED_BUSINESS_MESSAGE: Message,
    UpdateType.DELETED_BUSINESS_MESSAGES: BusinessMessagesDeleted,
    UpdateType.MESSAGE_REACTION: MessageReactionUpdated,
    UpdateType.MESSAGE_REACTION_COUNT: MessageReactionCountUpdated,
    UpdateType.INLINE_QUERY: InlineQuery,
    UpdateType.CHOSEN_INLINE_RESULT: ChosenInlineResult,
    UpdateType.CALLBACK_QUERY: CallbackQuery,
    UpdateType.SHIPPING_QUERY: ShippingQuery,
    UpdateType.PRE_CHECKOUT_QUERY: PreCheckoutQuery,
    UpdateType.PURCHASED_PAID_MEDIA: PaidMediaPurchased,
    UpdateType.POLL: Poll,
    UpdateType.POLL_ANSWER: PollAnswer,
    UpdateType.MY_CHAT_MEMBER: ChatMemberUpdated,
    UpdateType.CHAT_MEMBER: ChatMemberUpdated,
    UpdateType.CHAT_JOIN_REQUEST: ChatJoinRequest,
    UpdateType.CHAT_BOOST: ChatBoostUpdated,
    UpdateType.REMOVED_CHAT_BOOST: ChatBoostRemoved,
    UpdateType.GUEST_MESSAGE: Message,
    UpdateType.MANAGED_BOT: ManagedBotUpdated,
    UpdateType.SUBSCRIPTION: BotSubscriptionUpdated,
    UpdateType.STOPPED_MESSAGE_GENERATION: MessageGenerationStopped,
}


def wrap_result(result: Any, bot: Bot | None = None) -> Any:
    """UZ: API natijasini mos modelga o'raydi (topilmasa — `TelegramObject`).
    RU: Оборачивает результат API в подходящую модель (иначе — `TelegramObject`).
    EN: Wraps an API result into the matching model (falls back to `TelegramObject`).
    """
    if isinstance(result, list):
        return [wrap_result(item, bot) for item in result]
    if not isinstance(result, dict):
        return result
    if "update_id" in result:
        return Update(result, bot)
    if "message_id" in result and "chat" in result:
        return Message(result, bot)
    if "is_bot" in result and "id" in result:
        return User(result, bot)
    if "file_id" in result and "file_unique_id" in result and "file_path" in result:
        return File(result, bot)
    return TelegramObject(result, bot)


__all__ = ["Update", "wrap_result"]
