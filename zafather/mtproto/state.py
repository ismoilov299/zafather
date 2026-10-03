"""UZ: MTProto xabar holati: sessiya ID, `msg_id`, `seq_no`, tuz (salt) va vaqt farqi.
RU: Состояние сообщений MTProto: ID сессии, `msg_id`, `seq_no`, соль и сдвиг времени.
EN: MTProto message state: session ID, `msg_id`, `seq_no`, salt and clock offset.
"""

from __future__ import annotations

import os
import struct
import time
from dataclasses import dataclass

from .crypto import AuthKey
from .errors import SecurityError

_HEADER = struct.Struct("<qqqii")


class MessageIds:
    """UZ: Monoton o'suvchi, 4 ga karrali `msg_id` generatori (server vaqti bo'yicha).
    RU: Генератор монотонных `msg_id`, кратных 4 (по времени сервера).
    EN: Generates monotonic, 4-aligned `msg_id`s based on server time.
    """

    __slots__ = ("_last", "time_offset")

    def __init__(self, time_offset: int = 0) -> None:
        self.time_offset = time_offset
        self._last = 0

    def next(self) -> int:
        now = time.time() + self.time_offset
        msg_id = (int(now) << 32) | (int((now % 1) * 1e9) << 2)
        if msg_id <= self._last:
            msg_id = self._last + 4
        self._last = msg_id
        return msg_id

    def synchronize(self, server_msg_id: int) -> None:
        """UZ: Server `msg_id` siga qarab soat farqini to'g'rilaydi.
        RU: Корректирует сдвиг часов по `msg_id` сервера.
        EN: Corrects the clock offset using a server `msg_id`.
        """
        self.time_offset = (server_msg_id >> 32) - int(time.time())
        self._last = 0


@dataclass(frozen=True)
class IncomingMessage:
    msg_id: int
    seq_no: int
    body: bytes


class MTProtoState:
    """UZ: Shifrlangan sessiya holati va xabarlarni o'rash/ochish.
    RU: Состояние зашифрованной сессии, упаковка и распаковка сообщений.
    EN: Encrypted session state plus message packing and unpacking.
    """

    def __init__(self, auth_key: AuthKey, *, salt: int = 0, time_offset: int = 0) -> None:
        self.auth_key = auth_key
        self.salt = salt
        self.ids = MessageIds(time_offset)
        self.session_id = 0
        self._sequence = 0
        self.reset()

    def reset(self) -> None:
        """UZ: Yangi sessiya: ID yangilanadi, ketma-ketlik nolga tushadi.
        RU: Новая сессия: новый ID, счётчик последовательности обнуляется.
        EN: Starts a new session: a fresh ID and a zero sequence counter.
        """
        self.session_id = struct.unpack("<q", os.urandom(8))[0]
        self._sequence = 0

    def shift_sequence(self, delta: int) -> None:
        """UZ: Server `seq_no` haqida shikoyat qilganda ketma-ketlikni suradi.
        RU: Сдвигает счётчик, когда сервер сообщает о неверном `seq_no`.
        EN: Shifts the counter when the server reports a bad `seq_no`.
        """
        self._sequence = max(0, self._sequence + delta)

    def next_seq_no(self, content_related: bool) -> int:
        if content_related:
            seq_no = self._sequence * 2 + 1
            self._sequence += 1
            return seq_no
        return self._sequence * 2

    def pack(self, msg_id: int, seq_no: int, body: bytes) -> bytes:
        header = _HEADER.pack(self.salt, self.session_id, msg_id, seq_no, len(body))
        data = header + body
        padding = os.urandom(-(len(data) + 12) % 16 + 12)
        return self.auth_key.encrypt(data + padding, from_client=True)

    def unpack(self, envelope: bytes) -> IncomingMessage:
        plaintext = self.auth_key.decrypt(envelope, from_client=False)
        _, session_id, msg_id, seq_no, length = _HEADER.unpack_from(plaintext)
        if session_id != self.session_id:
            raise SecurityError("Message belongs to another session")
        if msg_id % 2 != 1:
            raise SecurityError("Server sent an even msg_id")
        padding = len(plaintext) - _HEADER.size - length
        if length < 0 or length % 4 or not 12 <= padding <= 1024:
            raise SecurityError("Invalid message length or padding")
        return IncomingMessage(msg_id, seq_no, plaintext[_HEADER.size : _HEADER.size + length])


__all__ = ["IncomingMessage", "MTProtoState", "MessageIds"]
