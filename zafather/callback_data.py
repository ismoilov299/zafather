"""UZ: Tiplangan `CallbackData` fabrikasi.
RU: Типизированная фабрика `CallbackData`.
EN: A typed `CallbackData` factory.

UZ: Misol / RU: Пример / EN: Example::

    class Action(CallbackData, prefix="act"):
        name: str
        item_id: int
        confirm: bool = False

    kb = InlineKeyboard().add("O'chirish", Action(name="delete", item_id=42).pack())

    @router.callback(Action.filter(F.name == "delete"))
    async def delete(query: CallbackQuery, callback_data: Action):
        await query.answer(f"#{callback_data.item_id} o'chirildi")
"""

from __future__ import annotations

import inspect
import typing
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import UnionType
from typing import Any, ClassVar, TypeVar

from .filters import Filter, FilterResult
from .keyboards import MAX_CALLBACK_DATA_BYTES

CallbackDataT = TypeVar("CallbackDataT", bound="CallbackData")

_MISSING: Any = object()


@dataclass(frozen=True)
class _Field:
    name: str
    annotation: Any
    default: Any = _MISSING

    @property
    def required(self) -> bool:
        return self.default is _MISSING


def _optional_inner(annotation: Any) -> Any | None:
    origin = typing.get_origin(annotation)
    if origin is typing.Union or origin is UnionType:
        args = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(args) == 1 and len(typing.get_args(annotation)) == 2:
            return args[0]
    return None


def _encode(annotation: Any, value: Any, separator: str) -> str:
    inner = _optional_inner(annotation)
    if inner is not None:
        return "" if value is None else _encode(inner, value, separator)
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Enum):
        value = value.value
    text = str(value)
    if separator in text:
        raise ValueError(f"Value {text!r} must not contain the separator {separator!r}")
    return text


def _decode(annotation: Any, raw: str) -> Any:
    inner = _optional_inner(annotation)
    if inner is not None:
        return None if raw == "" else _decode(inner, raw)
    if annotation is bool:
        if raw not in ("0", "1"):
            raise ValueError(f"Invalid boolean value {raw!r}")
        return raw == "1"
    if annotation in (int, float, str):
        return annotation(raw)
    if annotation is uuid.UUID:
        return uuid.UUID(raw)
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        for member in annotation:
            if str(member.value) == raw:
                return member
        raise ValueError(f"{raw!r} is not a valid {annotation.__name__}")
    return raw


