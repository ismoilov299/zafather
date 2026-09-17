"""UZ: MTProto 2.0 kriptografiya yordamchilari.
RU: Криптографические помощники MTProto 2.0.
EN: MTProto 2.0 cryptography helpers.
"""
from __future__ import annotations

import hashlib
from typing import Tuple


class AuthKey:
    """UZ/RU/EN: 2048-bit MTProto auth key va AES-IGE envelope."""

    def __init__(self, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) != 256:
            raise ValueError("MTProto auth key aynan 256 bayt bo'lishi kerak")
        self.key = key

    @property
    def auth_key_id(self) -> bytes:
        return hashlib.sha1(self.key).digest()[-8:]

    def _aes_material(self, msg_key: bytes, outgoing: bool = True) -> Tuple[bytes, bytes]:
        if len(msg_key) != 16:
            raise ValueError("MTProto msg_key aynan 16 bayt bo'lishi kerak")
        x = 0 if outgoing else 8
        sha_a = hashlib.sha256(msg_key + self.key[x:x + 36]).digest()
        sha_b = hashlib.sha256(self.key[40 + x:76 + x] + msg_key).digest()
        aes_key = sha_a[:8] + sha_b[8:24] + sha_a[24:32]
        aes_iv = sha_b[:8] + sha_a[8:24] + sha_b[24:32]
        return aes_key, aes_iv

    @staticmethod
    def _ige(data: bytes, key: bytes, iv: bytes, encrypt: bool) -> bytes:
        if len(data) % 16 or len(iv) != 32:
            raise ValueError("AES-IGE data 16 baytga karrali, IV 32 bayt bo'lishi kerak")
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        except ImportError as exc:
            raise RuntimeError(
                "MTProto encryption uchun cryptography kerak: pip install zafather[userbot]"
            ) from exc
        cipher = Cipher(algorithms.AES(key), modes.ECB())
        operation = cipher.encryptor() if encrypt else cipher.decryptor()
        previous_cipher = iv[:16]
        previous_plain = iv[16:]
        output = bytearray()
        for offset in range(0, len(data), 16):
            block = data[offset:offset + 16]
            if encrypt:
                mixed = bytes(a ^ b for a, b in zip(block, previous_cipher))
                encrypted = operation.update(mixed)
                current_cipher = bytes(a ^ b for a, b in zip(encrypted, previous_plain))
                output.extend(current_cipher)
                previous_cipher, previous_plain = current_cipher, block
            else:
                mixed = bytes(a ^ b for a, b in zip(block, previous_plain))
                decrypted = operation.update(mixed)
                current_plain = bytes(a ^ b for a, b in zip(decrypted, previous_cipher))
                output.extend(current_plain)
                previous_cipher, previous_plain = block, current_plain
        operation.finalize()
        return bytes(output)

    def encrypt(self, payload: bytes, outgoing: bool = True) -> bytes:
        """UZ/RU/EN: Block-aligned payloadni MTProto encrypted envelopega o'raydi."""
        if len(payload) % 16:
            raise ValueError("MTProto payload AES-IGE uchun 16 baytga karrali bo'lishi kerak")
        msg_key_large = hashlib.sha256(self.key[88:120] + payload).digest()
        msg_key = msg_key_large[8:24]
        aes_key, aes_iv = self._aes_material(msg_key, outgoing)
        encrypted = self._ige(payload, aes_key, aes_iv, True)
        return self.auth_key_id + msg_key + encrypted

    def decrypt(self, envelope: bytes, outgoing: bool = False) -> bytes:
        """UZ/RU/EN: MTProto envelope'ni tekshiradi va ochadi."""
        if len(envelope) < 40 or (len(envelope) - 24) % 16:
            raise ValueError("MTProto encrypted envelope hajmi noto'g'ri")
        if envelope[:8] != self.auth_key_id:
            raise ValueError("MTProto auth_key_id mos kelmadi")
        msg_key = envelope[8:24]
        aes_key, aes_iv = self._aes_material(msg_key, outgoing)
        payload = self._ige(envelope[24:], aes_key, aes_iv, False)
        expected = hashlib.sha256(self.key[88:120] + payload).digest()[8:24]
        if expected != msg_key:
            raise ValueError("MTProto msg_key tekshiruvi muvaffaqiyatsiz")
        return payload


__all__ = ["AuthKey"]
