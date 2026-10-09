"""UZ: Avtorizatsiya kalitini yaratish (MTProto 2.0 Diffie-Hellman almashinuvi).
RU: Создание ключа авторизации (обмен Диффи-Хеллмана MTProto 2.0).
EN: Authorization key creation (the MTProto 2.0 Diffie-Hellman exchange).

UZ: Bosqichlar: `req_pq_multi` -> `req_DH_params` (RSA_PAD) -> `set_client_DH_params`.
RU: Этапы: `req_pq_multi` -> `req_DH_params` (RSA_PAD) -> `set_client_DH_params`.
EN: Steps: `req_pq_multi` -> `req_DH_params` (RSA_PAD) -> `set_client_DH_params`.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
import time
from collections.abc import Iterable
from dataclasses import dataclass

from .crypto import (
    PRODUCTION_KEY,
    TEST_KEY,
    AuthKey,
    RSAPublicKey,
    aes_ige_decrypt,
    aes_ige_encrypt,
    check_dh_params,
    check_dh_value,
    factorize,
    keys_by_fingerprint,
    rsa_pad_encrypt,
)
from .errors import SecurityError
from .state import MessageIds
from .tl import TLObject, TLReader, TLSerializer, default_serializer, functions, types
from .transport import Transport

_MAX_RETRIES = 5


@dataclass(frozen=True)
class AuthResult:
    """UZ: Kalit almashinuvi natijasi. RU: Результат обмена ключами. EN: The key exchange result."""

    auth_key: AuthKey
    server_salt: int
    time_offset: int


class PlainSender:
    """UZ: Shifrlanmagan MTProto xabarlari (faqat kalit almashinuvida).
    RU: Нешифрованные сообщения MTProto (только при обмене ключами).
    EN: Unencrypted MTProto messages (used only during the key exchange).
    """

    def __init__(self, transport: Transport, serializer: TLSerializer) -> None:
        self.transport = transport
        self.serializer = serializer
        self.ids = MessageIds()

    async def send(self, request: TLObject) -> TLObject:
        body = self.serializer.serialize(request)
        await self.transport.send(struct.pack("<qqi", 0, self.ids.next(), len(body)) + body)
        packet = await self.transport.receive()
        if len(packet) < 20:
            raise SecurityError("Plain message is too short")
        auth_key_id, _, length = struct.unpack_from("<qqi", packet)
        if auth_key_id != 0 or length != len(packet) - 20:
            raise SecurityError("Malformed plain message")
        result = self.serializer.deserialize(packet[20:])
        if not isinstance(result, TLObject):
            raise SecurityError("Unexpected plain response")
        return result


def _nonce_key_iv(server_nonce: bytes, new_nonce: bytes) -> tuple[bytes, bytes]:
    hash1 = hashlib.sha1(new_nonce + server_nonce).digest()
    hash2 = hashlib.sha1(server_nonce + new_nonce).digest()
    hash3 = hashlib.sha1(new_nonce + new_nonce).digest()
    return hash1 + hash2[:12], hash2[12:20] + hash3 + new_nonce[:4]


def _expect(obj: TLObject, name: str) -> TLObject:
    if obj.tl_name != name:
        raise SecurityError(f"Expected {name}, got {obj.tl_name}")
    return obj


def _check_nonces(obj: TLObject, nonce: bytes, server_nonce: bytes | None = None) -> None:
    if not hmac.compare_digest(obj.nonce, nonce):
        raise SecurityError("nonce mismatch")
    if server_nonce is not None and not hmac.compare_digest(obj.server_nonce, server_nonce):
        raise SecurityError("server_nonce mismatch")


def default_rsa_keys(test_mode: bool) -> tuple[RSAPublicKey, ...]:
    """UZ: Telegram'ning ichki RSA kalitlari. RU: Встроенные RSA-ключи Telegram.
    EN: Telegram's built-in RSA keys.
    """
    return (TEST_KEY,) if test_mode else (PRODUCTION_KEY,)


class AuthKeyGenerator:
    """UZ: Serverda yangi avtorizatsiya kalitini yaratadi.
    RU: Создаёт новый ключ авторизации на сервере.
    EN: Creates a new authorization key with the server.

    UZ: `dc_id` — `p_q_inner_data_dc` uchun: test serverlarda +10000, media DC uchun manfiy.
    RU: `dc_id` — для `p_q_inner_data_dc`: +10000 на тестовых серверах, отрицательный для
    media DC.
    EN: `dc_id` feeds `p_q_inner_data_dc`: +10000 on test servers, negative for media DCs.
    """

    def __init__(
        self,
        transport: Transport,
        *,
        dc_id: int,
        test_mode: bool = False,
        media_only: bool = False,
        rsa_keys: Iterable[RSAPublicKey] | None = None,
        serializer: TLSerializer | None = None,
    ) -> None:
        self.serializer = serializer or default_serializer()
        self.sender = PlainSender(transport, self.serializer)
        self.dc_value = (dc_id + 10000 if test_mode else dc_id) * (-1 if media_only else 1)
        self.keys = keys_by_fingerprint(rsa_keys or default_rsa_keys(test_mode))

    async def generate(self) -> AuthResult:
        nonce = os.urandom(16)
        res_pq = _expect(await self.sender.send(functions.req_pq_multi(nonce=nonce)), "resPQ")
        _check_nonces(res_pq, nonce)
        server_nonce = res_pq.server_nonce
        key = next(
            (self.keys[f] for f in res_pq.server_public_key_fingerprints if f in self.keys), None
        )
        if key is None:
            raise SecurityError("The server offered no known RSA public key")
        pq = int.from_bytes(res_pq.pq, "big")
        p, q = factorize(pq)
        new_nonce = os.urandom(32)
        inner = types.p_q_inner_data_dc(
            pq=res_pq.pq,
            p=_int_bytes(p),
            q=_int_bytes(q),
            nonce=nonce,
            server_nonce=server_nonce,
            new_nonce=new_nonce,
            dc=self.dc_value,
        )
        params = await self.sender.send(
            functions.req_DH_params(
                nonce=nonce,
                server_nonce=server_nonce,
                p=_int_bytes(p),
                q=_int_bytes(q),
                public_key_fingerprint=key.fingerprint,
                encrypted_data=rsa_pad_encrypt(key, self.serializer.serialize(inner)),
            )
        )
        _check_nonces(params, nonce, server_nonce)
        if params.tl_name == "server_DH_params_fail":
            raise SecurityError("The server rejected req_DH_params")
        _expect(params, "server_DH_params_ok")
        tmp_key, tmp_iv = _nonce_key_iv(server_nonce, new_nonce)
        server_dh = self._decrypt_server_dh(params.encrypted_answer, tmp_key, tmp_iv)
        _check_nonces(server_dh, nonce, server_nonce)
        dh_prime = int.from_bytes(server_dh.dh_prime, "big")
        g_a = int.from_bytes(server_dh.g_a, "big")
        check_dh_params(dh_prime, server_dh.g)
        check_dh_value(g_a, dh_prime)
        time_offset = server_dh.server_time - int(time.time())
        return await self._finish(
            nonce, server_nonce, new_nonce, server_dh.g, dh_prime, g_a, tmp_key, tmp_iv, time_offset
        )

    def _decrypt_server_dh(self, encrypted: bytes, tmp_key: bytes, tmp_iv: bytes) -> TLObject:
        answer = aes_ige_decrypt(encrypted, tmp_key, tmp_iv)
        reader = TLReader(answer[20:])
        server_dh = self.serializer.read(reader, types.server_DH_inner_data.definition.result)
        if not isinstance(server_dh, TLObject) or server_dh.tl_name != "server_DH_inner_data":
            raise SecurityError("Malformed server_DH_inner_data")
        if not hmac.compare_digest(
            hashlib.sha1(answer[20 : 20 + reader.position]).digest(), answer[:20]
        ):
            raise SecurityError("server_DH_inner_data hash mismatch")
        return server_dh

    async def _finish(
        self,
        nonce: bytes,
        server_nonce: bytes,
        new_nonce: bytes,
        g: int,
        dh_prime: int,
        g_a: int,
        tmp_key: bytes,
        tmp_iv: bytes,
        time_offset: int,
    ) -> AuthResult:
        retry_id = 0
        for _ in range(_MAX_RETRIES):
            b = int.from_bytes(os.urandom(256), "big")
            g_b = pow(g, b, dh_prime)
            check_dh_value(g_b, dh_prime)
            client_dh = types.client_DH_inner_data(
                nonce=nonce,
                server_nonce=server_nonce,
                retry_id=retry_id,
                g_b=g_b.to_bytes(256, "big"),
            )
            data = self.serializer.serialize(client_dh)
            with_hash = hashlib.sha1(data).digest() + data
            with_hash += os.urandom(-len(with_hash) % 16)
            answer = await self.sender.send(
                functions.set_client_DH_params(
                    nonce=nonce,
                    server_nonce=server_nonce,
                    encrypted_data=aes_ige_encrypt(with_hash, tmp_key, tmp_iv),
                )
            )
            _check_nonces(answer, nonce, server_nonce)
            auth_key = AuthKey(pow(g_a, b, dh_prime).to_bytes(256, "big"))
            outcome = {"dh_gen_ok": 1, "dh_gen_retry": 2, "dh_gen_fail": 3}.get(answer.tl_name)
            if outcome is None:
                raise SecurityError(f"Unexpected {answer.tl_name}")
            received = answer.values[f"new_nonce_hash{outcome}"]
            if not hmac.compare_digest(received, auth_key.new_nonce_hash(new_nonce, outcome)):
                raise SecurityError("new_nonce_hash mismatch")
            if outcome == 1:
                salt = int.from_bytes(
                    bytes(a ^ b for a, b in zip(new_nonce[:8], server_nonce[:8], strict=True)),
                    "little",
                    signed=True,
                )
                return AuthResult(auth_key, salt, time_offset)
            if outcome == 3:
                raise SecurityError("The server failed to create the authorization key")
            retry_id = int.from_bytes(auth_key.aux_hash, "little", signed=True)
        raise SecurityError("Too many dh_gen_retry answers")


def _int_bytes(value: int) -> bytes:
    return value.to_bytes((value.bit_length() + 7) // 8, "big")


__all__ = ["AuthKeyGenerator", "AuthResult", "PlainSender", "default_rsa_keys"]
