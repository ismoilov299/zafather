"""UZ: Dispatcher — update'dan kontekst yasab, routerga uzatadi.
RU: Dispatcher — строит контекст из update и передаёт его в router.
EN: Dispatcher — builds the context for an update and hands it to the router.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .fsm import BaseStorage, FSMContext, FSMStrategy
from .types import Update

if TYPE_CHECKING:
    from .bot import Bot
    from .router import Router

log = logging.getLogger("zafather.dispatcher")


@dataclass(frozen=True)
class EventScope:
    """UZ: Event qaysi chat, foydalanuvchi va forum mavzusiga tegishli.
    RU: К какому чату, пользователю и теме форума относится событие.
    EN: The chat, user and forum topic an event belongs to.
    """

    chat_id: int | None
    user_id: int | None
    thread_id: int | None = None

    @classmethod
    def from_event(cls, event: Any) -> EventScope:
        chat = getattr(event, "chat", None)
        if chat is None:
            chat = getattr(getattr(event, "message", None), "chat", None)
        user = getattr(event, "from_user", None) or getattr(event, "user", None)
        thread_id = event.message_thread_id if getattr(event, "is_topic_message", None) else None
        chat_id = chat.id if chat is not None else (user.id if user is not None else None)
        user_id = user.id if user is not None else chat_id
        return cls(chat_id, user_id, thread_id)


class Dispatcher:
    """UZ: Update'larni qayta ishlaydi: kontekst, FSM holati va xatolarni yo'naltirish.
    RU: Обрабатывает update: контекст, состояние FSM и маршрутизация ошибок.
    EN: Processes updates: context, FSM state and error routing.

    UZ: `context` — barcha handlerlarga uzatiladigan umumiy lug'at (masalan, DB).
    RU: `context` — общий словарь, передаваемый всем handlers (например, БД).
    EN: `context` is a shared dict passed to every handler (for example a DB).
    """

    def __init__(
        self,
        router: Router,
        *,
        bot: Bot,
        storage: BaseStorage,
        strategy: FSMStrategy = FSMStrategy.USER_IN_CHAT,
        context: MutableMapping[str, Any] | None = None,
        app: Any = None,
    ) -> None:
        self.router = router
        self.bot = bot
        self.storage = storage
        self.strategy = strategy
        self.context: MutableMapping[str, Any] = context if context is not None else {}
        self.app = app

    def fsm_context(self, scope: EventScope) -> FSMContext:
        chat_id = scope.chat_id or 0
        user_id = scope.user_id or chat_id
        key = self.strategy.build_key(self.bot.id, chat_id, user_id, scope.thread_id)
        return FSMContext(self.storage, key)

    async def build_context(self, update: Update, event: Any) -> dict[str, Any]:
        scope = EventScope.from_event(event)
        state = self.fsm_context(scope)
        return {
            **self.context,
            "bot": self.bot,
            "app": self.app,
            "update": update,
            "event_type": update.event_type,
            "state": state,
            "raw_state": await state.get_state(),
            "chat_id": scope.chat_id,
            "user_id": scope.user_id,
            "thread_id": scope.thread_id,
        }

    async def feed_update(self, update: Update) -> bool:
        """UZ: Update'ni qayta ishlaydi; mos handler topilsa `True`.
        RU: Обрабатывает update; возвращает `True`, если нашёлся handler.
        EN: Processes an update; returns `True` when a handler handled it.
        """
        event_type, event = update.event_type, update.event
        if event_type is None or event is None:
            log.debug("Unsupported update: %s", sorted(update.raw))
            return False
        data = await self.build_context(update, event)
        try:
            return await self.router.trigger(event_type, event, data)
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            await self._handle_error(event_type, event, exception, data)
            return False

    async def feed_raw_update(self, payload: Mapping[str, Any]) -> bool:
        return await self.feed_update(Update(payload, self.bot))

    async def _handle_error(
        self, event_type: str, event: Any, exception: Exception, data: dict[str, Any]
    ) -> None:
        try:
            handled = await self.router.handle_error(event, exception, data)
        except Exception:
            log.exception("Error handler failed while handling %s", event_type)
            handled = False
        if not handled:
            log.error("Unhandled error in %s handler", event_type, exc_info=exception)


__all__ = ["Dispatcher", "EventScope"]
