"""UZ: AES-IGE rejimi (MTProto shu rejimdan foydalanadi).
RU: Режим AES-IGE (используется в MTProto).
EN: AES-IGE mode (used by MTProto).
"""

from __future__ import annotations

from typing import Any

from ...exceptions import OptionalDependencyError


def _ecb(key: bytes) -> Any:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as exc:
        raise OptionalDependencyError("cryptography", "userbot") from exc
    return Cipher(algorithms.AES(key), modes.ECB())


def _xor(left: bytes, right: bytes) -> bytes:
    return (int.from_bytes(left, "little") ^ int.from_bytes(right, "little")).to_bytes(16, "little")


def _check(data: bytes, iv: bytes) -> None:
    if len(data) % 16:
        raise ValueError("AES-IGE data length must be a multiple of 16")
    if len(iv) != 32:
        raise ValueError("AES-IGE IV must be 32 bytes")


def aes_ige_encrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """UZ: AES-IGE shifrlash. RU: Шифрование AES-IGE. EN: AES-IGE encryption."""
    _check(data, iv)
    encryptor = _ecb(key).encryptor()
    previous_cipher, previous_plain = iv[:16], iv[16:]
    output = bytearray()
    for offset in range(0, len(data), 16):
        block = data[offset : offset + 16]
        encrypted = _xor(encryptor.update(_xor(block, previous_cipher)), previous_plain)
        output += encrypted
        previous_cipher, previous_plain = encrypted, block
    encryptor.finalize()
    return bytes(output)


def aes_ige_decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """UZ: AES-IGE ochish. RU: Расшифровка AES-IGE. EN: AES-IGE decryption."""
    _check(data, iv)
    decryptor = _ecb(key).decryptor()
    previous_cipher, previous_plain = iv[:16], iv[16:]
    output = bytearray()
    for offset in range(0, len(data), 16):
        block = data[offset : offset + 16]
        decrypted = _xor(decryptor.update(_xor(block, previous_plain)), previous_cipher)
        output += decrypted
        previous_cipher, previous_plain = block, decrypted
    decryptor.finalize()
    return bytes(output)


__all__ = ["aes_ige_decrypt", "aes_ige_encrypt"]
