"""UZ: Zafather — `F` sehrli filtri.
RU: Zafather — магический фильтр `F`.
EN: Zafather — the magic `F` filter.

UZ: Misollar / RU: Примеры / EN: Examples::

    F.text                       # matn bor / есть текст / has text
    F.data == "menu"             # callback data teng / равна / equals
    F.text.startswith("/")
    F.chat.type == "private"
    F.photo | F.video
    ~F.text
    F.text.func(str.isdigit)
    F.text.len() > 3
    F.text.as_("name")           # handlerga `name` argumenti / аргумент `name` / injects `name`
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .filters import AndFilter, OrFilter

Resolver = Callable[[Any], Any]


def _identity(value: Any) -> Any:
    return value


def _safe(resolver: Resolver) -> Resolver:
    def resolve(value: Any) -> Any:
        try:
            return resolver(value)
        except (TypeError, ValueError, AttributeError):
            return None

    return resolve


class Magic:
    """UZ: Atribut zanjirini dangasa (lazy) yig'ib, filtrga aylantiradi.
    RU: Лениво собирает цепочку атрибутов и превращает её в фильтр.
    EN: Lazily builds an attribute chain and turns it into a filter.
    """

    __slots__ = ("_repr", "_resolve")

    def __init__(self, resolve: Resolver | None = None, repr_: str = "F") -> None:
        self._resolve: Resolver = resolve or _identity
        self._repr = repr_

    def resolve(self, event: Any) -> Any:
        """UZ: Zanjir qiymatini hisoblaydi. RU: Вычисляет значение цепочки.
        EN: Evaluates the chain for an event.
        """
        return self._resolve(event)

    # --- UZ: zanjir / RU: цепочка / EN: chain ------------------------------------------------
    def __getattr__(self, item: str) -> Magic:
        if item.startswith("_"):
            raise AttributeError(item)
        previous = self._resolve

        def resolve(event: Any) -> Any:
            value = previous(event)
            return None if value is None else getattr(value, item, None)

        return Magic(resolve, f"{self._repr}.{item}")

    def __getitem__(self, item: Any) -> Magic:
        previous = self._resolve

        def resolve(event: Any) -> Any:
            value = previous(event)
            try:
                return value[item]
            except (TypeError, KeyError, IndexError):
                return None

        return Magic(resolve, f"{self._repr}[{item!r}]")

    def _then(self, function: Resolver, label: str) -> Magic:
        previous = self._resolve
        guarded = _safe(function)
        return Magic(lambda event: guarded(previous(event)), f"{self._repr}{label}")

    # --- UZ: taqqoslash / RU: сравнение / EN: comparison -----------------------------------
    def __eq__(self, other: object) -> Magic:  # type: ignore[override]
        return self._then(lambda value: value == other, f" == {other!r}")

    def __ne__(self, other: object) -> Magic:  # type: ignore[override]
        return self._then(lambda value: value != other, f" != {other!r}")

    def __lt__(self, other: Any) -> Magic:
        return self._then(lambda value: value is not None and value < other, f" < {other!r}")

    def __le__(self, other: Any) -> Magic:
        return self._then(lambda value: value is not None and value <= other, f" <= {other!r}")

    def __gt__(self, other: Any) -> Magic:
        return self._then(lambda value: value is not None and value > other, f" > {other!r}")

    def __ge__(self, other: Any) -> Magic:
        return self._then(lambda value: value is not None and value >= other, f" >= {other!r}")

    __hash__ = object.__hash__

    # --- UZ: mantiq / RU: логика / EN: logic -------------------------------------------------
    def __and__(self, other: Any) -> Any:
        if isinstance(other, Magic):
            return Magic(
                lambda event: bool(self._resolve(event)) and bool(other._resolve(event)),
                f"({self._repr} & {other._repr})",
            )
        return AndFilter(self, other)

    def __rand__(self, other: Any) -> Any:
        return AndFilter(other, self)

    def __or__(self, other: Any) -> Any:
        if isinstance(other, Magic):
            return Magic(
                lambda event: bool(self._resolve(event)) or bool(other._resolve(event)),
                f"({self._repr} | {other._repr})",
            )
        return OrFilter(self, other)

    def __ror__(self, other: Any) -> Any:
        return OrFilter(other, self)

    def __invert__(self) -> Magic:
        return Magic(lambda event: not bool(self._resolve(event)), f"~{self._repr}")

    # --- UZ: yordamchilar / RU: помощники / EN: helpers -------------------------------------
    def in_(self, values: Iterable[Any]) -> Magic:
        collection = list(values)
        return self._then(lambda value: value in collection, f".in_({collection!r})")

    def contains(self, item: Any) -> Magic:
        return self._then(lambda value: value is not None and item in value, f".contains({item!r})")

    def startswith(self, prefix: str) -> Magic:
        return self._then(
            lambda value: isinstance(value, str) and value.startswith(prefix),
            f".startswith({prefix!r})",
        )

    def endswith(self, suffix: str) -> Magic:
        return self._then(
            lambda value: isinstance(value, str) and value.endswith(suffix),
            f".endswith({suffix!r})",
        )

    def lower(self) -> Magic:
        return self._then(
            lambda value: value.lower() if isinstance(value, str) else value, ".lower()"
        )

    def upper(self) -> Magic:
        return self._then(
            lambda value: value.upper() if isinstance(value, str) else value, ".upper()"
        )

    def len(self) -> Magic:
        return self._then(lambda value: None if value is None else len(value), ".len()")

    def regexp(self, pattern: str | re.Pattern[str], flags: int = 0) -> Magic:
        compiled = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
        return self._then(
            lambda value: compiled.search(value) if isinstance(value, str) else None,
            f".regexp({compiled.pattern!r})",
        )

    def func(self, function: Callable[[Any], Any]) -> Magic:
        return self._then(
            lambda value: bool(function(value)) if value is not None else False, ".func(...)"
        )

    def is_none(self) -> Magic:
        return self._then(lambda value: value is None, ".is_none()")

    def is_not_none(self) -> Magic:
        return self._then(lambda value: value is not None, ".is_not_none()")

    def as_(self, name: str) -> MagicAs:
        """UZ: Qiymat bo'sh bo'lmasa, handlerga `name` argumenti sifatida uzatiladi.
        RU: Если значение непустое, оно передаётся в handler как аргумент `name`.
        EN: When the value is truthy it is injected into the handler as `name`.
        """
        return MagicAs(self, name)

    # --- UZ: filtr sifatida / RU: как фильтр / EN: as a filter ----------------------------
    def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> bool:
        return bool(self._resolve(event))

    def __repr__(self) -> str:
        return self._repr


class MagicAs:
    """UZ: `F...as_(name)` natijasi. RU: Результат `F...as_(name)`.
    EN: The result of `F...as_(name)`.
    """

    __slots__ = ("magic", "name")

    def __init__(self, magic: Magic, name: str) -> None:
        self.magic = magic
        self.name = name

    def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> Any:
        value = self.magic.resolve(event)
        return {self.name: value} if value else False

    def __repr__(self) -> str:
        return f"{self.magic!r}.as_({self.name!r})"


#: UZ: Global sehrli filtr. RU: Глобальный магический фильтр. EN: The global magic filter.
F = Magic()

__all__ = ["F", "Magic", "MagicAs"]
