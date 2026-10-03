"""UZ: Diffie-Hellman parametrlarini tekshirish va `pq` ni ko'paytuvchilarga ajratish.
RU: Проверка параметров Диффи-Хеллмана и разложение `pq` на множители.
EN: Diffie-Hellman parameter checks and `pq` factorisation.
"""

from __future__ import annotations

import math
import secrets

from ..errors import SecurityError

#: UZ: Telegram ishlatadigan 2048-bitli xavfsiz tub son.
#: RU: 2048-битное безопасное простое число, используемое Telegram.
#: EN: The 2048-bit safe prime used by Telegram.
TELEGRAM_DH_PRIME = int(
    "c71caeb9c6b1c9048e6c522f70f13f73980d40238e3e21c14934d037563d930f48198a0aa7c14058229493d225"
    "30f4dbfa336f6e0ac925139543aed44cce7c3720fd51f69458705ac68cd4fe6b6b13abdc9746512969328454f1"
    "8faf8c595f642477fe96bb2a941d5bcd1d4ac8cc49880708fa9b378e3c4f3a9060bee67cf9a4a4a69581105190"
    "7e162753b56b0f6b410dba74d8a84b2a14b3144e0ef1284754fd17ed950d5965b4b9dd46582db1178d169c6bc"
    "465b0d6ff9ca3928fef5b9ae4e418fc15e83ebea0f87fa9ff5eed70050ded2849f47bf959d956850ce929851f0"
    "d8115f635b105ee2e4e15d04b2454bf6f4fadf034b10403119cd8e3b92fcc5b",
    16,
)

_SMALL_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)


def is_probable_prime(value: int, rounds: int = 32) -> bool:
    """UZ: Miller-Rabin testi. RU: Тест Миллера-Рабина. EN: The Miller-Rabin test."""
    if value < 2:
        return False
    for prime in _SMALL_PRIMES:
        if value % prime == 0:
            return value == prime
    exponent, shifts = value - 1, 0
    while exponent % 2 == 0:
        exponent //= 2
        shifts += 1
    for _ in range(rounds):
        witness = secrets.randbelow(value - 3) + 2
        current = pow(witness, exponent, value)
        if current in (1, value - 1):
            continue
        for _ in range(shifts - 1):
            current = pow(current, 2, value)
            if current == value - 1:
                break
        else:
            return False
    return True


def _generator_is_valid(g: int, prime: int) -> bool:
    rules = {
        2: lambda p: p % 8 == 7,
        3: lambda p: p % 3 == 2,
        4: lambda p: True,
        5: lambda p: p % 5 in (1, 4),
        6: lambda p: p % 24 in (19, 23),
        7: lambda p: p % 7 in (3, 5, 6),
    }
    rule = rules.get(g)
    return rule is not None and rule(prime)


def check_dh_params(prime: int, g: int) -> None:
    """UZ: `dh_prime` va `g` ni MTProto talablari bo'yicha tekshiradi.
    RU: Проверяет `dh_prime` и `g` по требованиям MTProto.
    EN: Validates `dh_prime` and `g` against the MTProto requirements.
    """
    if not _generator_is_valid(g, prime):
        raise SecurityError(f"Invalid DH generator g={g} for the given prime")
    if prime == TELEGRAM_DH_PRIME:
        return
    if not (1 << 2047) < prime < (1 << 2048):
        raise SecurityError("DH prime must be a 2048-bit number")
    if not is_probable_prime(prime) or not is_probable_prime((prime - 1) // 2):
        raise SecurityError("DH prime must be a safe prime")


def check_dh_value(value: int, prime: int) -> None:
    """UZ: `g_a`/`g_b` oralig'ini tekshiradi: 2^(2048-64) <= qiymat <= p - 2^(2048-64).
    RU: Проверяет диапазон `g_a`/`g_b`: 2^(2048-64) <= значение <= p - 2^(2048-64).
    EN: Checks the `g_a`/`g_b` range: 2^(2048-64) <= value <= p - 2^(2048-64).
    """
    bound = 1 << (2048 - 64)
    if not (1 < value < prime - 1 and bound <= value <= prime - bound):
        raise SecurityError("DH value is outside the safe range")


def factorize(pq: int) -> tuple[int, int]:
    """UZ: `pq` ni ikki tub ko'paytuvchiga ajratadi (Pollard-Brent rho).
    RU: Раскладывает `pq` на два простых множителя (rho Полларда-Брента).
    EN: Splits `pq` into two prime factors (Pollard-Brent rho).
    """
    if pq < 4:
        raise ValueError("pq must be a product of two primes")
    if pq % 2 == 0:
        return 2, pq // 2
    while True:
        divisor = _brent(pq)
        if 1 < divisor < pq:
            low, high = sorted((divisor, pq // divisor))
            return low, high


def _brent(n: int) -> int:
    y, c, m = secrets.randbelow(n - 1) + 1, secrets.randbelow(n - 1) + 1, 128
    divisor, r, q = 1, 1, 1
    x = ys = y
    while divisor == 1:
        x = y
        for _ in range(r):
            y = (y * y + c) % n
        k = 0
        while k < r and divisor == 1:
            ys = y
            for _ in range(min(m, r - k)):
                y = (y * y + c) % n
                q = q * abs(x - y) % n
            divisor = math.gcd(q, n)
            k += m
        r *= 2
    if divisor == n:
        while True:
            ys = (ys * ys + c) % n
            divisor = math.gcd(abs(x - ys), n)
            if divisor > 1:
                break
    return divisor


__all__ = [
    "TELEGRAM_DH_PRIME",
    "check_dh_params",
    "check_dh_value",
    "factorize",
    "is_probable_prime",
]
