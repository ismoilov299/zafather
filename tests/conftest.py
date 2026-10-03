"""UZ: Umumiy pytest fixture'lari. RU: Общие фикстуры pytest. EN: Shared pytest fixtures."""

from __future__ import annotations

import pytest

from tests.support import TOKEN, FakeSession
from zafather import Bot, Zafather


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def bot(session: FakeSession) -> Bot:
    return Bot(TOKEN, parse_mode="HTML", session=session)


@pytest.fixture
def app(session: FakeSession) -> Zafather:
    return Zafather(TOKEN, session=session)
