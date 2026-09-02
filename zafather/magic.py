"""Zafather — `F` sehrli filtri.

    F.text                      -> event.text mavjud va bo'sh emas
    F.data == "menu"            -> callback data teng
    F.text.startswith("/")      -> matn shu bilan boshlanadi
    F.chat.type == "private"    -> shaxsiy chat
    F.photo | F.video           -> yoki
    ~F.text                     -> inkor
    F.text.func(str.isdigit)    -> ixtiyoriy funksiya
"""
from __future__ import annotations

import re
from typing import Any, Callable, Iterable


class Magic:
    """Atribut zanjirini lazy tarzda yig'ib, filtrga aylantiradi."""

    __slots__ = ("_resolve", "_repr")

    def __init__(self, resolve: Callable[[Any], Any] = None, repr_: str = "F"):
        self._resolve = resolve or (lambda obj: obj)
        self._repr = repr_

    # --- zanjir ---------------------------------------------------------------
    def __getattr__(self, item: str) -> "Magic":
        if item.startswith("_"):
            raise AttributeError(item)
        prev = self._resolve

        def resolve(obj):
            value = prev(obj)
            return getattr(value, item, None) if value is not None else None

        return Magic(resolve, f"{self._repr}.{item}")

    def __getitem__(self, item) -> "Magic":
        prev = self._resolve

        def resolve(obj):
            value = prev(obj)
            try:
                return value[item]
            except (TypeError, KeyError, IndexError):
                return None

        return Magic(resolve, f"{self._repr}[{item!r}]")

    def _make(self, fn: Callable[[Any], Any], label: str) -> "Magic":
        prev = self._resolve
        return Magic(lambda obj: fn(prev(obj)), f"{self._repr}{label}")

    # --- taqqoslashlar --------------------------------------------------------
    def __eq__(self, other) -> "Magic":  # type: ignore[override]
        return self._make(lambda v: v == other, f" == {other!r}")

    def __ne__(self, other) -> "Magic":  # type: ignore[override]
        return self._make(lambda v: v != other, f" != {other!r}")

    def __lt__(self, other) -> "Magic":
        return self._make(lambda v: v is not None and v < other, f" < {other!r}")

    def __le__(self, other) -> "Magic":
        return self._make(lambda v: v is not None and v <= other, f" <= {other!r}")

    def __gt__(self, other) -> "Magic":
        return self._make(lambda v: v is not None and v > other, f" > {other!r}")

    def __ge__(self, other) -> "Magic":
        return self._make(lambda v: v is not None and v >= other, f" >= {other!r}")

    __hash__ = object.__hash__

    # --- mantiqiy amallar -----------------------------------------------------
    def __and__(self, other) -> "Magic":
        return Magic(
            lambda obj: bool(self._resolve(obj)) and bool(_call(other, obj)),
            f"({self._repr} & {other!r})",
        )

    def __or__(self, other) -> "Magic":
        return Magic(
            lambda obj: bool(self._resolve(obj)) or bool(_call(other, obj)),
            f"({self._repr} | {other!r})",
        )

    def __invert__(self) -> "Magic":
        return Magic(lambda obj: not bool(self._resolve(obj)), f"~{self._repr}")

    # --- yordamchilar ---------------------------------------------------------
    def in_(self, values: Iterable) -> "Magic":
        collection = list(values)
        return self._make(lambda v: v in collection, f".in_({collection!r})")

    def contains(self, value) -> "Magic":
        return self._make(
            lambda v: v is not None and value in v, f".contains({value!r})"
        )

    def startswith(self, prefix: str) -> "Magic":
        return self._make(
            lambda v: isinstance(v, str) and v.startswith(prefix),
            f".startswith({prefix!r})",
        )

    def endswith(self, suffix: str) -> "Magic":
        return self._make(
            lambda v: isinstance(v, str) and v.endswith(suffix), f".endswith({suffix!r})"
        )

    def lower(self) -> "Magic":
        return self._make(lambda v: v.lower() if isinstance(v, str) else v, ".lower()")

    def regexp(self, pattern: str) -> "Magic":
        compiled = re.compile(pattern)
        return self._make(
            lambda v: bool(compiled.search(v)) if isinstance(v, str) else False,
            f".regexp({pattern!r})",
        )

    def func(self, fn: Callable[[Any], Any]) -> "Magic":
        return self._make(lambda v: bool(fn(v)) if v is not None else False, ".func(...)")

    def is_none(self) -> "Magic":
        return self._make(lambda v: v is None, ".is_none()")

    def is_not_none(self) -> "Magic":
        return self._make(lambda v: v is not None, ".is_not_none()")

    # --- filtr sifatida chaqirish --------------------------------------------
    def __call__(self, event, data: dict = None) -> bool:
        return bool(self._resolve(event))

    def __repr__(self) -> str:
        return self._repr


def _call(target, obj) -> Any:
    if isinstance(target, Magic):
        return target._resolve(obj)
    return target(obj)


#: Global sehrli filtr obyekti
F = Magic()
