"""UZ: Sxemaga asoslangan TL serializatsiya va deserializatsiya.
RU: Сериализация и десериализация TL на основе схемы.
EN: Schema-driven TL serialization and deserialization.
"""

from __future__ import annotations

import gzip
from typing import Any

from .codec import (
    BOOL_FALSE_ID,
    BOOL_TRUE_ID,
    GZIP_PACKED_ID,
    VECTOR_ID,
    TLDecodeError,
    TLReader,
    TLWriter,
)
from .objects import TLObject
from .schema import TLDefinition, TLParam, TLSchema, TLType

OBJECT = TLType("Object")


class TLSerializer:
    """UZ: `TLObject` <-> baytlar. Tiplar sxemadagi e'lonlar bo'yicha tekshiriladi.
    RU: `TLObject` <-> байты. Типы проверяются по объявлениям схемы.
    EN: `TLObject` <-> bytes. Types are checked against the schema declarations.
    """

    def __init__(self, schema: TLSchema) -> None:
        self.schema = schema

    # --- UZ: yozish / RU: запись / EN: writing ---------------------------------------------
    def serialize(self, obj: TLObject) -> bytes:
        """UZ: Obyektni (konstruktor ID si bilan) baytlarga. RU: Объект (с ID конструктора) в
        байты. EN: Serializes an object (boxed, with its constructor ID).
        """
        writer = TLWriter()
        self._write_object(writer, obj, boxed=True)
        return writer.to_bytes()

    def _write_object(self, writer: TLWriter, obj: TLObject, *, boxed: bool) -> None:
        definition = obj.definition
        if boxed:
            writer.uint32(definition.id)
        values = obj.values
        flags = self._flags(definition, values)
        for param in definition.params:
            if param.is_flags_field:
                writer.uint32(flags[param.name])
                continue
            value = values.get(param.name)
            path = f"{definition.name}.{param.name}"
            if param.flag is not None:
                if param.is_true_flag or not _flag_set(param, flags):
                    continue
                if value is None:
                    # UZ: Bit boshqa maydon tomonidan yoqilgan — bu maydon ham majburiy.
                    # RU: Бит включён другим полем — это поле тоже обязательно.
                    # EN: Another field sharing this bit set it, so this one is required too.
                    raise TLTypeError(f"{path} is required when its flag bit is set")
            elif value is None:
                raise TLTypeError(f"{path} is required")
            self._write_value(writer, param.type, value, path)

    @staticmethod
    def _flags(definition: TLDefinition, values: dict[str, Any]) -> dict[str, int]:
        flags = {param.name: 0 for param in definition.params if param.is_flags_field}
        for param in definition.params:
            if param.flag is None:
                continue
            value = values.get(param.name)
            present = bool(value) if param.is_true_flag else value is not None
            if present:
                field, bit = param.flag
                flags[field] = flags.get(field, 0) | (1 << bit)
        return flags

    def _write_value(self, writer: TLWriter, type_: TLType, value: Any, path: str) -> None:
        name = type_.name
        try:
            if name == "int":
                writer.int32(int(value))
            elif name == "long":
                writer.int64(int(value))
            elif name == "double":
                writer.double(float(value))
            elif name == "int128":
                writer.fixed(value, 16)
            elif name == "int256":
                writer.fixed(value, 32)
            elif name == "string" or name == "bytes":
                writer.bytes(value.encode("utf-8") if isinstance(value, str) else value)
            elif name == "Bool":
                writer.uint32(BOOL_TRUE_ID if value else BOOL_FALSE_ID)
            elif type_.is_vector:
                self._write_vector(writer, type_, value, path)
            else:
                self._write_typed_object(writer, type_, value, path)
        except (TypeError, ValueError, OverflowError) as exc:
            if isinstance(exc, TLTypeError):
                raise
            raise TLTypeError(f"{path}: cannot encode {value!r} as {type_}: {exc}") from exc

    def _write_vector(self, writer: TLWriter, type_: TLType, value: Any, path: str) -> None:
        if not isinstance(value, (list, tuple)):
            raise TLTypeError(f"{path}: expected a list for {type_}, got {type(value).__name__}")
        if not type_.bare:
            writer.uint32(VECTOR_ID)
        writer.int32(len(value))
        item_type = type_.argument or OBJECT
        for index, item in enumerate(value):
            self._write_value(writer, item_type, item, f"{path}[{index}]")

    def _write_typed_object(self, writer: TLWriter, type_: TLType, value: Any, path: str) -> None:
        if isinstance(value, (bytes, bytearray)) and (type_.generic or type_.name == "Object"):
            writer.raw(bytes(value))
            return
        if not isinstance(value, TLObject):
            raise TLTypeError(f"{path}: expected a TL object for {type_}, got {value!r}")
        if type_.is_bare_constructor:
            if value.tl_name != type_.name:
                raise TLTypeError(f"{path}: expected {type_.name}, got {value.tl_name}")
            self._write_object(writer, value, boxed=False)
            return
        expected = None if type_.generic or type_.name in ("Object", "X", "Type") else type_.name
        if expected is not None and value.definition.result.name != expected:
            raise TLTypeError(f"{path}: expected {expected}, got {value.tl_name}")
        self._write_object(writer, value, boxed=True)

    # --- UZ: o'qish / RU: чтение / EN: reading ------------------------------------------------
    def deserialize(self, data: bytes, expected: TLType | None = None) -> Any:
        """UZ: Baytlardan qiymat (`expected` — kutilgan tip). RU: Значение из байтов
        (`expected` — ожидаемый тип). EN: Reads a value (`expected` is the expected type).
        """
        return self.read(TLReader(data), expected or OBJECT)

    def read(self, reader: TLReader, type_: TLType) -> Any:
        """UZ: `reader` dan berilgan tipdagi qiymat. RU: Значение заданного типа из
        `reader`. EN: Reads a value of the given type from `reader`.
        """
        name = type_.name
        if name == "int":
            return reader.int32()
        if name == "long":
            return reader.int64()
        if name == "double":
            return reader.double()
        if name == "int128":
            return reader.fixed(16)
        if name == "int256":
            return reader.fixed(32)
        if name == "string":
            return reader.string()
        if name == "bytes":
            return reader.bytes()
        if name == "true":
            return True
        if type_.is_vector and type_.bare:
            return self._read_vector_items(reader, type_)
        if type_.is_bare_constructor:
            return self._read_fields(reader, self.schema.constructor(name))
        return self._read_boxed(reader, type_)

    def _read_vector_items(self, reader: TLReader, type_: TLType) -> list[Any]:
        count = reader.int32()
        if count < 0:
            raise TLDecodeError(f"Negative vector length {count}")
        item_type = type_.argument or OBJECT
        return [self.read(reader, item_type) for _ in range(count)]

    def _read_boxed(self, reader: TLReader, type_: TLType) -> Any:
        constructor_id = reader.uint32()
        if constructor_id == GZIP_PACKED_ID:
            return self.read(TLReader(gzip.decompress(reader.bytes())), type_)
        if constructor_id == BOOL_TRUE_ID:
            return True
        if constructor_id == BOOL_FALSE_ID:
            return False
        if constructor_id == VECTOR_ID:
            return self._read_vector_items(reader, type_ if type_.is_vector else OBJECT)
        definition = self.schema.by_id.get(constructor_id) or self.schema.function_ids.get(
            constructor_id
        )
        if definition is None:
            raise TLDecodeError(f"Unknown constructor 0x{constructor_id:08x} (expected {type_})")
        return self._read_fields(reader, definition)

    def _read_fields(self, reader: TLReader, definition: TLDefinition) -> TLObject:
        values: dict[str, Any] = {}
        flags: dict[str, int] = {}
        for param in definition.params:
            if param.is_flags_field:
                flags[param.name] = reader.uint32()
                continue
            if param.flag is not None and not _flag_set(param, flags):
                continue
            values[param.name] = self.read(reader, param.type)
        return TLObject(definition, values, validate=False)

    # --- UZ: natija tipi / RU: тип результата / EN: result type ---------------------------
    def result_type(self, request: TLObject) -> TLType:
        """UZ: Funksiya natijasi tipi (`invokeWithLayer` kabi generik o'ramlar ochiladi).
        RU: Тип результата функции (обёртки вроде `invokeWithLayer` раскрываются).
        EN: The function's result type (generic wrappers such as `invokeWithLayer` unwrap).
        """
        definition = request.definition
        if definition.result.name in definition.generic_args:
            for param in definition.params:
                if param.type.generic:
                    inner = request.values.get(param.name)
                    if isinstance(inner, TLObject):
                        return self.result_type(inner)
            return OBJECT
        return definition.result


class TLTypeError(TypeError):
    """UZ: Qiymat sxemadagi tipga mos emas. RU: Значение не соответствует типу схемы.
    EN: A value does not match the schema type.
    """


def _flag_set(param: TLParam, flags: dict[str, int]) -> bool:
    assert param.flag is not None
    field, bit = param.flag
    return bool(flags.get(field, 0) & (1 << bit))


__all__ = ["OBJECT", "TLSerializer", "TLTypeError"]
