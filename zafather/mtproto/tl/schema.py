"""UZ: TL sxema parseri: `.tl` matnidan konstruktor va funksiya ta'riflarini o'qiydi.
RU: Парсер TL-схемы: читает определения конструкторов и функций из текста `.tl`.
EN: TL schema parser: reads constructor and function definitions from `.tl` text.
"""

from __future__ import annotations

import re
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

#: UZ: Ichki (bare) primitiv tiplar. RU: Встроенные примитивные типы.
#: EN: Built-in primitive types.
PRIMITIVES = frozenset(
    {"int", "long", "double", "string", "bytes", "int128", "int256", "true", "Bool", "#"}
)

_LAYER_RE = re.compile(r"^//\s*LAYER\s+(\d+)")


@dataclass(frozen=True)
class TLType:
    """UZ: Tipga havola: nom, generik argument (`Vector<T>`), bare/generik belgilari.
    RU: Ссылка на тип: имя, аргумент (`Vector<T>`), признаки bare/generic.
    EN: A type reference: name, argument (`Vector<T>`), bare and generic markers.
    """

    name: str
    argument: TLType | None = None
    bare: bool = False
    generic: bool = False

    @property
    def is_vector(self) -> bool:
        return self.name in ("Vector", "vector")

    @property
    def is_primitive(self) -> bool:
        return self.name in PRIMITIVES

    @property
    def is_bare_constructor(self) -> bool:
        """UZ: Kichik harfli konstruktor nomi (`future_salt`). RU: Конструктор со строчной буквы.
        EN: A lowercase constructor name such as `future_salt`.
        """
        short = self.name.rsplit(".", 1)[-1]
        return not self.is_primitive and not self.is_vector and short[:1].islower()

    def __str__(self) -> str:
        prefix = "!" if self.generic else ""
        if self.argument is not None:
            return f"{prefix}{self.name}<{self.argument}>"
        return prefix + self.name


@dataclass(frozen=True)
class TLParam:
    """UZ: Parametr; `flag` — (bayroq maydoni, bit) juftligi yoki `None`.
    RU: Параметр; `flag` — пара (поле флагов, бит) или `None`.
    EN: A parameter; `flag` is a (flags field, bit) pair or `None`.
    """

    name: str
    type: TLType
    flag: tuple[str, int] | None = None

    @property
    def is_flags_field(self) -> bool:
        return self.type.name == "#"

    @property
    def is_true_flag(self) -> bool:
        return self.flag is not None and self.type.name == "true"

    @property
    def required(self) -> bool:
        return self.flag is None and not self.is_flags_field


@dataclass(frozen=True)
class TLDefinition:
    """UZ: Konstruktor yoki funksiya ta'rifi. RU: Определение конструктора или функции.
    EN: A constructor or function definition.
    """

    name: str
    id: int
    params: tuple[TLParam, ...]
    result: TLType
    is_function: bool
    generic_args: tuple[str, ...] = ()

    @property
    def namespace(self) -> str | None:
        return self.name.rpartition(".")[0] or None

    def param(self, name: str) -> TLParam | None:
        return next((param for param in self.params if param.name == name), None)

    def __str__(self) -> str:
        parts = [f"{self.name}#{self.id:08x}"]
        parts.extend(f"{{{name}:Type}}" for name in self.generic_args)
        for param in self.params:
            condition = f"{param.flag[0]}.{param.flag[1]}?" if param.flag else ""
            parts.append(f"{param.name}:{condition}{param.type}")
        return " ".join(parts) + f" = {self.result};"


class TLSchemaError(ValueError):
    """UZ: Sxemani tahlil qilishdagi xato. RU: Ошибка разбора схемы. EN: A schema parsing error."""


def parse_type(text: str) -> TLType:
    """UZ: `Vector<long>`, `!X`, `%Type`, `flags` kabi tip yozuvini tahlil qiladi.
    RU: Разбирает запись типа: `Vector<long>`, `!X`, `%Type` и т.п.
    EN: Parses a type expression such as `Vector<long>`, `!X` or `%Type`.
    """
    generic = text.startswith("!")
    bare = text.startswith("%")
    text = text.lstrip("!%")
    if "<" in text:
        if not text.endswith(">"):
            raise TLSchemaError(f"Malformed type: {text!r}")
        outer, inner = text[:-1].split("<", 1)
        return TLType(outer, parse_type(inner), bare=outer == "vector", generic=generic)
    return TLType(text, bare=bare, generic=generic)


def _parse_param(token: str) -> TLParam:
    name, _, type_text = token.partition(":")
    if not name or not type_text:
        raise TLSchemaError(f"Malformed parameter: {token!r}")
    flag = None
    if "?" in type_text:
        condition, type_text = type_text.split("?", 1)
        field, _, bit = condition.partition(".")
        flag = (field, int(bit))
    return TLParam(name, parse_type(type_text), flag)


