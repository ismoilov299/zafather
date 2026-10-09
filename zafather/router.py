"""UZ: Zafather — Router: handlerlarni guruhlash va yo'naltirish.
RU: Zafather — Router: группировка и маршрутизация handlers.
EN: Zafather — Router: grouping and routing handlers.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from .enums import UpdateType
from .filters import Command, ContentType, Service, StateFilter, Text
from .handler import Handler

NextHandler = Callable[[Any, dict[str, Any]], Awaitable[Any]]
Middleware = Callable[[Any, dict[str, Any], NextHandler], Awaitable[Any]]
CallbackT = TypeVar("CallbackT", bound=Callable[..., Any])


class _Unset:
    """UZ: `state` berilmaganini bildiradi (`state=None` dan farqli).
    RU: Означает, что `state` не передан (в отличие от `state=None`).
    EN: Marks that `state` was not passed (unlike `state=None`).
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET: Any = _Unset()


class SkipHandler(Exception):
    """UZ: Handler ichida ko'tarilsa — keyingi mos handlerga o'tiladi.
    RU: Если выброшено в handler, управление переходит к следующему подходящему handler.
    EN: Raised inside a handler to pass the event to the next matching handler.
    """


def _with_state(filters: tuple[Any, ...], state: Any) -> tuple[Any, ...]:
    return filters if state is UNSET else (*filters, StateFilter(state))


def _chain(middleware: Middleware, next_handler: NextHandler) -> NextHandler:
    async def wrapped(event: Any, data: dict[str, Any]) -> Any:
        return await middleware(event, data, next_handler)

    return wrapped


