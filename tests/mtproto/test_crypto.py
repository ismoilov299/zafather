from __future__ import annotations

import hashlib
import os
import secrets

import pytest

from zafather.mtproto.crypto import (
    PRODUCTION_KEY,
    TELEGRAM_DH_PRIME,
    TEST_KEY,
    AuthKey,
    RSAPublicKey,
    aes_ige_decrypt,
    aes_ige_encrypt,
    check_dh_params,
    check_dh_value,
    compute_srp_answer,
    factorize,
    is_probable_prime,
    password_hash,
    rsa_pad_encrypt,
)
from zafather.mtproto.errors import SecurityError


def test_aes_ige_reference_vectors() -> None:
    first = aes_ige_encrypt(bytes(32), bytes(range(16)), bytes(range(32)))
    assert first.hex() == "1a8519a6557be652e9da8e43da4ef4453cf456b4ca488aa383c79c98b34797cb"
    plain = bytes.fromhex("99706487a1cde613bc6de0b6f24b1c7aa448c8b9c3403e3467a8cad89340f53b")
    second = aes_ige_encrypt(plain, b"This is an imple", b"mentation of IGE mode for OpenSSL"[:32])
    assert second == b"L. Let's hope Ben got it right!\n"
    key, iv, data = os.urandom(32), os.urandom(32), os.urandom(64)
    assert aes_ige_decrypt(aes_ige_encrypt(data, key, iv), key, iv) == data
    with pytest.raises(ValueError):
        aes_ige_encrypt(b"x" * 15, key, iv)
    with pytest.raises(ValueError):
        aes_ige_encrypt(b"x" * 16, key, b"short")


def test_known_rsa_fingerprints() -> None:
    assert PRODUCTION_KEY.fingerprint & 0xFFFFFFFFFFFFFFFF == 0xD09D1D85DE64FD85
    assert TEST_KEY.fingerprint & 0xFFFFFFFFFFFFFFFF == 0xB25898DF208D2603
    assert PRODUCTION_KEY.size == 256
    with pytest.raises(ValueError):
        RSAPublicKey.from_pem("-----BEGIN RSA PUBLIC KEY-----\nAAAA\n-----END RSA PUBLIC KEY-----")


def test_rsa_pad_round_trip(rsa_private_key) -> None:
    numbers = rsa_private_key.private_numbers()
    key = RSAPublicKey(numbers.public_numbers.n, numbers.public_numbers.e)
    data = os.urandom(100)
    encrypted = rsa_pad_encrypt(key, data)
    assert len(encrypted) == 256
    key_aes_encrypted = pow(int.from_bytes(encrypted, "big"), numbers.d, key.n).to_bytes(256, "big")
    temp_key_xor, aes_encrypted = key_aes_encrypted[:32], key_aes_encrypted[32:]
    digest = hashlib.sha256(aes_encrypted).digest()
    temp_key = bytes(a ^ b for a, b in zip(temp_key_xor, digest, strict=True))
    data_with_hash = aes_ige_decrypt(aes_encrypted, temp_key, bytes(32))
    data_with_padding = data_with_hash[:192][::-1]
    assert hashlib.sha256(temp_key + data_with_padding).digest() == data_with_hash[192:]
    assert data_with_padding[:100] == data
    with pytest.raises(ValueError):
        rsa_pad_encrypt(key, b"x" * 145)
    with pytest.raises(ValueError):
        key.encrypt_raw(b"\xff" * 300)


def test_factorize() -> None:
    assert factorize(0x17ED48941A08F981) == (0x494C553B, 0x53911073)
    assert factorize(2 * 7919) == (2, 7919)
    for _ in range(3):
        p, q = sorted(_random_prime(31) for _ in range(2))
        assert factorize(p * q) == (p, q)
    with pytest.raises(ValueError):
        factorize(3)


def _random_prime(bits: int) -> int:
    while True:
        candidate = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if is_probable_prime(candidate):
            return candidate


