from __future__ import annotations

import json

import pytest

from zafather import (
    FSMContext,
    FSMStrategy,
    JSONStorage,
    MemoryStorage,
    RedisStorage,
    State,
    StatesGroup,
)
from zafather.fsm import StorageKey

KEY = StorageKey(bot_id=1, chat_id=10, user_id=20)


class Form(StatesGroup):
    name = State()
    age = State()
    custom = State("renamed")


def test_states_group() -> None:
    assert Form.name.state == "Form:name" and str(Form.custom) == "Form:renamed"
    assert Form.all() == (Form.name, Form.age, Form.custom)
    assert list(Form) == [Form.name, Form.age, Form.custom]
    assert Form.name == "Form:name" and "Form:age" in Form
    assert hash(Form.name) == hash("Form:name")
    assert State().state == "state"


def test_storage_key_roundtrip() -> None:
    assert StorageKey.from_string(KEY.to_string()) == KEY
    topic = StorageKey(1, 2, 3, 4)
    assert topic.to_string() == "1:2:3:4" and StorageKey.from_string("1:2:3:4") == topic
    with pytest.raises(ValueError):
        StorageKey.from_string("1:2")


@pytest.mark.parametrize(
    ("strategy", "expected"),
    [
        (FSMStrategy.USER_IN_CHAT, StorageKey(1, 10, 20)),
        (FSMStrategy.CHAT, StorageKey(1, 10, 10)),
        (FSMStrategy.GLOBAL_USER, StorageKey(1, 20, 20)),
        (FSMStrategy.USER_IN_TOPIC, StorageKey(1, 10, 20, 5)),
        (FSMStrategy.CHAT_TOPIC, StorageKey(1, 10, 10, 5)),
    ],
)
def test_strategies(strategy: FSMStrategy, expected: StorageKey) -> None:
    assert strategy.build_key(1, 10, 20, 5) == expected


async def test_memory_storage_isolates_copies() -> None:
    storage = MemoryStorage()
    context = FSMContext(storage, KEY)
    await context.set_state(Form.name)
    await context.set_data({"items": [1]})
    data = await context.get_data()
    data["items"].append(2)
    assert await context.get_data() == {"items": [1]}
    assert await context.update_data(extra=True) == {"items": [1], "extra": True}
    assert await context.get_state() == "Form:name"
    await context.clear()
    assert await context.get_state() is None and await context.get_data() == {}
    other = FSMContext(storage, StorageKey(2, 10, 20))
    assert await other.get_state() is None


async def test_json_storage_persists_atomically(tmp_path) -> None:
    path = tmp_path / "state.json"
    storage = JSONStorage(path)
    context = FSMContext(storage, KEY)
    await context.set_state("Form:age")
    await context.update_data(name="Ali")
    reloaded = FSMContext(JSONStorage(path), KEY)
    assert await reloaded.get_state() == "Form:age"
    assert await reloaded.get_data() == {"name": "Ali"}
    assert json.loads(path.read_text())["version"] == 2
    assert not (tmp_path / "state.json.tmp").exists()


async def test_json_storage_migrates_legacy_files(tmp_path) -> None:
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"states": {"10:20": "Form:name"}, "data": {"10:20": {"a": 1}}}))
    storage = JSONStorage(path)
    context = FSMContext(storage, KEY)
    assert await context.get_state() == "Form:name"
    assert await context.get_data() == {"a": 1}
    await context.set_state(None)
    assert json.loads(path.read_text())["states"] == {}


async def test_json_storage_ignores_corrupted_file(tmp_path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json")
    assert await JSONStorage(path).get_state(KEY) is None


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expiry: dict[str, int | None] = {}
        self.closed = False

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value
        self.expiry[key] = ex

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)

    async def aclose(self) -> None:
        self.closed = True


async def test_redis_storage_with_injected_client() -> None:
    client = FakeRedis()
    storage = RedisStorage(client=client, prefix="bot", ttl=60)
    context = FSMContext(storage, KEY)
    await context.set_state(Form.age)
    await context.set_data(name="Vali")
    assert client.values["bot:state:1:10:20"] == "Form:age"
    assert json.loads(client.values["bot:data:1:10:20"]) == {"name": "Vali"}
    assert client.expiry["bot:state:1:10:20"] == 60
    assert await context.get_state() == "Form:age" and await context.get_data() == {"name": "Vali"}
    await context.clear()
    assert client.values == {}
    await storage.close()
    assert client.closed


def test_redis_storage_from_url() -> None:
    storage = RedisStorage("redis://localhost:6379/0")
    assert storage.client is not None
