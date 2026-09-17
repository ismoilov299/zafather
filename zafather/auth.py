"""UZ: MTProto auth handshake yordamchilari.
RU: Помощники auth handshake MTProto.
EN: MTProto auth handshake helpers.
"""
from __future__ import annotations

import math
import secrets
import hashlib
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .tl import TLReader, TLRequest


class RSAPublicKey:
    """UZ/RU/EN: MTProto RSA public key va PKCS#1 v1.5 encryption."""

    def __init__(self, n: int, e: int = 65537) -> None:
        if n <= 0 or e <= 1 or e % 2 == 0:
            raise ValueError("RSA n musbat, e esa toq bo'lishi kerak")
        self.n = n
        self.e = e

    @property
    def size(self) -> int:
        return (self.n.bit_length() + 7) // 8

    @property
    def fingerprint(self) -> bytes:
        body = self.n.to_bytes(self.size, "big") + self.e.to_bytes(
            (self.e.bit_length() + 7) // 8, "big"
        )
        return hashlib.sha1(body).digest()[-8:]

    def encrypt(self, payload: bytes) -> bytes:
        block_size = self.size
        if len(payload) > block_size - 11:
            raise ValueError("RSA payload juda katta")
        padding_size = block_size - len(payload) - 3
        padding = bytearray()
        while len(padding) < padding_size:
            padding.extend(secrets.token_bytes(padding_size - len(padding)))
            padding = bytearray(value for value in padding if value != 0)
        encoded = b"\x00\x02" + bytes(padding[:padding_size]) + b"\x00" + payload
        return pow(int.from_bytes(encoded, "big"), self.e, self.n).to_bytes(block_size, "big")


class DHExchange:
    """UZ/RU/EN: MTProto Diffie-Hellman public/private exchange."""

    def __init__(self, p: int, g: int, private: Optional[int] = None) -> None:
        if not self.validate_params(p, g):
            raise ValueError("DH group parametrlari noto'g'ri")
        self.p = p
        self.g = g
        self.private = private or secrets.randbelow(p - 3) + 2

    @property
    def public_value(self) -> int:
        return pow(self.g, self.private, self.p)

    def shared_secret(self, peer_public: int) -> int:
        if not self.validate_params(self.p, self.g, peer_public):
            raise ValueError("DH peer public qiymati noto'g'ri")
        return pow(peer_public, self.private, self.p)

    @staticmethod
    def validate_params(p: int, g: int, peer_public: Optional[int] = None) -> bool:
        if p <= 3 or g < 2 or g >= p - 1:
            return False
        if not AuthHandshake._is_prime(p):
            return False
        return peer_public is None or 1 < peer_public < p - 1


@dataclass(frozen=True)
class ResPQ:
    """UZ/RU/EN: Telegram `resPQ` javobi."""

    nonce: bytes
    server_nonce: bytes
    pq: int
    fingerprints: List[int]


class AuthHandshake:
    """UZ: Auth handshake'ning `req_pq` va `resPQ` bosqichi.
    RU: Этапы `req_pq` и `resPQ` auth handshake.
    EN: The `req_pq` and `resPQ` stages of auth handshake.
    """

    REQ_PQ = 0x60469778
    RES_PQ = 0x05162463
    REQ_DH_PARAMS = 0xD712E4BE

    def __init__(self, nonce: Optional[bytes] = None) -> None:
        self.nonce = nonce or secrets.token_bytes(16)
        if len(self.nonce) != 16:
            raise ValueError("MTProto nonce aynan 16 bayt bo'lishi kerak")

    def build_req_pq(self) -> bytes:
        return TLRequest(self.REQ_PQ).raw(self.nonce).to_bytes()

    def build_req_dh_params(
        self,
        server_nonce: bytes,
        p: bytes,
        q: bytes,
        fingerprint: bytes,
        encrypted_data: bytes,
    ) -> bytes:
        if len(server_nonce) != 16 or len(fingerprint) != 8:
            raise ValueError("server_nonce 16 bayt, fingerprint 8 bayt bo'lishi kerak")
        fingerprint_value = int.from_bytes(fingerprint, "little")
        if fingerprint_value >= 1 << 63:
            fingerprint_value -= 1 << 64
        return (
            TLRequest(self.REQ_DH_PARAMS)
            .raw(self.nonce)
            .raw(server_nonce)
            .bytes(p)
            .bytes(q)
            .int64(fingerprint_value)
            .bytes(encrypted_data)
            .to_bytes()
        )

    def parse_res_pq(self, payload: bytes) -> ResPQ:
        reader = TLReader(payload)
        if reader.uint32() != self.RES_PQ:
            raise ValueError("MTProto resPQ constructori noto'g'ri")
        nonce = reader.raw(16)
        if nonce != self.nonce:
            raise ValueError("MTProto nonce mos kelmadi")
        server_nonce = reader.raw(16)
        pq_bytes = reader.bytes()
        fingerprints = reader.vector("int64")
        return ResPQ(nonce, server_nonce, int.from_bytes(pq_bytes, "big"), fingerprints)

    @staticmethod
    def _is_prime(value: int) -> bool:
        if value < 2:
            return False
        for prime in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            if value % prime == 0:
                return value == prime
        d = value - 1
        shifts = 0
        while d % 2 == 0:
            shifts += 1
            d //= 2
        for base in (2, 3, 5, 7, 11, 13):
            if base >= value:
                continue
            result = pow(base, d, value)
            if result in (1, value - 1):
                continue
            for _ in range(shifts - 1):
                result = pow(result, 2, value)
                if result == value - 1:
                    break
            else:
                return False
        return True

    @classmethod
    def _pollard_rho(cls, value: int) -> int:
        if value % 2 == 0:
            return 2
        while True:
            constant = secrets.randbelow(value - 2) + 1
            current = secrets.randbelow(value - 2) + 2
            candidate = current
            divisor = 1
            while divisor == 1:
                current = (current * current + constant) % value
                candidate = (candidate * candidate + constant) % value
                candidate = (candidate * candidate + constant) % value
                divisor = math.gcd(abs(current - candidate), value)
            if divisor != value:
                return divisor

    @classmethod
    def _factor(cls, value: int) -> List[int]:
        if value == 1:
            return []
        if cls._is_prime(value):
            return [value]
        divisor = cls._pollard_rho(value)
        return cls._factor(divisor) + cls._factor(value // divisor)

    @classmethod
    def factor_pq(cls, pq: int) -> Tuple[int, int]:
        if pq <= 1:
            raise ValueError("pq musbat semiprime bo'lishi kerak")
        factors = sorted(cls._factor(pq))
        if len(factors) != 2 or factors[0] * factors[1] != pq:
            raise ValueError("pq ikkita tub ko'paytuvchiga ajralmadi")
        return factors[0], factors[1]


__all__ = ["AuthHandshake", "ResPQ"]
