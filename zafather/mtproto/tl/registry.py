"""UZ: Paket ichidagi TL sxemasi va `functions`/`types` nom fazolari.
RU: Встроенная TL-схема и пространства имён `functions`/`types`.
EN: The bundled TL schema and the `functions`/`types` namespaces.

    from zafather.mtproto import functions, types

    request = functions.messages.sendMessage(
        peer=types.inputPeerSelf(), message="Salom", random_id=42
    )
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from importlib import resources
from typing import Any

from .objects import TLConstructor
from .schema import TLSchema
from .serializer import TLSerializer


@cache
def default_schema() -> TLSchema:
    """UZ: API (229-qatlam) va MTProto xizmat sxemalari birlashmasi.
    RU: Объединение схем API (слой 229) и служебной MTProto.
    EN: The API (layer 229) and MTProto service schemas combined.
    """
    data = resources.files(__package__) / "data"
    api = TLSchema.parse((data / "api.tl").read_text(encoding="utf-8"))
    service = TLSchema.parse((data / "mtproto.tl").read_text(encoding="utf-8"))
    return api.merge(service)


@cache
def default_serializer() -> TLSerializer:
    """UZ: Ichki sxema uchun serializer. RU: Сериализатор встроенной схемы.
    EN: The serializer for the bundled schema.
    """
    return TLSerializer(default_schema())


def schema_layer() -> int:
    """UZ: Sxema qatlami. RU: Слой схемы. EN: The schema layer."""
    layer = default_schema().layer
    if layer is None:
        raise RuntimeError("The bundled TL schema does not declare its layer")
    return layer


class TLNamespace:
    """UZ: `functions.messages.sendMessage` kabi nuqtali murojaatni ta'minlaydi.
    RU: Обеспечивает доступ через точку: `functions.messages.sendMessage`.
    EN: Provides dotted access such as `functions.messages.sendMessage`.
    """

    def __init__(
        self,
        functions: bool,
        prefix: str = "",
        schema: Callable[[], TLSchema] = default_schema,
        constructor: TLConstructor | None = None,
    ) -> None:
        self._functions = functions
        self._prefix = prefix
        self._schema = schema
        self._constructor = constructor

    def _table(self) -> dict[str, object]:
        schema = self._schema()
        return dict(schema.functions if self._functions else schema.constructors)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        schema = self._schema()
        table = schema.functions if self._functions else schema.constructors
        full_name = self._prefix + name
        nested = full_name + "."
        constructor = TLConstructor(table[full_name]) if full_name in table else None
        if any(key.startswith(nested) for key in table):
            return TLNamespace(self._functions, nested, self._schema, constructor)
        if constructor is not None:
            return constructor
        kind = "function" if self._functions else "constructor"
        raise AttributeError(f"No TL {kind} named {full_name!r}")

    def __call__(self, /, **values: Any) -> Any:
        """UZ: `types.updates(...)` kabi nom ham konstruktor, ham nom fazosi bo'lsa.
        RU: Когда имя одновременно конструктор и пространство имён (`types.updates(...)`).
        EN: For names that are both a constructor and a namespace (`types.updates(...)`).
        """
        if self._constructor is None:
            raise TypeError(f"{self!r} is a namespace, not a constructor")
        return self._constructor(**values)

    @property
    def definition(self) -> Any:
        if self._constructor is None:
            raise AttributeError("definition")
        return self._constructor.definition

    def __dir__(self) -> list[str]:
        names = set()
        for key in self._table():
            if key.startswith(self._prefix):
                names.add(key[len(self._prefix) :].split(".", 1)[0])
        return sorted(names)

    def __repr__(self) -> str:
        kind = "functions" if self._functions else "types"
        return f"<TLNamespace {kind}{'.' + self._prefix.rstrip('.') if self._prefix else ''}>"


#: UZ: Funksiyalar (so'rovlar). RU: Функции (запросы). EN: Functions (requests).
functions = TLNamespace(functions=True)
#: UZ: Konstruktorlar (tiplar). RU: Конструкторы (типы). EN: Constructors (types).
types = TLNamespace(functions=False)

__all__ = [
    "TLNamespace",
    "default_schema",
    "default_serializer",
    "functions",
    "schema_layer",
    "types",
]
