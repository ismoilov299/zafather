"""UZ: Telegram TL binary serializer/deserializer.
RU: Бинарный serializer/deserializer Telegram TL.
EN: Telegram TL binary serializer/deserializer.
"""
from __future__ import annotations

import struct
from typing import Any, Iterable, List


class TLWriter:
    """UZ/RU/EN: TL qiymatlarini little-endian binary formatga yozadi."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def raw(self, value: bytes) -> "TLWriter":
        self._buffer.extend(value)
        return self

    def int32(self, value: int) -> "TLWriter":
        self._buffer.extend(struct.pack("<i", value))
        return self

    def uint32(self, value: int) -> "TLWriter":
        self._buffer.extend(struct.pack("<I", value))
        return self

    def int64(self, value: int) -> "TLWriter":
        self._buffer.extend(struct.pack("<q", value))
        return self

    def int128(self, value: int) -> "TLWriter":
        return self.raw(int(value).to_bytes(16, "little", signed=True))

    def int256(self, value: int) -> "TLWriter":
        return self.raw(int(value).to_bytes(32, "little", signed=True))

    def bytes(self, value: bytes) -> "TLWriter":
        if not isinstance(value, bytes):
            raise TypeError("TL bytes qiymati bytes bo'lishi kerak")
        size = len(value)
        if size < 254:
            self._buffer.append(size)
            header_size = 1
        else:
            if size >= 1 << 24:
                raise ValueError("TL bytes qiymati 2^24 baytdan kichik bo'lishi kerak")
            self._buffer.append(254)
            self._buffer.extend(size.to_bytes(3, "little"))
            header_size = 4
        self._buffer.extend(value)
        self._buffer.extend(b"\x00" * ((-(header_size + size)) % 4))
        return self

    def string(self, value: str) -> "TLWriter":
        return self.bytes(value.encode("utf-8"))

    def vector(self, values: Iterable[Any], encoder: str = "int32") -> "TLWriter":
        items = list(values)
        self.uint32(0x1CB5C415).int32(len(items))
        for value in items:
            method = getattr(self, encoder)
            method(value)
        return self

    def to_bytes(self) -> bytes:
        return bytes(self._buffer)


class TLReader:
    """UZ/RU/EN: TL binary qiymatlarini ketma-ket o'qiydi."""

    def __init__(self, data: bytes) -> None:
        self._data = memoryview(data)
        self._position = 0

    def _read(self, size: int) -> bytes:
        end = self._position + size
        if end > len(self._data):
            raise ValueError("TL buffer yetarli emas")
        value = self._data[self._position:end].tobytes()
        self._position = end
        return value

    def raw(self, size: int) -> bytes:
        return self._read(size)

    def int32(self) -> int:
        return struct.unpack("<i", self._read(4))[0]

    def uint32(self) -> int:
        return struct.unpack("<I", self._read(4))[0]

    def int64(self) -> int:
        return struct.unpack("<q", self._read(8))[0]

    def int128(self) -> int:
        return int.from_bytes(self._read(16), "little", signed=True)

    def int256(self) -> int:
        return int.from_bytes(self._read(32), "little", signed=True)

    def bytes(self) -> bytes:
        first = self._read(1)[0]
        if first == 254:
            size = int.from_bytes(self._read(3), "little")
            header_size = 4
        else:
            size = first
            header_size = 1
        value = self._read(size)
        padding = (-(header_size + size)) % 4
        if padding:
            self._read(padding)
        return value

    def string(self) -> str:
        return self.bytes().decode("utf-8")

    def vector(self, decoder: str = "int32") -> List[Any]:
        if self.uint32() != 0x1CB5C415:
            raise ValueError("TL vector constructori noto'g'ri")
        return [getattr(self, decoder)() for _ in range(self.int32())]

    @property
    def remaining(self) -> int:
        return len(self._data) - self._position


class TLRequest(TLWriter):
    """UZ/RU/EN: Constructor ID bilan boshlanadigan TL request builder."""

    def __init__(self, constructor_id: int) -> None:
        super().__init__()
        self.uint32(constructor_id)


__all__ = ["TLReader", "TLWriter", "TLRequest"]
