"""UZ: Handler obyektlari va argument in'ektsiyasi (dependency injection).
RU: Объекты handler и внедрение аргументов (dependency injection).
EN: Handler objects and argument injection (dependency injection).

UZ: Handler faqat o'zi so'ragan argumentlarni oladi: imzo ro'yxatga olishda bir
marta tahlil qilinadi.
RU: Handler получает только запрошенные аргументы: сигнатура анализируется один раз
при регистрации.
EN: A handler receives only the arguments it asks for; its signature is analysed once
at registration time.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .filters import CompiledFilter, compile_filter


class CallableSpec:
    """UZ: Chaqiriluvchi obyektning oldindan hisoblangan imzosi.
    RU: Заранее вычисленная сигнатура вызываемого объекта.
    EN: The precomputed signature of a callable.

    UZ: `positional` — kontekstdan emas, to'g'ridan-to'g'ri uzatiladigan pozitsion
    argumentlar soni (handler uchun 1 — event).
    RU: `positional` — число позиционных аргументов, передаваемых напрямую, а не из
    контекста (для handler это 1 — событие).
    EN: `positional` is the number of leading positional arguments passed directly
    rather than from the context (1 for handlers — the event).
    """

    __slots__ = ("accepts_any", "callback", "parameters")

    def __init__(self, callback: Callable[..., Any], *, positional: int = 1) -> None:
        self.callback = callback
        parameters = list(inspect.signature(callback).parameters.values())
        self.accepts_any = any(p.kind is p.VAR_KEYWORD for p in parameters)
        self.parameters = tuple(
            p.name
            for p in parameters[positional:]
            if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
        )

    def select(self, context: Mapping[str, Any]) -> dict[str, Any]:
        if self.accepts_any:
            return dict(context)
        return {name: context[name] for name in self.parameters if name in context}

    async def __call__(self, *args: Any, context: Mapping[str, Any]) -> Any:
        result = self.callback(*args, **self.select(context))
        if inspect.isawaitable(result):
            result = await result
        return result


class Handler:
    """UZ: Callback + filtrlar + bayroqlar (flags).
    RU: Callback + фильтры + флаги (flags).
    EN: A callback plus its filters and flags.
    """

    __slots__ = ("callback", "filters", "flags", "spec")

    def __init__(
        self,
        callback: Callable[..., Any],
        filters: Iterable[Any] = (),
        flags: Mapping[str, Any] | None = None,
    ) -> None:
        self.callback = callback
        self.spec = CallableSpec(callback)
        self.filters: tuple[CompiledFilter, ...] = tuple(compile_filter(f) for f in filters)
        self.flags: dict[str, Any] = dict(flags or {})

    @property
    def name(self) -> str:
        return getattr(self.callback, "__name__", repr(self.callback))

    async def check(self, event: Any, data: Mapping[str, Any]) -> dict[str, Any] | None:
        """UZ: Barcha filtrlar mos kelsa qo'shimcha argumentlarni, aks holda `None`.
        RU: Если все фильтры подходят — дополнительные аргументы, иначе `None`.
        EN: Returns the extra arguments when every filter matches, otherwise `None`.
        """
        extra: dict[str, Any] = {}
        for item in self.filters:
            matched, result = await item.check(event, {**data, **extra})
            if not matched:
                return None
            extra.update(result)
        return extra

    async def call(self, event: Any, data: Mapping[str, Any]) -> Any:
        return await self.spec(event, context=data)

    def __repr__(self) -> str:
        return f"<Handler {self.name}>"


__all__ = ["CallableSpec", "Handler"]