def test_dh_checks() -> None:
    check_dh_params(TELEGRAM_DH_PRIME, 3)
    with pytest.raises(SecurityError):
        check_dh_params(TELEGRAM_DH_PRIME, 2)
    with pytest.raises(SecurityError):
        check_dh_params(TELEGRAM_DH_PRIME + 2, 4)
    with pytest.raises(SecurityError):
        check_dh_params(23, 4)
    check_dh_value(pow(3, 12345678901234567890, TELEGRAM_DH_PRIME), TELEGRAM_DH_PRIME)
    for bad in (1, 2, TELEGRAM_DH_PRIME - 1, 1 << 1000):
        with pytest.raises(SecurityError):
            check_dh_value(bad, TELEGRAM_DH_PRIME)
    assert is_probable_prime(TELEGRAM_DH_PRIME) and is_probable_prime((TELEGRAM_DH_PRIME - 1) // 2)
    assert not is_probable_prime(1) and is_probable_prime(2) and not is_probable_prime(91)


def test_auth_key_directions_and_tampering() -> None:
    key = AuthKey(os.urandom(256))
    plaintext = os.urandom(64)
    from_client = key.encrypt(plaintext, from_client=True)
    assert from_client[:8] == key.id and key.decrypt(from_client, from_client=True) == plaintext
    with pytest.raises(SecurityError, match="msg_key"):
        key.decrypt(from_client, from_client=False)
    tampered = bytearray(from_client)
    tampered[-1] ^= 1
    with pytest.raises(SecurityError):
        key.decrypt(bytes(tampered), from_client=True)
    with pytest.raises(SecurityError, match="auth_key_id"):
        AuthKey(os.urandom(256)).decrypt(from_client, from_client=True)
    with pytest.raises(SecurityError, match="length"):
        key.decrypt(b"x" * 30)
    with pytest.raises(ValueError):
        key.encrypt(b"x" * 15)
    with pytest.raises(ValueError):
        AuthKey(b"short")
    assert key == AuthKey(key.key) and "AuthKey" in repr(key)
    new_nonce = os.urandom(32)
    expected = hashlib.sha1(new_nonce + b"\x01" + hashlib.sha1(key.key).digest()[:8]).digest()[4:20]
    assert key.new_nonce_hash(new_nonce, 1) == expected


def test_srp_answer_matches_server_side_check() -> None:
    password = "maxfiy-parol"
    salt1, salt2 = os.urandom(40), os.urandom(16)
    p, g = TELEGRAM_DH_PRIME, 3
    p_bytes, g_bytes = p.to_bytes(256, "big"), g.to_bytes(256, "big")
    x = int.from_bytes(password_hash(password, salt1, salt2), "big")
    v = pow(g, x, p)
    k = int.from_bytes(hashlib.sha256(p_bytes + g_bytes).digest(), "big")
    b = secrets.randbits(2048)
    srp_b = (k * v + pow(g, b, p)) % p
    answer = compute_srp_answer(
        password, salt1=salt1, salt2=salt2, g=g, p=p_bytes, srp_b=srp_b.to_bytes(256, "big")
    )
    a_value = int.from_bytes(answer.a_bytes, "big")
    u = int.from_bytes(hashlib.sha256(answer.a_bytes + srp_b.to_bytes(256, "big")).digest(), "big")
    shared = pow(a_value * pow(v, u, p) % p, b, p)
    k_s = hashlib.sha256(shared.to_bytes(256, "big")).digest()
    hashed = bytes(
        a ^ c
        for a, c in zip(
            hashlib.sha256(p_bytes).digest(), hashlib.sha256(g_bytes).digest(), strict=True
        )
    )
    expected = hashlib.sha256(
        hashed
        + hashlib.sha256(salt1).digest()
        + hashlib.sha256(salt2).digest()
        + answer.a_bytes
        + srp_b.to_bytes(256, "big")
        + k_s
    ).digest()
    assert answer.m1 == expected
    with pytest.raises(SecurityError):
        compute_srp_answer(password, salt1=salt1, salt2=salt2, g=g, p=p_bytes, srp_b=bytes(256))
    with pytest.raises(SecurityError):
        compute_srp_answer(
            password,
            salt1=salt1,
            salt2=salt2,
            g=g,
            p=p_bytes,
            srp_b=srp_b.to_bytes(256, "big"),
            secret_a=1,
        )
