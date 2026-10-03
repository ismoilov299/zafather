"""UZ: MTProto 2.0 avtorizatsiya kaliti va xabarlarni shifrlash.
RU: Ключ авторизации MTProto 2.0 и шифрование сообщений.
EN: The MTProto 2.0 authorization key and message encryption.
"""

from __future__ import annotations

import hashlib
import hmac

from ..errors import SecurityError
from .aes import aes_ige_decrypt, aes_ige_encrypt


class AuthKey:
    """UZ: 2048-bitli avtorizatsiya kaliti.
    RU: 2048-битный ключ авторизации.
    EN: A 2048-bit authorization key.

    UZ: `from_client=True` — mijoz yuborgan xabar (x=0), `False` — server yuborgan (x=8).
    RU: `from_client=True` — сообщение клиента (x=0), `False` — сервера (x=8).
    EN: `from_client=True` means a client message (x=0); `False` a server message (x=8).
    """

    __slots__ = ("aux_hash", "id", "key")

    def __init__(self, key: bytes) -> None:
        if len(key) != 256:
            raise ValueError("An MTProto authorization key must be exactly 256 bytes")
        digest = hashlib.sha1(key).digest()
        self.key = bytes(key)
        self.id = digest[-8:]
        self.aux_hash = digest[:8]

    @property
    def id_int(self) -> int:
        return int.from_bytes(self.id, "little", signed=True)

    def new_nonce_hash(self, new_nonce: bytes, number: int) -> bytes:
        """UZ: `new_nonce_hash1/2/3` (128 bit). RU: `new_nonce_hash1/2/3` (128 бит).
        EN: `new_nonce_hash1/2/3` (128 bits).
        """
        return hashlib.sha1(new_nonce + bytes((number,)) + self.aux_hash).digest()[4:20]

    def _key_iv(self, msg_key: bytes, from_client: bool) -> tuple[bytes, bytes]:
        x = 0 if from_client else 8
        sha_a = hashlib.sha256(msg_key + self.key[x : x + 36]).digest()
        sha_b = hashlib.sha256(self.key[40 + x : 76 + x] + msg_key).digest()
        aes_key = sha_a[:8] + sha_b[8:24] + sha_a[24:32]
        aes_iv = sha_b[:8] + sha_a[8:24] + sha_b[24:32]
        return aes_key, aes_iv

    def _msg_key(self, plaintext: bytes, from_client: bool) -> bytes:
        x = 0 if from_client else 8
        return hashlib.sha256(self.key[88 + x : 120 + x] + plaintext).digest()[8:24]

    def encrypt(self, plaintext: bytes, *, from_client: bool = True) -> bytes:
        """UZ: To'ldirilgan (16 ga karrali) matnni shifrlab, konvert qaytaradi.
        RU: Шифрует дополненный (кратный 16) текст и возвращает конверт.
        EN: Encrypts padded (16-byte aligned) plaintext into an envelope.
        """
        if len(plaintext) % 16:
            raise ValueError("Plaintext must be padded to a multiple of 16 bytes")
        msg_key = self._msg_key(plaintext, from_client)
        aes_key, aes_iv = self._key_iv(msg_key, from_client)
        return self.id + msg_key + aes_ige_encrypt(plaintext, aes_key, aes_iv)

    def decrypt(self, envelope: bytes, *, from_client: bool = False) -> bytes:
        """UZ: Konvertni ochadi va `msg_key` ni tekshiradi. RU: Открывает конверт и проверяет
        `msg_key`. EN: Opens an envelope and verifies its `msg_key`.
        """
        if len(envelope) < 24 + 16 or (len(envelope) - 24) % 16:
            raise SecurityError("Encrypted message has an invalid length")
        if not hmac.compare_digest(envelope[:8], self.id):
            raise SecurityError("auth_key_id mismatch")
        msg_key = envelope[8:24]
        aes_key, aes_iv = self._key_iv(msg_key, from_client)
        plaintext = aes_ige_decrypt(envelope[24:], aes_key, aes_iv)
        if not hmac.compare_digest(msg_key, self._msg_key(plaintext, from_client)):
            raise SecurityError("msg_key mismatch")
        return plaintext

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AuthKey) and hmac.compare_digest(self.key, other.key)

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"<AuthKey id={self.id.hex()}>"


__all__ = ["AuthKey"]
