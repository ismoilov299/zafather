"""UZ: TL binar primitivlari: little-endian butun sonlar, baytlar, satrlar.
RU: Бинарные примитивы TL: целые числа little-endian, байты, строки.
EN: TL binary primitives: little-endian integers, bytes and strings.
"""

from __future__ import annotations

import builtins
import struct

VECTOR_ID = 0x1CB5C415
BOOL_TRUE_ID = 0x997275B5
BOOL_FALSE_ID = 0xBC799737
GZIP_PACKED_ID = 0x3072CFA1

_INT32 = struct.Struct("<i")
_UINT32 = struct.Struct("<I")
_INT64 = struct.Struct("<q")
_DOUBLE = struct.Struct("<d")


class TLDecodeError(ValueError):
    """UZ: Binar ma'lumot buzilgan yoki tugab qolgan.
    RU: Бинарные данные повреждены или закончились.
    EN: The binary data is malformed or truncated.
    """


class TLWriter:
    """UZ: TL qiymatlarini binar ko'rinishga yozadi. RU: Записывает значения TL в бинарный вид.
    EN: Writes TL values in binary form.
    """

    __slots__ = ("_buffer",)

    def __init__(self) -> None:
        self._buffer = bytearray()

    def raw(self, value: bytes) -> TLWriter:
        self._buffer += value
        return self

    def int32(self, value: int) -> TLWriter:
        self._buffer += _INT32.pack(value)
        return self

    def uint32(self, value: int) -> TLWriter:
        self._buffer += _UINT32.pack(value)
        return self

    def int64(self, value: int) -> TLWriter:
        self._buffer += _INT64.pack(value)
        return self

    def double(self, value: float) -> TLWriter:
        self._buffer += _DOUBLE.pack(value)
        return self

    def fixed(self, value: bytes | int, size: int) -> TLWriter:
        """UZ: `int128`/`int256` — aynan `size` bayt. RU: `int128`/`int256` — ровно `size` байт.
        EN: `int128`/`int256` — exactly `size` bytes.
        """
        if isinstance(value, int):
            value = value.to_bytes(size, "little", signed=value < 0)
        if len(value) != size:
            raise ValueError(f"Expected {size} bytes, got {len(value)}")
        return self.raw(value)

    def bytes(self, value: bytes) -> TLWriter:
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError(f"TL bytes value must be bytes, got {type(value).__name__}")
        size = len(value)
        if size < 254:
            header = bytes((size,))
        elif size < 1 << 24:
            header = b"\xfe" + size.to_bytes(3, "little")
        else:
            raise ValueError("TL bytes value must be shorter than 16 MiB")
        self._buffer += header
        self._buffer += value
        self._buffer += b"\x00" * (-(len(header) + size) % 4)
        return self

    def string(self, value: str) -> TLWriter:
        return self.bytes(value.encode("utf-8"))

    def to_bytes(self) -> builtins.bytes:
        return bytes(self._buffer)

    def __len__(self) -> int:
        return len(self._buffer)


class TLReader:
    """UZ: TL binar qiymatlarini ketma-ket o'qiydi. RU: Последовательно читает бинарные значения TL.
    EN: Reads TL binary values sequentially.
    """

    __slots__ = ("_data", "_position")

    def __init__(self, data: bytes) -> None:
        self._data = memoryview(data)
        self._position = 0

    def read(self, size: int) -> bytes:
        end = self._position + size
        if size < 0 or end > len(self._data):
            raise TLDecodeError(f"Unexpected end of data: need {size} bytes at {self._position}")
        value = self._data[self._position : end].tobytes()
        self._position = end
        return value

    def int32(self) -> int:
        return int(_INT32.unpack(self.read(4))[0])

    def uint32(self) -> int:
        return int(_UINT32.unpack(self.read(4))[0])

    def int64(self) -> int:
        return int(_INT64.unpack(self.read(8))[0])

    def double(self) -> float:
        return float(_DOUBLE.unpack(self.read(8))[0])

    def fixed(self, size: int) -> bytes:
        return self.read(size)

    def bytes(self) -> builtins.bytes:
        first = self.read(1)[0]
        if first == 254:
            size = int.from_bytes(self.read(3), "little")
            header = 4
        elif first == 255:
            raise TLDecodeError("Invalid TL bytes length prefix 0xff")
        else:
            size = first
            header = 1
        value = self.read(size)
        self.read(-(header + size) % 4)
        return value

    def string(self) -> str:
        return self.bytes().decode("utf-8", errors="replace")

    def peek_uint32(self) -> int:
        position = self._position
        value = self.uint32()
        self._position = position
        return value

    def rest(self) -> builtins.bytes:
        return self.read(len(self._data) - self._position)

    @property
    def position(self) -> int:
        return self._position

    @property
    def remaining(self) -> int:
        return len(self._data) - self._position


__all__ = [
    "BOOL_FALSE_ID",
    "BOOL_TRUE_ID",
    "GZIP_PACKED_ID",
    "VECTOR_ID",
    "TLDecodeError",
    "TLReader",
    "TLWriter",
]