def constructor_id(definition_text: str) -> int:
    """UZ: Ta'rif matnidan CRC32 identifikatorini hisoblaydi (ID ko'rsatilmaganda).
    RU: Вычисляет CRC32-идентификатор по тексту определения (если ID не указан).
    EN: Computes the CRC32 identifier from definition text (when no ID is given).
    """
    text = re.sub(r"#[0-9a-fA-F]+", "", definition_text.strip().rstrip(";"))
    text = re.sub(r"\s\w+:\w+\.\d+\?true", "", text)
    text = text.replace(":bytes", ":string").replace("?bytes", "?string")
    text = text.replace("<", " ").replace(">", "").replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text).strip()
    return zlib.crc32(text.encode("ascii"))


def parse_definition(line: str, *, is_function: bool) -> TLDefinition:
    """UZ: Bitta ta'rif qatorini tahlil qiladi. RU: Разбирает одну строку определения.
    EN: Parses a single definition line.
    """
    body = line.strip().rstrip(";").strip()
    left, sep, result = body.rpartition("=")
    if not sep:
        raise TLSchemaError(f"Definition without result type: {line!r}")
    head, *tokens = left.split()
    name, _, hex_id = head.partition("#")
    generic_args = []
    params = []
    for token in tokens:
        if token.startswith("{"):
            generic_args.append(token.strip("{}").partition(":")[0])
        else:
            params.append(_parse_param(token))
    definition_id = int(hex_id, 16) if hex_id else constructor_id(line)
    return TLDefinition(
        name=name,
        id=definition_id,
        params=tuple(params),
        result=parse_type(result.strip()),
        is_function=is_function,
        generic_args=tuple(generic_args),
    )


def iter_definitions(text: str) -> Iterator[tuple[str, bool]]:
    """UZ: Sxema matnidan (ta'rif, funksiyami) juftliklarini beradi.
    RU: Возвращает пары (определение, функция ли) из текста схемы.
    EN: Yields (definition, is_function) pairs from schema text.
    """
    is_function = False
    for raw_line in text.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if line == "---functions---":
            is_function = True
        elif line == "---types---":
            is_function = False
        else:
            yield line, is_function


class TLSchema:
    """UZ: Ta'riflar to'plami: ID va nom bo'yicha qidirish.
    RU: Набор определений с поиском по ID и имени.
    EN: A set of definitions searchable by ID and name.
    """

    def __init__(self, definitions: Iterable[TLDefinition], layer: int | None = None) -> None:
        self.layer = layer
        self.constructors: dict[str, TLDefinition] = {}
        self.functions: dict[str, TLDefinition] = {}
        self.by_id: dict[int, TLDefinition] = {}
        for definition in definitions:
            target = self.functions if definition.is_function else self.constructors
            target[definition.name] = definition
            if not definition.is_function:
                self.by_id[definition.id] = definition
        self.function_ids = {definition.id: definition for definition in self.functions.values()}

    @classmethod
    def parse(cls, text: str) -> TLSchema:
        """UZ: `.tl` matnini o'qiydi (`// LAYER N` izohi ham). RU: Разбирает текст `.tl`
        (включая `// LAYER N`). EN: Parses `.tl` text (including `// LAYER N`).
        """
        layer = None
        for raw_line in text.splitlines():
            match = _LAYER_RE.match(raw_line.strip())
            if match:
                layer = int(match.group(1))
        definitions = [
            parse_definition(line, is_function=is_function)
            for line, is_function in iter_definitions(text)
        ]
        return cls(definitions, layer)

    def merge(self, other: TLSchema) -> TLSchema:
        """UZ: Ikki sxemani birlashtiradi (qatlam birinchisidan olinadi).
        RU: Объединяет две схемы (слой берётся у первой).
        EN: Merges two schemas (the layer comes from the first one).
        """
        definitions = [*self.constructors.values(), *self.functions.values()]
        definitions += [*other.constructors.values(), *other.functions.values()]
        return TLSchema(definitions, self.layer or other.layer)

    def constructor(self, name: str) -> TLDefinition:
        """UZ: Konstruktor nomi bo'yicha. RU: Конструктор по имени. EN: A constructor by name."""
        try:
            return self.constructors[name]
        except KeyError:
            raise KeyError(f"Unknown TL constructor {name!r}") from None

    def function(self, name: str) -> TLDefinition:
        """UZ: Funksiya nomi bo'yicha. RU: Функция по имени. EN: A function by name."""
        try:
            return self.functions[name]
        except KeyError:
            raise KeyError(f"Unknown TL function {name!r}") from None

    def __len__(self) -> int:
        return len(self.constructors) + len(self.functions)

    def __repr__(self) -> str:
        return (
            f"<TLSchema layer={self.layer} constructors={len(self.constructors)} "
            f"functions={len(self.functions)}>"
        )


__all__ = [
    "PRIMITIVES",
    "TLDefinition",
    "TLParam",
    "TLSchema",
    "TLSchemaError",
    "TLType",
    "constructor_id",
    "iter_definitions",
    "parse_definition",
    "parse_type",
]
