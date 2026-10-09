"""UZ: Ikki bosqichli tekshiruv (2FA) uchun SRP hisoblash.
RU: Вычисление SRP для двухэтапной проверки (2FA).
EN: SRP computation for two-step verification (2FA).

UZ: Algoritm: `passwordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow`.
RU: Алгоритм: `passwordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow`.
EN: Algorithm: `passwordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow`.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from ..errors import SecurityError
from .dh import check_dh_params

_SIZE = 256


def _sha256(*parts: bytes) -> bytes:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part)
    return digest.digest()


def _pad(value: int) -> bytes:
    return value.to_bytes(_SIZE, "big")


def _good_power(value: int, prime: int) -> bool:
    bits = 2048 - 64
    return 0 < value < prime and (prime - value).bit_length() >= bits and value.bit_length() >= bits


def password_hash(password: str, salt1: bytes, salt2: bytes) -> bytes:
    """UZ: PH2(parol, salt1, salt2). RU: PH2(пароль, salt1, salt2).
    EN: PH2(password, salt1, salt2).
    """
    hash1 = _sha256(salt1, password.encode("utf-8"), salt1)
    hash2 = _sha256(salt2, hash1, salt2)
    hash3 = hashlib.pbkdf2_hmac("sha512", hash2, salt1, 100000)
    return _sha256(salt2, hash3, salt2)


@dataclass(frozen=True)
class SRPAnswer:
    """UZ: `inputCheckPasswordSRP` uchun `A` va `M1`. RU: `A` и `M1` для
    `inputCheckPasswordSRP`. EN: `A` and `M1` for `inputCheckPasswordSRP`.
    """

    a_bytes: bytes
    m1: bytes


def compute_srp_answer(
    password: str,
    *,
    salt1: bytes,
    salt2: bytes,
    g: int,
    p: bytes,
    srp_b: bytes,
    secret_a: int | None = None,
) -> SRPAnswer:
    """UZ: Server parametrlari (`account.password`) bo'yicha SRP javobini hisoblaydi.
    RU: Вычисляет ответ SRP по параметрам сервера (`account.password`).
    EN: Computes the SRP answer from the server parameters (`account.password`).
    """
    prime = int.from_bytes(p, "big")
    check_dh_params(prime, g)
    g_b = int.from_bytes(srp_b, "big")
    if not _good_power(g_b, prime):
        raise SecurityError("Invalid SRP B value")
    p_bytes, g_bytes, b_bytes = _pad(prime), _pad(g), _pad(g_b)
    x = int.from_bytes(password_hash(password, salt1, salt2), "big")
    k = int.from_bytes(_sha256(p_bytes, g_bytes), "big")
    kg_x = k * pow(g, x, prime) % prime
    while True:
        a = secret_a if secret_a is not None else int.from_bytes(os.urandom(_SIZE), "big")
        g_a = pow(g, a, prime)
        u = int.from_bytes(_sha256(_pad(g_a), b_bytes), "big")
        if _good_power(g_a, prime) and u > 0:
            break
        if secret_a is not None:
            raise SecurityError("The supplied SRP secret produces an invalid A")
    s_a = pow((g_b - kg_x) % prime, a + u * x, prime)
    k_a = _sha256(_pad(s_a))
    hashed_pg = bytes(a ^ b for a, b in zip(_sha256(p_bytes), _sha256(g_bytes), strict=True))
    m1 = _sha256(hashed_pg, _sha256(salt1), _sha256(salt2), _pad(g_a), b_bytes, k_a)
    return SRPAnswer(_pad(g_a), m1)


__all__ = ["SRPAnswer", "compute_srp_answer", "password_hash"]