class CallbackData:
    """UZ: Callback data'ni `prefix:qiymat1:qiymat2` ko'rinishida yig'adi va ochadi.
    RU: Собирает и разбирает callback data в виде `prefix:значение1:значение2`.
    EN: Packs and unpacks callback data as `prefix:value1:value2`.

    UZ: Maydonlar annotatsiyalardan olinadi (`str`, `int`, `float`, `bool`, `Enum`,
    `UUID` va ularning `Optional` varianti). Natija 64 baytdan oshsa `ValueError`.
    RU: Поля берутся из аннотаций (`str`, `int`, `float`, `bool`, `Enum`, `UUID` и их
    `Optional`). Если результат длиннее 64 байт — `ValueError`.
    EN: Fields come from annotations (`str`, `int`, `float`, `bool`, `Enum`, `UUID` and
    their `Optional` forms). A result longer than 64 bytes raises `ValueError`.
    """

    __prefix__: ClassVar[str] = ""
    __separator__: ClassVar[str] = ":"
    __callback_fields__: ClassVar[tuple[_Field, ...]] = ()

    def __init_subclass__(cls, prefix: str = "", separator: str = ":", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        prefix = prefix or cls.__prefix__
        if not prefix:
            raise TypeError(
                f"{cls.__name__} needs a prefix: class {cls.__name__}(CallbackData, prefix='...')"
            )
        if not separator or separator in prefix:
            raise ValueError("The separator must be non-empty and must not occur in the prefix")
        cls.__prefix__ = prefix
        cls.__separator__ = separator
        cls.__callback_fields__ = tuple(_collect_fields(cls))

    def __init__(self, **values: Any) -> None:
        fields = type(self).__callback_fields__
        unknown = set(values) - {field.name for field in fields}
        if unknown:
            raise TypeError(f"Unknown fields for {type(self).__name__}: {sorted(unknown)}")
        for field in fields:
            if field.name in values:
                value = values[field.name]
            elif not field.required:
                value = field.default
            else:
                raise TypeError(f"{type(self).__name__} is missing the field {field.name!r}")
            setattr(self, field.name, value)

    def pack(self) -> str:
        """UZ: Callback data satrini yasaydi. RU: Собирает строку callback data.
        EN: Builds the callback data string.
        """
        cls = type(self)
        parts = [cls.__prefix__]
        parts.extend(
            _encode(field.annotation, getattr(self, field.name), cls.__separator__)
            for field in cls.__callback_fields__
        )
        packed = cls.__separator__.join(parts)
        size = len(packed.encode("utf-8"))
        if size > MAX_CALLBACK_DATA_BYTES:
            raise ValueError(f"Packed callback data is {size} bytes; Telegram allows at most 64")
        return packed

    @classmethod
    def unpack(cls: type[CallbackDataT], value: str) -> CallbackDataT:
        """UZ: Satrni obyektga aylantiradi; prefiks mos kelmasa `ValueError`.
        RU: Превращает строку в объект; при чужом префиксе — `ValueError`.
        EN: Parses a string into an object; a foreign prefix raises `ValueError`.
        """
        prefix, *raw_values = value.split(cls.__separator__)
        fields = cls.__callback_fields__
        if prefix != cls.__prefix__:
            raise ValueError(f"Callback data {value!r} does not belong to {cls.__name__}")
        if len(raw_values) != len(fields):
            raise ValueError(f"Callback data {value!r} has a wrong number of fields")
        return cls(
            **{
                field.name: _decode(field.annotation, raw)
                for field, raw in zip(fields, raw_values, strict=True)
            }
        )

    @classmethod
    def filter(cls, rule: Callable[[Any], Any] | None = None) -> CallbackDataFilter:
        """UZ: Callback filtri; mos kelsa handlerga `callback_data` obyekti keladi.
        RU: Фильтр callback; при совпадении в handler передаётся объект `callback_data`.
        EN: A callback filter; on match the handler receives the `callback_data` object.
        """
        return CallbackDataFilter(cls, rule)

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return all(
            getattr(self, field.name) == getattr(other, field.name)
            for field in type(self).__callback_fields__
        )

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        values = ", ".join(
            f"{field.name}={getattr(self, field.name)!r}"
            for field in type(self).__callback_fields__
        )
        return f"{type(self).__name__}({values})"


_BUILTIN_TYPES = {"int": int, "str": str, "float": float, "bool": bool}


def _type_hints(cls: type[CallbackData]) -> dict[str, Any]:
    try:
        return typing.get_type_hints(cls)
    except (NameError, TypeError):
        raw: dict[str, Any] = {}
        for klass in reversed(cls.__mro__):
            raw.update(vars(klass).get("__annotations__", {}))
        return {name: _BUILTIN_TYPES.get(hint, hint) for name, hint in raw.items()}


def _collect_fields(cls: type[CallbackData]) -> list[_Field]:
    hints = _type_hints(cls)
    names: list[str] = []
    for klass in reversed(cls.__mro__):
        for name in vars(klass).get("__annotations__", {}):
            if name not in names and not name.startswith("_"):
                names.append(name)
    fields = []
    for name in names:
        annotation = hints.get(name)
        if typing.get_origin(annotation) is ClassVar:
            continue
        fields.append(_Field(name, annotation, getattr(cls, name, _MISSING)))
    return fields


class CallbackDataFilter(Filter):
    """UZ: `CallbackData.filter()` natijasi. RU: Результат `CallbackData.filter()`.
    EN: The result of `CallbackData.filter()`.
    """

    def __init__(
        self, factory: type[CallbackData], rule: Callable[[Any], Any] | None = None
    ) -> None:
        self.factory = factory
        self.rule = rule

    async def __call__(self, event: Any, data: Mapping[str, Any] | None = None) -> FilterResult:
        raw = event.get("data") if isinstance(event, Mapping) else getattr(event, "data", None)
        if not isinstance(raw, str):
            return False
        try:
            callback_data = self.factory.unpack(raw)
        except (ValueError, TypeError):
            return False
        if self.rule is not None:
            matched = self.rule(callback_data)
            if inspect.isawaitable(matched):
                matched = await matched
            if not matched:
                return False
        return {"callback_data": callback_data}


__all__ = ["CallbackData", "CallbackDataFilter"]
