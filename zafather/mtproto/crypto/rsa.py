"""UZ: Telegram RSA ochiq kalitlari va MTProto `RSA_PAD` shifrlash.
RU: Открытые RSA-ключи Telegram и шифрование MTProto `RSA_PAD`.
EN: Telegram RSA public keys and MTProto `RSA_PAD` encryption.
"""

from __future__ import annotations

import base64
import hashlib
import os
from collections.abc import Iterable
from dataclasses import dataclass

from .aes import aes_ige_encrypt


def _tl_bytes(value: bytes) -> bytes:
    size = len(value)
    header = bytes((size,)) if size < 254 else b"\xfe" + size.to_bytes(3, "little")
    serialized = header + value
    return serialized + b"\x00" * (-len(serialized) % 4)


def _int_bytes(value: int) -> bytes:
    return value.to_bytes((value.bit_length() + 7) // 8, "big")


@dataclass(frozen=True)
class RSAPublicKey:
    """UZ: RSA ochiq kaliti (`n`, `e`). RU: Открытый ключ RSA (`n`, `e`).
    EN: An RSA public key (`n`, `e`).
    """

    n: int
    e: int = 65537

    @property
    def size(self) -> int:
        """UZ: Modul uzunligi baytlarda. RU: Длина модуля в байтах. EN: Modulus size in bytes."""
        return (self.n.bit_length() + 7) // 8

    @property
    def fingerprint(self) -> int:
        """UZ: `resPQ` dagi barmoq izi: SHA1(TL(n) + TL(e)) ning quyi 64 biti.
        RU: Отпечаток из `resPQ`: младшие 64 бита SHA1(TL(n) + TL(e)).
        EN: The `resPQ` fingerprint: the lower 64 bits of SHA1(TL(n) + TL(e)).
        """
        digest = hashlib.sha1(
            _tl_bytes(_int_bytes(self.n)) + _tl_bytes(_int_bytes(self.e))
        ).digest()
        return int.from_bytes(digest[-8:], "little", signed=True)

    def encrypt_raw(self, data: bytes) -> bytes:
        """UZ: To'ldirishsiz RSA (`data ** e mod n`). RU: RSA без дополнения
        (`data ** e mod n`). EN: Unpadded RSA (`data ** e mod n`).
        """
        value = int.from_bytes(data, "big")
        if value >= self.n:
            raise ValueError("RSA input must be smaller than the modulus")
        return pow(value, self.e, self.n).to_bytes(self.size, "big")

    @classmethod
    def from_pem(cls, pem: str) -> RSAPublicKey:
        """UZ: PKCS#1 `RSA PUBLIC KEY` PEM'dan o'qiydi. RU: Читает PEM PKCS#1 `RSA PUBLIC KEY`.
        EN: Loads a PKCS#1 `RSA PUBLIC KEY` PEM.
        """
        body = "".join(line for line in pem.strip().splitlines() if not line.startswith("-----"))
        return cls(*_parse_pkcs1(base64.b64decode(body)))


def _der_length(data: bytes, position: int) -> tuple[int, int]:
    first = data[position]
    if first < 0x80:
        return first, position + 1
    size = first & 0x7F
    return int.from_bytes(data[position + 1 : position + 1 + size], "big"), position + 1 + size


def _parse_pkcs1(der: bytes) -> tuple[int, int]:
    if der[0] != 0x30:
        raise ValueError("Not a PKCS#1 RSA public key")
    _, position = _der_length(der, 1)
    integers = []
    for _ in range(2):
        if der[position] != 0x02:
            raise ValueError("Malformed PKCS#1 RSA public key")
        length, position = _der_length(der, position + 1)
        integers.append(int.from_bytes(der[position : position + length], "big"))
        position += length
    return integers[0], integers[1]


def rsa_pad_encrypt(key: RSAPublicKey, data: bytes) -> bytes:
    """UZ: MTProto 2.0 `RSA_PAD`: `req_DH_params` uchun ma'lumotni shifrlaydi (<=144 bayt).
    RU: MTProto 2.0 `RSA_PAD`: шифрует данные для `req_DH_params` (<=144 байт).
    EN: MTProto 2.0 `RSA_PAD`: encrypts the `req_DH_params` payload (<=144 bytes).
    """
    if len(data) > 144:
        raise ValueError("RSA_PAD payload must be at most 144 bytes")
    data_with_padding = data + os.urandom(192 - len(data))
    reversed_data = data_with_padding[::-1]
    while True:
        temp_key = os.urandom(32)
        data_with_hash = reversed_data + hashlib.sha256(temp_key + data_with_padding).digest()
        aes_encrypted = aes_ige_encrypt(data_with_hash, temp_key, bytes(32))
        aes_hash = hashlib.sha256(aes_encrypted).digest()
        temp_key_xor = bytes(a ^ b for a, b in zip(temp_key, aes_hash, strict=True))
        key_aes_encrypted = temp_key_xor + aes_encrypted
        if int.from_bytes(key_aes_encrypted, "big") < key.n:
            return key.encrypt_raw(key_aes_encrypted)


#: UZ: Ishlab chiqarish serverlari kaliti (fingerprint 0xd09d1d85de64fd85).
#: RU: Ключ рабочих серверов (fingerprint 0xd09d1d85de64fd85).
#: EN: Production server key (fingerprint 0xd09d1d85de64fd85).
PRODUCTION_KEY = RSAPublicKey(
    int(
        "e8bb3305c0b52c6cf2afdf7637313489e63e05268e5badb601af417786472e5f93b85438968e20e6729a301c"
        "0afc121bf7151f834436f7fda680847a66bf64accec78ee21c0b316f0edafe2f41908da7bd1f4a5107638eeb"
        "67040ace472a14f90d9f7c2b7def99688ba3073adb5750bb02964902a359fe745d8170e36876d4fd8a5d41b2"
        "a76cbff9a13267eb9580b2d06d10357448d20d9da2191cb5d8c93982961cdfdeda629e37f1fb09a072202769"
        "6032fe61ed663db7a37f6f263d370f69db53a0dc0a1748bdaaff6209d5645485e6e001d1953255757e4b8e42"
        "813347b11da6ab500fd0ace7e6dfa3736199ccaf9397ed0745a427dcfa6cd67bcb1acff3",
        16,
    )
)

#: UZ: Test serverlari kaliti (fingerprint 0xb25898df208d2603).
#: RU: Ключ тестовых серверов (fingerprint 0xb25898df208d2603).
#: EN: Test server key (fingerprint 0xb25898df208d2603).
TEST_KEY = RSAPublicKey.from_pem(
    """-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAyMEdY1aR+sCR3ZSJrtztKTKqigvO/vBfqACJLZtS7QMgCGXJ6XIR
yy7mx66W0/sOFa7/1mAZtEoIokDP3ShoqF4fVNb6XeqgQfaUHd8wJpDWHcR2OFwv
plUUI1PLTktZ9uW2WE23b+ixNwJjJGwBDJPQEQFBE+vfmH0JP503wr5INS1poWg/
j25sIWeYPHYeOrFp/eXaqhISP6G+q2IeTaWTXpwZj4LzXq5YOpk4bYEQ6mvRq7D1
aHWfYmlEGepfaYR8Q0YqvvhYtMte3ITnuSJs171+GDqpdKcSwHnd6FudwGO4pcCO
j4WcDuXc2CTHgH8gFTNhp/Y8/SpDOhvn9QIDAQAB
-----END RSA PUBLIC KEY-----"""
)


def keys_by_fingerprint(keys: Iterable[RSAPublicKey]) -> dict[int, RSAPublicKey]:
    """UZ: Kalitlarni barmoq izi bo'yicha indekslaydi. RU: Индексирует ключи по отпечатку.
    EN: Indexes keys by their fingerprint.
    """
    return {key.fingerprint: key for key in keys}


__all__ = [
    "PRODUCTION_KEY",
    "TEST_KEY",
    "RSAPublicKey",
    "keys_by_fingerprint",
    "rsa_pad_encrypt",
]
