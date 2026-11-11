"""UZ: Widget, so'rov va wallet modellari (Bot API 10.4).
RU: Модели виджета, запросов и кошелька (Bot API 10.4).
EN: Widget, query and wallet models (Bot API 10.4).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from .base import TelegramObject
from .models import Chat, User

if TYPE_CHECKING:
    from ..bot import Bot


class Widget(TelegramObject):
    """UZ: Xabardagi widget: `message.widget.html`.
    RU: Виджет сообщения: `message.widget.html`.
    EN: A message widget: `message.widget.html`.
    """

    __slots__ = ()


class ExternalReplyInfo(TelegramObject):
    """UZ: Tashqi javob kontenti: `message.external_reply.widget`.
    RU: Содержимое внешнего ответа: `message.external_reply.widget`.
    EN: External reply content: `message.external_reply.widget`.
    """

    __slots__ = ()
    FIELD_TYPES: ClassVar[Mapping[str, type[TelegramObject]]] = {"widget": Widget, "chat": Chat}


class TonWalletCard(TelegramObject):
    """UZ: Wallet kartasi: `query.type.wallet_card.address`.
    RU: Карточка кошелька: `query.type.wallet_card.address`.
    EN: Wallet card: `query.type.wallet_card.address`.
    """

    __slots__ = ()


class WidgetQueryWallet(TelegramObject):
    """UZ: So'rov walleti: `query.type.wallet.address`.
    RU: Кошелёк запроса: `query.type.wallet.address`.
    EN: Query wallet: `query.type.wallet.address`.
    """

    __slots__ = ()


class WidgetQueryType(TelegramObject):
    """UZ: So'rov turi avtomatik tanlanadi: `query.type.type == 'data'`.
    RU: Тип запроса выбирается автоматически: `query.type.type == 'data'`.
    EN: Query variants are selected automatically: `query.type.type == 'data'`.
    """

    __slots__ = ()

    def __new__(
        cls, data: Mapping[str, Any] | None = None, bot: Bot | None = None
    ) -> WidgetQueryType:
        if cls is WidgetQueryType:
            variant = _QUERY_TYPES.get((data or {}).get("type"), cls)
            return object.__new__(variant)
        return object.__new__(cls)


class WidgetQueryTypeData(WidgetQueryType):
    """UZ: Oddiy so'rov: `query.type.wallet_card` ixtiyoriy.
    RU: Обычный запрос: `query.type.wallet_card` необязателен.
    EN: Data query: `query.type.wallet_card` is optional.
    """

    __slots__ = ()
    FIELD_TYPES: ClassVar[Mapping[str, type[TelegramObject]]] = {"wallet_card": TonWalletCard}


class WidgetQueryTypeSignData(WidgetQueryType):
    """UZ: Imzo so'rovi: `query.type.sign_data`; imzoni backend tekshiradi.
    RU: Подписанные данные: `query.type.sign_data`; подпись проверяет backend.
    EN: Signed data: `query.type.sign_data`; the backend verifies the signature.
    """

    __slots__ = ()
    FIELD_TYPES: ClassVar[Mapping[str, type[TelegramObject]]] = {"wallet": WidgetQueryWallet}


class WidgetQueryTypeSentTransaction(WidgetQueryType):
    """UZ: Tranzaksiya xabari: `query.type.msg_hash`; to'lovni zanjirda tekshiring.
    RU: Уведомление о транзакции: `query.type.msg_hash`; проверяйте платёж в сети.
    EN: Transaction notification: `query.type.msg_hash`; verify payment on-chain.
    """

    __slots__ = ()
    FIELD_TYPES: ClassVar[Mapping[str, type[TelegramObject]]] = {"wallet": WidgetQueryWallet}


_QUERY_TYPES: dict[Any, type[WidgetQueryType]] = {
    "data": WidgetQueryTypeData,
    "sign_data": WidgetQueryTypeSignData,
    "sent_transaction": WidgetQueryTypeSentTransaction,
}


class _WidgetQuery(TelegramObject):
    """UZ: Forward widget so'rovi: `await query.answer('ok')`; chat noma'lum.
    RU: Запрос из пересланного виджета: `await query.answer('ok')`; чат неизвестен.
    EN: Forwarded widget query: `await query.answer('ok')`; the chat is unknown.
    """

    __slots__ = ()
    FIELD_TYPES: ClassVar[Mapping[str, type[TelegramObject]]] = {
        "from": User,
        "type": WidgetQueryType,
    }

    @property
    def user_id(self) -> int | None:
        sender = self._data.get("from")
        return sender.get("id") if isinstance(sender, dict) else None

    async def answer(self, data: str | None = None, **kwargs: Any) -> Any:
        """UZ: 15 soniyada javob: `await query.answer('ok')`; holatni o'zgartirmaydi.
        RU: Ответ за 15 секунд: `await query.answer('ok')`; состояние не меняет.
        EN: Answer within 15 seconds: `await query.answer('ok')`; state is unchanged.
        """
        return await self._client().answer_widget_query(self.id, data=data, **kwargs)

    async def edit_shared_data(
        self, public_data: str, *, cache_time: int | None = None, **kwargs: Any
    ) -> Any:
        """UZ: Umumiy holat: `await query.edit_shared_data('{}')`.
        RU: Общее состояние: `await query.edit_shared_data('{}')`.
        EN: Shared state: `await query.edit_shared_data('{}')`.
        """
        if not self.widget_id:
            raise ValueError("This query does not refer to a shared widget")
        return await self._client().edit_shared_widget_data(
            self.widget_id, public_data, cache_time=cache_time, **kwargs
        )


class SharedWidgetQuery(_WidgetQuery):
    """UZ: Forward so'rovi: `await query.answer()`; chat koordinatalari mavjud emas.
    RU: Запрос из пересылки: `await query.answer()`; координат чата нет.
    EN: Forward query: `await query.answer()`; no chat coordinates are available.
    """

    __slots__ = ()


class WidgetQuery(_WidgetQuery):
    """UZ: Original yoki inline widget so'rovi: `await query.edit_data(chat_data='{}')`.
    RU: Запрос исходного или inline-виджета: `await query.edit_data(chat_data='{}')`.
    EN: Original or inline widget query: `await query.edit_data(chat_data='{}')`.
    """

    __slots__ = ()
    FIELD_TYPES: ClassVar[Mapping[str, type[TelegramObject]]] = {
        **_WidgetQuery.FIELD_TYPES,
        "chat": Chat,
    }

    @property
    def chat_id(self) -> int | None:
        chat = self._data.get("chat")
        return chat.get("id") if isinstance(chat, dict) else None

    def _target(self) -> dict[str, Any]:
        if self.inline_message_id:
            return {"inline_message_id": self.inline_message_id}
        if self.chat_id is None or self.message_id is None:
            raise ValueError("Widget query has no message coordinates")
        return {"chat_id": self.chat_id, "message_id": self.message_id}

    async def edit_data(
        self, *, public_data: str | None = None, chat_data: str | None = None, **kwargs: Any
    ) -> Any:
        """UZ: Xabar holati: `await query.edit_data(chat_data='')` holatni tozalaydi.
        RU: Состояние сообщения: `await query.edit_data(chat_data='')` очищает данные.
        EN: Message state: `await query.edit_data(chat_data='')` clears the data.
        """
        return await self._client().edit_message_widget_data(
            **self._target(), public_data=public_data, chat_data=chat_data, **kwargs
        )


__all__ = [
    "ExternalReplyInfo",
    "SharedWidgetQuery",
    "TonWalletCard",
    "Widget",
    "WidgetQuery",
    "WidgetQueryType",
    "WidgetQueryTypeData",
    "WidgetQueryTypeSentTransaction",
    "WidgetQueryTypeSignData",
    "WidgetQueryWallet",
]
