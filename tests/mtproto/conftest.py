"""UZ: MTProto testlari uchun fixture'lar. RU: Фикстуры для тестов MTProto.
EN: MTProto test fixtures.
"""

from __future__ import annotations

import pytest

from tests.mtproto.fake_server import FakeTelegramServer


@pytest.fixture(scope="session")
def rsa_private_key():
    rsa = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.rsa")
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
async def server(rsa_private_key):
    fake = FakeTelegramServer(rsa_private_key)
    await fake.start()
    yield fake
    await fake.stop()
