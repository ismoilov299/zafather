"""UZ: Sxemaga asoslangan umumiy TL obyekti.
RU: Универсальный TL-объект на основе схемы.
EN: A generic, schema-driven TL object.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import TLDefinition


def _plain(value: Any) -> Any:
    if isinstance(value, TLObject):
        return value.to_dict()
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _short_repr(value: Any) -> str:
    if isinstance(value, bytes) and len(value) > 16:
        return f"<{len(value)} bytes>"
    return repr(value)


class TLObject:
    """UZ: TL konstruktori yoki funksiya chaqiruvi; maydonlar atribut orqali o'qiladi.
    RU: Конструктор TL или вызов функции; поля доступны как атрибуты.
    EN: A TL constructor or function call; fields are readable as attributes.

    UZ: Berilmagan ixtiyoriy maydon `None`, `true` bayroq esa `False` bo'ladi.
    RU: Непереданное необязательное поле равно `None`, флаг `true` — `False`.
    EN: A missing optional field reads as `None`, a `true` flag as `False`.
    """

    __slots__ = ("_definition", "_values")

    def __init__(
        self, definition: TLDefinition, values: Mapping[str, Any], *, validate: bool = True
    ) -> None:
        self._definition = definition
        self._values = dict(values)
        if validate:
            self._validate()

    def _validate(self) -> None:
        known = {param.name for param in self._definition.params if not param.is_flags_field}
        unknown = set(self._values) - known
        if unknown:
            raise TypeError(f"{self._definition.name} got unknown fields: {sorted(unknown)}")
        missing = [
            param.name
            for param in self._definition.params
            if param.required and self._values.get(param.name) is None
        ]
        if missing:
            raise TypeError(f"{self._definition.name} is missing required fields: {missing}")

    @property
    def definition(self) -> TLDefinition:
        return self._definition

    @property
    def tl_name(self) -> str:
        """UZ: TL nomi (`updateNewMessage`). RU: Имя TL. EN: The TL name."""
        return self._definition.name

    @property
    def tl_id(self) -> int:
        return self._definition.id

    @property
    def is_function(self) -> bool:
        return self._definition.is_function

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        param = self._definition.param(name)
        if param is None:
            raise AttributeError(f"{self._definition.name} has no field {name!r}")
        if param.is_true_flag:
            return bool(self._values.get(name, False))
        return self._values.get(name)

    def get(self, name: str, default: Any = None) -> Any:
        value = self._values.get(name)
        return default if value is None else value

    @property
    def values(self) -> dict[str, Any]:
        return self._values

    def to_dict(self) -> dict[str, Any]:
        """UZ: `{"_": nom, ...}` ko'rinishidagi lug'at. RU: Словарь вида `{"_": имя, ...}`.
        EN: A `{"_": name, ...}` dictionary.
        """
        return {"_": self._definition.name, **{k: _plain(v) for k, v in self._values.items()}}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TLObject):
            return NotImplemented
        return self._definition.id == other._definition.id and self._values == other._values

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        fields = ", ".join(f"{key}={_short_repr(value)}" for key, value in self._values.items())
        return f"{self._definition.name}({fields})"


class TLConstructor:
    """UZ: Muayyan ta'rif bo'yicha `TLObject` yasaydigan chaqiriluvchi obyekt.
    RU: Вызываемый объект, создающий `TLObject` по определению.
    EN: A callable that creates `TLObject`s for one definition.

        functions.messages.sendMessage(peer=types.inputPeerSelf(), message="hi", random_id=1)
    """

    __slots__ = ("definition",)

    def __init__(self, definition: TLDefinition) -> None:
        self.definition = definition

    def __call__(self, /, **values: Any) -> TLObject:
        return TLObject(self.definition, values)

    @property
    def tl_id(self) -> int:
        return self.definition.id

    def __repr__(self) -> str:
        return f"<TLConstructor {self.definition}>"


__all__ = ["TLConstructor", "TLObject"]
