from __future__ import annotations

import uuid
from enum import Enum

import pytest

from tests.support import FakeSession, callback_update
from zafather import CallbackData, F, Update, Zafather


class Kind(Enum):
    BOOK = "book"
    PEN = "pen"


class Action(CallbackData, prefix="act"):
    name: str
    item_id: int
    confirm: bool = False


class Other(CallbackData, prefix="oth"):
    name: str
    item_id: int


class Rich(CallbackData, prefix="r"):
    kind: Kind
    ratio: float
    token: uuid.UUID
    note: str | None = None


def test_pack_unpack_roundtrip() -> None:
    packed = Action(name="delete", item_id=42).pack()
    assert packed == "act:delete:42:0"
    restored = Action.unpack(packed)
    assert restored == Action(name="delete", item_id=42, confirm=False)
    assert restored.item_id == 42 and restored.confirm is False
    assert repr(restored) == "Action(name='delete', item_id=42, confirm=False)"


def test_typed_fields() -> None:
    token = uuid.UUID(int=1)
    packed = Rich(kind=Kind.PEN, ratio=0.5, token=token).pack()
    restored = Rich.unpack(packed)
    assert restored.kind is Kind.PEN and restored.ratio == 0.5
    assert restored.token == token and restored.note is None
    assert Rich.unpack(Rich(kind=Kind.BOOK, ratio=1, token=token, note="n").pack()).note == "n"


def test_validation_errors() -> None:
    with pytest.raises(ValueError, match="64"):
        Action(name="x" * 70, item_id=1).pack()
    with pytest.raises(ValueError, match="separator"):
        Action(name="a:b", item_id=1).pack()
    with pytest.raises(TypeError, match="missing"):
        Action(name="x")
    with pytest.raises(TypeError, match="Unknown"):
        Action(name="x", item_id=1, extra=2)
    with pytest.raises(ValueError, match="does not belong"):
        Action.unpack(Other(name="x", item_id=1).pack())
    with pytest.raises(ValueError):
        Action.unpack("act:x")
    with pytest.raises(TypeError, match="prefix"):

        class NoPrefix(CallbackData):
            value: int


async def test_filter_injects_object_and_checks_prefix() -> None:
    packed = Action(name="delete", item_id=42).pack()
    assert await Action.filter(F.name == "delete")({"data": packed}) == {
        "callback_data": Action(name="delete", item_id=42)
    }
    assert await Action.filter(F.name == "edit")({"data": packed}) is False
    assert await Other.filter()({"data": packed}) is False
    assert await Action.filter()({"data": None}) is False


async def test_filter_inside_router(app: Zafather, session: FakeSession) -> None:
    @app.callback(Action.filter(F.name == "delete"))
    async def delete(query, callback_data: Action):
        await query.answer(f"deleted {callback_data.item_id}")

    await app.feed_update(Update(callback_update(Action(name="delete", item_id=9).pack()), app.bot))
    assert session.last("answerCallbackQuery").params["text"] == "deleted 9"