class Router:
    """UZ: Handlerlar to'plami; modullarga bo'lish uchun ishlatiladi.
    RU: Набор handlers; используется для разделения кода по модулям.
    EN: A set of handlers used to split code into modules.

    UZ: `middleware()` — handler tanlanishidan oldin ishlaydi; `inner_middleware()` —
    filtrlar mos kelgandan keyin, handler chaqiruvidan oldin (`data["handler"].flags`
    o'qilishi mumkin).
    RU: `middleware()` выполняется до выбора handler; `inner_middleware()` — после
    совпадения фильтров, перед вызовом handler (доступны `data["handler"].flags`).
    EN: `middleware()` runs before handler selection; `inner_middleware()` runs after
    the filters matched and right before the handler (`data["handler"].flags` is
    available).
    """

    def __init__(self, name: str = "router") -> None:
        self.name = name
        self.handlers: dict[str, list[Handler]] = {event: [] for event in UpdateType.ALL}
        self.middlewares: list[Middleware] = []
        self.inner_middlewares: list[Middleware] = []
        self.sub_routers: list[Router] = []
        self.error_handlers: list[Handler] = []

    # --- UZ: ro'yxatga olish / RU: регистрация / EN: registration --------------------
    def register(
        self, event_type: str, callback: Callable[..., Any], *filters: Any, **flags: Any
    ) -> Handler:
        """UZ: Handlerni dekoratorsiz ro'yxatga oladi.
        RU: Регистрирует handler без декоратора.
        EN: Registers a handler without a decorator.
        """
        observers = self.handlers.get(event_type)
        if observers is None:
            known = ", ".join(UpdateType.ALL)
            raise ValueError(f"Unknown event type {event_type!r}; expected one of: {known}")
        handler = Handler(callback, filters, flags)
        observers.append(handler)
        return handler

    def on(self, event_type: str, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Istalgan update turi uchun dekorator.
        RU: Декоратор для любого типа update.
        EN: Decorator for any update type.
        """

        def decorator(callback: CallbackT) -> CallbackT:
            self.register(event_type, callback, *filters, **flags)
            return callback

        return decorator

    def message(
        self, *filters: Any, state: Any = UNSET, **flags: Any
    ) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.MESSAGE, *_with_state(filters, state), **flags)

    def command(
        self, *names: str, state: Any = UNSET, prefix: str = "/", **flags: Any
    ) -> Callable[[CallbackT], CallbackT]:
        filters = _with_state((Command(*names, prefix=prefix),), state)
        return self.on(UpdateType.MESSAGE, *filters, **flags)

    def text(
        self, *values: str, state: Any = UNSET, **flags: Any
    ) -> Callable[[CallbackT], CallbackT]:
        text_filter = Text(equals=list(values)) if values else Text()
        return self.on(UpdateType.MESSAGE, *_with_state((text_filter,), state), **flags)

    def content(
        self, *types: str, state: Any = UNSET, **flags: Any
    ) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.MESSAGE, *_with_state((ContentType(*types),), state), **flags)

    def service(self, *fields: str, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Xizmat xabarlari (managed_bot_created, gift ...).
        RU: Служебные сообщения (managed_bot_created, gift ...).
        EN: Service messages (managed_bot_created, gift ...).
        """
        return self.on(UpdateType.MESSAGE, Service(*fields), **flags)

    def callback(
        self, *filters: Any, state: Any = UNSET, **flags: Any
    ) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.CALLBACK_QUERY, *_with_state(filters, state), **flags)

    def edited_message(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.EDITED_MESSAGE, *filters, **flags)

    def channel_post(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.CHANNEL_POST, *filters, **flags)

    def edited_channel_post(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.EDITED_CHANNEL_POST, *filters, **flags)

    def inline(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.INLINE_QUERY, *filters, **flags)

    def chosen_inline_result(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.CHOSEN_INLINE_RESULT, *filters, **flags)

    def managed_bot(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Bot yaratildi yoki tokeni almashdi (9.6+).
        RU: Бот создан или его токен изменён (9.6+).
        EN: A bot was created or its token changed (9.6+).
        """
        return self.on(UpdateType.MANAGED_BOT, *filters, **flags)

    def guest(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Guest mode (10.0+). RU: Гостевой режим (10.0+). EN: Guest mode (10.0+)."""
        return self.on(UpdateType.GUEST_MESSAGE, *filters, **flags)

    def subscription(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Obuna o'zgardi (10.2+). RU: Изменилась подписка (10.2+).
        EN: A subscription changed (10.2+).
        """
        return self.on(UpdateType.SUBSCRIPTION, *filters, **flags)

    def stopped_generation(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Generatsiyani to'xtatish so'raldi (10.3).
        RU: Запрошена остановка генерации (10.3).
        EN: Stopping a generation was requested (10.3).
        """
        return self.on(UpdateType.STOPPED_MESSAGE_GENERATION, *filters, **flags)

    def business_connection(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.BUSINESS_CONNECTION, *filters, **flags)

    def business_message(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.BUSINESS_MESSAGE, *filters, **flags)

    def reaction(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.MESSAGE_REACTION, *filters, **flags)

    def poll(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.POLL, *filters, **flags)

    def poll_answer(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.POLL_ANSWER, *filters, **flags)

    def shipping_query(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.SHIPPING_QUERY, *filters, **flags)

    def pre_checkout(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.PRE_CHECKOUT_QUERY, *filters, **flags)

    def paid_media(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.PURCHASED_PAID_MEDIA, *filters, **flags)

    def chat_member(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.CHAT_MEMBER, *filters, **flags)

    def my_chat_member(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.MY_CHAT_MEMBER, *filters, **flags)

    def join_request(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.CHAT_JOIN_REQUEST, *filters, **flags)

    def boost(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.CHAT_BOOST, *filters, **flags)

    def removed_boost(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        return self.on(UpdateType.REMOVED_CHAT_BOOST, *filters, **flags)

    # --- UZ: middleware va xatolar / RU: middleware и ошибки / EN: middleware and errors --
    def middleware(self, middleware: Middleware) -> Middleware:
        """UZ: `async def mw(event, data, next_)` — handler tanlanishidan oldin.
        RU: `async def mw(event, data, next_)` — до выбора handler.
        EN: `async def mw(event, data, next_)` — runs before handler selection.
        """
        self.middlewares.append(middleware)
        return middleware

    def inner_middleware(self, middleware: Middleware) -> Middleware:
        """UZ: Filtrlar mos kelgandan keyin, handlerdan oldin ishlaydi.
        RU: Выполняется после совпадения фильтров, перед handler.
        EN: Runs after the filters matched, right before the handler.
        """
        self.inner_middlewares.append(middleware)
        return middleware

    def error(self, *filters: Any, **flags: Any) -> Callable[[CallbackT], CallbackT]:
        """UZ: Xato handleri (filtrlar bilan): `async def h(event, exception)`.
        RU: Обработчик ошибок (с фильтрами): `async def h(event, exception)`.
        EN: Error handler (with filters): `async def h(event, exception)`.
        """

        def decorator(callback: CallbackT) -> CallbackT:
            self.error_handlers.append(Handler(callback, filters, flags))
            return callback

        return decorator

    def errors(self, callback: CallbackT) -> CallbackT:
        """UZ: Filtrsiz xato handleri. RU: Обработчик ошибок без фильтров.
        EN: Error handler without filters.
        """
        return self.error()(callback)

    def include(self, *routers: Router) -> Router:
        """UZ: Ichki routerlarni ulaydi (tsikl hosil bo'lishiga yo'l qo'ymaydi).
        RU: Подключает вложенные routers (не допускает циклов).
        EN: Includes child routers (cycles are rejected).
        """
        for router in routers:
            if router is self or router.reaches(self):
                raise ValueError(f"Including {router!r} into {self!r} would create a cycle")
            self.sub_routers.append(router)
        return self

    def reaches(self, target: Router) -> bool:
        """UZ: `target` shu routerning ichida (har qanday chuqurlikda) bormi.
        RU: Есть ли `target` среди вложенных routers (на любой глубине).
        EN: Whether `target` is nested inside this router at any depth.
        """
        pending = list(self.sub_routers)
        seen: set[int] = set()
        while pending:
            router = pending.pop()
            if router is target:
                return True
            if id(router) not in seen:
                seen.add(id(router))
                pending.extend(router.sub_routers)
        return False

    # --- UZ: yo'naltirish / RU: маршрутизация / EN: routing --------------------------
    async def trigger(self, event_type: str, event: Any, data: dict[str, Any]) -> bool:
        """UZ: Eventni middleware'lar orqali handlerlarga uzatadi.
        RU: Передаёт событие через middleware в handlers.
        EN: Passes the event through the middlewares to the handlers.
        """

        async def propagate(current_event: Any, current_data: dict[str, Any]) -> bool:
            return await self._propagate(event_type, current_event, current_data)

        handler: NextHandler = propagate
        for middleware in reversed(self.middlewares):
            handler = _chain(middleware, handler)
        return bool(await handler(event, data))

    async def _propagate(self, event_type: str, event: Any, data: dict[str, Any]) -> bool:
        for handler in self.handlers.get(event_type, ()):
            extra = await handler.check(event, data)
            if extra is None:
                continue
            try:
                await self._call_handler(handler, event, {**data, **extra, "handler": handler})
            except SkipHandler:
                continue
            return True
        for router in self.sub_routers:
            if await router.trigger(event_type, event, data):
                return True
        return False

    async def _call_handler(self, handler: Handler, event: Any, data: dict[str, Any]) -> Any:
        call: NextHandler = handler.call
        for middleware in reversed(self.inner_middlewares):
            call = _chain(middleware, call)
        return await call(event, data)

    async def handle_error(self, event: Any, exception: Exception, data: dict[str, Any]) -> bool:
        """UZ: Xatoni mos xato handleriga uzatadi. RU: Передаёт ошибку обработчику ошибок.
        EN: Routes the exception to a matching error handler.
        """
        context = {**data, "exception": exception}
        for handler in self.error_handlers:
            extra = await handler.check(event, context)
            if extra is None:
                continue
            try:
                await handler.call(event, {**context, **extra})
            except SkipHandler:
                continue
            return True
        for router in self.sub_routers:
            if await router.handle_error(event, exception, data):
                return True
        return False

    def __repr__(self) -> str:
        total = sum(len(handlers) for handlers in self.handlers.values())
        routers = len(self.sub_routers)
        return f"<{type(self).__name__} {self.name!r} handlers={total} routers={routers}>"


__all__ = ["UNSET", "Middleware", "NextHandler", "Router", "SkipHandler"]
