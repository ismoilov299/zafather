"""UZ: MTProto transport interfeysi va paket ramkalash kodeklari.
RU: Интерфейс транспорта MTProto и кодеки кадрирования пакетов.
EN: The MTProto transport interface and packet framing codecs.
"""

from __future__ import annotations

import asyncio
import struct
from abc import ABC, abstractmethod

from ..errors import AuthKeyNotFoundError, TransportError


class Transport(ABC):
    """UZ: Binar paketlarni yuboradigan va qabul qiladigan ulanish.
    RU: Соединение, отправляющее и принимающее бинарные пакеты.
    EN: A connection that sends and receives binary packets.
    """

    @property
    @abstractmethod
    def connected(self) -> bool:
        """UZ: Ulanish ochiqmi. RU: Открыто ли соединение. EN: Whether it is connected."""

    @abstractmethod
    async def connect(self) -> None:
        """UZ: Ulanishni ochadi. RU: Открывает соединение. EN: Opens the connection."""

    @abstractmethod
    async def send(self, packet: bytes) -> None:
        """UZ: Bitta paket yuboradi. RU: Отправляет один пакет. EN: Sends one packet."""

    @abstractmethod
    async def receive(self) -> bytes:
        """UZ: Bitta paketni kutadi. RU: Ждёт один пакет. EN: Waits for one packet."""

    @abstractmethod
    async def close(self) -> None:
        """UZ: Ulanishni yopadi. RU: Закрывает соединение. EN: Closes the connection."""


class FrameCodec(ABC):
    """UZ: TCP oqimida paket chegaralarini belgilash usuli.
    RU: Способ разметки границ пакетов в потоке TCP.
    EN: How packet boundaries are marked in the TCP stream.
    """

    #: UZ: Ulangandan keyin bir marta yuboriladigan belgi. RU: Метка, отправляемая один раз.
    #: EN: The tag sent once right after connecting.
    tag: bytes = b""

    @abstractmethod
    def encode(self, payload: bytes) -> bytes:
        """UZ: Paketni ramkalaydi. RU: Кадрирует пакет. EN: Frames a packet."""

    @abstractmethod
    async def read_frame(self, reader: asyncio.StreamReader) -> bytes:
        """UZ: Bitta ramkani o'qiydi. RU: Читает один кадр. EN: Reads one frame."""


class AbridgedCodec(FrameCodec):
    """UZ: MTProto Abridged: uzunlik 4 baytli so'zlarda, 1 yoki 4 baytli sarlavha.
    RU: MTProto Abridged: длина в 4-байтовых словах, заголовок 1 или 4 байта.
    EN: MTProto Abridged: length in 4-byte words, a 1- or 4-byte header.
    """

    tag = b"\xef"

    def encode(self, payload: bytes) -> bytes:
        if len(payload) % 4:
            raise ValueError("Abridged payloads must be 4-byte aligned")
        words = len(payload) // 4
        if words < 0x7F:
            return bytes((words,)) + payload
        if words >= 1 << 24:
            raise ValueError("Packet is too large for the abridged transport")
        return b"\x7f" + words.to_bytes(3, "little") + payload

    async def read_frame(self, reader: asyncio.StreamReader) -> bytes:
        first = (await reader.readexactly(1))[0] & 0x7F
        words = int.from_bytes(await reader.readexactly(3), "little") if first == 0x7F else first
        return await reader.readexactly(words * 4)


class IntermediateCodec(FrameCodec):
    """UZ: MTProto Intermediate: 4 baytli uzunlik sarlavhasi.
    RU: MTProto Intermediate: 4-байтовый заголовок длины.
    EN: MTProto Intermediate: a 4-byte length header.
    """

    tag = b"\xee\xee\xee\xee"

    def encode(self, payload: bytes) -> bytes:
        return struct.pack("<I", len(payload)) + payload

    async def read_frame(self, reader: asyncio.StreamReader) -> bytes:
        size = struct.unpack("<I", await reader.readexactly(4))[0] & 0x7FFFFFFF
        return await reader.readexactly(size)


def check_transport_error(packet: bytes) -> None:
    """UZ: 4 baytli manfiy javob — transport xatosi (masalan, -404, -429).
    RU: 4-байтовый отрицательный ответ — ошибка транспорта (например, -404, -429).
    EN: A 4-byte negative reply is a transport error (for example -404 or -429).
    """
    if len(packet) != 4:
        return
    code = struct.unpack("<i", packet)[0]
    if code >= 0:
        return
    if code == -404:
        raise AuthKeyNotFoundError("Authorization key is unknown to the server", code)
    raise TransportError(f"Transport error {code}", code)


__all__ = [
    "AbridgedCodec",
    "FrameCodec",
    "IntermediateCodec",
    "Transport",
    "check_transport_error",
]
