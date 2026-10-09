"""UZ: Test yordamchilari: soxta HTTP sessiya va update yasovchilar.
RU: Тестовые помощники: фейковая HTTP-сессия и фабрики update.
EN: Test helpers: a fake HTTP session and update factories.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import AsyncIterator
from typing import Any

from zafather.api import BaseSession, RequestPayload
from zafather.files import InputFile

TOKEN = "123456:TEST-TOKEN"
ME = {"id": 123456, "is_bot": True, "first_name": "Test", "username": "ZafatherBot"}


class SentRequest:
    def __init__(self, method: str, payload: RequestPayload, timeout: float) -> None:
        self.method = method
        self.params = payload.fields
        self.files: dict[str, InputFile] = payload.files
        self.timeout = timeout

    def __repr__(self) -> str:
        return f"SentRequest({self.method!r}, {self.params!r})"


class FakeSession(BaseSession):
    """UZ: Telegram o'rnida javob beradigan sessiya. RU: Сессия, отвечающая вместо Telegram.
    EN: A session that answers instead of Telegram.
    """

    def __init__(self) -> None:
        self.requests: list[SentRequest] = []
        self.queued: dict[str, deque[Any]] = defaultdict(deque)
        self.defaults: dict[str, Any] = {"getMe": ME, "getUpdates": []}
        self.files: dict[str, bytes] = {}
        self.closed = False

    def respond(self, method: str, *results: Any) -> None:
        """Queue results (plain values, raw response dicts or exceptions) for a method."""
        self.queued[method].extend(results)

    def fail(self, method: str, code: int, description: str, **parameters: Any) -> None:
        self.respond(
            method,
            {"ok": False, "error_code": code, "description": description, "parameters": parameters},
        )

    async def request(self, url: str, payload: RequestPayload, *, timeout: float) -> dict[str, Any]:
        method = url.rsplit("/", 1)[-1]
        self.requests.append(SentRequest(method, payload, timeout))
        queue = self.queued.get(method)
        result = queue.popleft() if queue else self.defaults.get(method, True)
        if isinstance(result, BaseException):
            raise result
        if isinstance(result, dict) and "ok" in result:
            return result
        return {"ok": True, "result": result}

    async def stream(
        self, url: str, *, timeout: float, chunk_size: int = 65536
    ) -> AsyncIterator[bytes]:
        data = self.files[url.rsplit("/", 1)[-1]]
        for index in range(0, len(data), chunk_size):
            yield data[index : index + chunk_size]

    async def close(self) -> None:
        self.closed = True

    def calls(self, method: str) -> list[SentRequest]:
        return [request for request in self.requests if request.method == method]

    def last(self, method: str | None = None) -> SentRequest:
        requests = self.calls(method) if method else self.requests
        assert requests, f"no {method or 'requests'} were sent; got {self.requests}"
        return requests[-1]


def user(user_id: int = 1, **fields: Any) -> dict[str, Any]:
    return {"id": user_id, "is_bot": False, "first_name": "Ali", "last_name": "Valiev", **fields}


def message(
    text: str | None = "hello",
    *,
    chat_id: int = 1,
    user_id: int = 1,
    message_id: int = 1,
    chat_type: str = "private",
    **fields: Any,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "message_id": message_id,
        "date": 0,
        "chat": {"id": chat_id, "type": chat_type},
        "from": user(user_id),
        **fields,
    }
    if text is not None:
        data["text"] = text
    return data


def message_update(
    text: str | None = "hello", *, update_id: int = 1, **fields: Any
) -> dict[str, Any]:
    return {"update_id": update_id, "message": message(text, **fields)}


def callback_update(
    data: str, *, chat_id: int = 1, user_id: int = 1, update_id: int = 2
) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": "cb1",
            "data": data,
            "chat_instance": "ci",
            "from": user(user_id),
            "message": message(None, chat_id=chat_id, message_id=5),
        },
    }
