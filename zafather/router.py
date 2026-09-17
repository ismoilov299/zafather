"""UZ: Zafather — Router (handlerlarni guruhlash va yo'naltirish).
RU: Zafather — Router (группировка и маршрутизация handlers).
EN: Zafather — Router (grouping and routing handlers).
"""
from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

from .enums import UpdateType
from .filters import Command, ContentType, Service, StateFilter, Text, check_filter

log = logging.getLogger("zafather.router")


class _Unset:
    """UZ: `state` ko'rsatilmaganini bildiruvchi sentinel (state=None dan farqli).
    RU: Sentinel, обозначающий, что `state` не указан (отличается от `state=None`).
    EN: Sentinel meaning `state` was not specified (distinct from `state=None`).
    """

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = _Unset()

EVENTS = UpdateType.ALL

_sig_cache: Dict[int, Any] = {}


async def call_handler(callback: Callable, event, data: dict):
    """UZ: Handler faqat o'zi so'ragan argumentlarni oladi.
    RU: Handler получает только те аргументы, которые ему нужны.
    EN: The handler receives only the arguments it needs.
    """
    key = id(callback)
    info = _sig_cache.get(key)
    if info is None:
        params = inspect.signature(callback).parameters
        names = list(params)[1:]
        var_kw = any(p.kind == p.VAR_KEYWORD for p in params.values())
        info = (names, var_kw)
        _sig_cache[key] = info
    names, var_kw = info
    kwargs = dict(data) if var_kw else {n: data[n] for n in names if n in data}
    result = callback(event, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result


class Handler:
    __slots__ = ("callback", "filters", "flags", "name")

    def __init__(self, callback: Callable, filters: tuple, flags: dict):
        self.callback = callback
        self.filters = filters
        self.flags = flags
        self.name = getattr(callback, "__name__", repr(callback))

    async def check(self, event, data: dict) -> tuple[bool, dict]:
        extra: dict = {}
        for f in self.filters:
            ok, result = await check_filter(f, event, data)
            if not ok:
                return False, {}
            extra.update(result)
        return True, extra

    def __repr__(self) -> str:
        return f"<Handler {self.name}>"


class SkipHandler(Exception):
    """UZ: Handler ichida ko'tarilsa — keyingi handlerga o'tiladi.
    RU: Если выброшено внутри handler, управление переходит к следующему handler.
    EN: If raised inside a handler, execution skips to the next handler.
    """


class Router:
    """UZ: Handlerlar to'plami. Modul bo'yicha ajratish uchun ishlatiladi.
    RU: Набор handlers. Используется для разделения по модулям.
    EN: A collection of handlers. Used to split logic by module.
    """

    def __init__(self, name: str = "router") -> None:
        self.name = name
        self.handlers: Dict[str, List[Handler]] = {e: [] for e in EVENTS}
        self.middlewares: List[Callable] = []
        self.sub_routers: List["Router"] = []
        self.error_handlers: List[Handler] = []
        self.parent: Optional["Router"] = None

    # --- ro'yxatga olish ------------------------------------------------------
    def on(self, event: str, *filters, **flags) -> Callable:
        """Ixtiyoriy event turi uchun handler."""
        if event not in self.handlers:
            raise ValueError(
                f"Noma'lum event: {event!r}. Mumkin bo'lganlar: {', '.join(EVENTS)}"
            )

        def decorator(func: Callable) -> Callable:
            self.handlers[event].append(Handler(func, filters, flags))
            return func

        return decorator

    def message(self, *filters, state=UNSET, **flags) -> Callable:
        if state is not UNSET:
            filters = filters + (StateFilter(state),)
        return self.on("message", *filters, **flags)

    def edited_message(self, *filters, **flags) -> Callable:
        return self.on("edited_message", *filters, **flags)

    def channel_post(self, *filters, **flags) -> Callable:
        return self.on("channel_post", *filters, **flags)

    def command(self, *names: str, state=UNSET, prefix: str = "/", **flags) -> Callable:
        filters: tuple = (Command(*names, prefix=prefix),)
        if state is not UNSET:
            filters += (StateFilter(state),)
        return self.on("message", *filters, **flags)

    def text(self, *values: str, state=UNSET, **flags) -> Callable:
        filters: tuple = (Text(equals=list(values)),) if values else (Text(),)
        if state is not UNSET:
            filters += (StateFilter(state),)
        return self.on("message", *filters, **flags)

    def callback(self, *filters, state=UNSET, **flags) -> Callable:
        if state is not UNSET:
            filters = filters + (StateFilter(state),)
        return self.on("callback_query", *filters, **flags)

    def content(self, *types: str, state=UNSET, **flags) -> Callable:
        filters: tuple = (ContentType(*types),)
        if state is not UNSET:
            filters += (StateFilter(state),)
        return self.on("message", *filters, **flags)

    def inline(self, *filters, **flags) -> Callable:
        return self.on("inline_query", *filters, **flags)

    def service(self, *fields: str, **flags) -> Callable:
        """Xizmat xabarlari: managed_bot_created, community_chat_added, gift ..."""
        return self.on("message", Service(*fields), **flags)

    # --- Bot API 9.6+ / 10.x update turlari -----------------------------------
    def managed_bot(self, *filters, **flags) -> Callable:
        """Bot yaratildi yoki tokeni almashtirildi (Bot API 9.6+)."""
        return self.on(UpdateType.MANAGED_BOT, *filters, **flags)

    def guest(self, *filters, **flags) -> Callable:
        """Guest mode: bot a'zo bo'lmagan chatdagi xabar (Bot API 10.0+)."""
        return self.on(UpdateType.GUEST_MESSAGE, *filters, **flags)

    def subscription(self, *filters, **flags) -> Callable:
        """Foydalanuvchi obunasi o'zgardi (Bot API 10.2+)."""
        return self.on(UpdateType.SUBSCRIPTION, *filters, **flags)

    def stopped_generation(self, *filters, **flags) -> Callable:
        """UZ: `stopped_message_generation` update'i uchun handler ro'yxatga oladi.
        RU: Регистрирует handler для update `stopped_message_generation`.
        EN: Registers a handler for the `stopped_message_generation` update.
        """
        return self.on(UpdateType.STOPPED_MESSAGE_GENERATION, *filters, **flags)

    def business_message(self, *filters, **flags) -> Callable:
        return self.on(UpdateType.BUSINESS_MESSAGE, *filters, **flags)

    def business_connection(self, *filters, **flags) -> Callable:
        return self.on(UpdateType.BUSINESS_CONNECTION, *filters, **flags)

    def reaction(self, *filters, **flags) -> Callable:
        """Xabarga reaksiya qo'yildi/olib tashlandi."""
        return self.on(UpdateType.MESSAGE_REACTION, *filters, **flags)

    def poll_answer(self, *filters, **flags) -> Callable:
        return self.on(UpdateType.POLL_ANSWER, *filters, **flags)

    def pre_checkout(self, *filters, **flags) -> Callable:
        return self.on(UpdateType.PRE_CHECKOUT_QUERY, *filters, **flags)

    def paid_media(self, *filters, **flags) -> Callable:
        return self.on(UpdateType.PURCHASED_PAID_MEDIA, *filters, **flags)

    def chat_member(self, *filters, **flags) -> Callable:
        return self.on(UpdateType.CHAT_MEMBER, *filters, **flags)

    def my_chat_member(self, *filters, **flags) -> Callable:
        return self.on(UpdateType.MY_CHAT_MEMBER, *filters, **flags)

    def join_request(self, *filters, **flags) -> Callable:
        return self.on(UpdateType.CHAT_JOIN_REQUEST, *filters, **flags)

    def boost(self, *filters, **flags) -> Callable:
        return self.on(UpdateType.CHAT_BOOST, *filters, **flags)

    def middleware(self, func: Callable) -> Callable:
        """`async def mw(event, data, next_)` ko'rinishidagi middleware."""
        self.middlewares.append(func)
        return func

    def errors(self, func: Callable) -> Callable:
        """Xatolarni ushlovchi handler: `async def h(event, exception)`."""
        self.error_handlers.append(Handler(func, (), {}))
        return func

    def include(self, *routers: "Router") -> "Router":
        for router in routers:
            if router is self:
                raise ValueError("Router o'zini o'ziga qo'sha olmaydi")
            router.parent = self
            self.sub_routers.append(router)
        return self

    # --- yo'naltirish ---------------------------------------------------------
    async def _propagate(self, event_type: str, event, data: dict) -> bool:
        for handler in self.handlers.get(event_type, ()):
            ok, extra = await handler.check(event, data)
            if not ok:
                continue
            merged = {**data, **extra, "handler": handler}
            try:
                await call_handler(handler.callback, event, merged)
            except SkipHandler:
                continue
            return True
        for router in self.sub_routers:
            if await router.trigger(event_type, event, data):
                return True
        return False

    async def trigger(self, event_type: str, event, data: dict) -> bool:
        async def base(ev, d):
            return await self._propagate(event_type, ev, d)

        handler = base
        for mw in reversed(self.middlewares):
            handler = self._wrap(mw, handler)
        return bool(await handler(event, data))

    @staticmethod
    def _wrap(mw: Callable, next_: Callable) -> Callable:
        async def wrapper(event, data):
            return await mw(event, data, next_)

        return wrapper

    async def handle_error(self, event, exception: Exception, data: dict) -> bool:
        for handler in self.error_handlers:
            merged = {**data, "exception": exception}
            await call_handler(handler.callback, event, merged)
            return True
        for router in self.sub_routers:
            if await router.handle_error(event, exception, data):
                return True
        return False

    def __repr__(self) -> str:
        total = sum(len(v) for v in self.handlers.values())
        return f"<Router {self.name} handlers={total} sub={len(self.sub_routers)}>"
