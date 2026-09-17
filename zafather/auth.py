"""UZ: MTProto auth handshake yordamchilari.
RU: Помощники auth handshake MTProto.
EN: MTProto auth handshake helpers.
"""
from __future__ import annotations

import math
import secrets
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .tl import TLReader, TLRequest


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

    def __init__(self, nonce: Optional[bytes] = None) -> None:
        self.nonce = nonce or secrets.token_bytes(16)
        if len(self.nonce) != 16:
            raise ValueError("MTProto nonce aynan 16 bayt bo'lishi kerak")

    def build_req_pq(self) -> bytes:
        return TLRequest(self.REQ_PQ).raw(self.nonce).to_bytes()

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
