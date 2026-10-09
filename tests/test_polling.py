from __future__ import annotations

import asyncio

import pytest

from tests.support import FakeSession, message_update
from zafather import Bot, LongPolling, NetworkError, Unauthorized, Update
from zafather.api import RetryPolicy

NO_WAIT = RetryPolicy(backoff_base=0)


async def run_until(polling: LongPolling, condition, timeout: float = 5) -> None:
    task = asyncio.create_task(polling.run())
    for _ in range(int(timeout / 0.005)):
        if condition():
            break
        await asyncio.sleep(0.005)
    polling.stop()
    await asyncio.wait_for(task, timeout=timeout)


async def test_offsets_and_dispatch(bot: Bot, session: FakeSession) -> None:
    received: list[int] = []

    async def handle(update: Update) -> None:
        received.append(update.update_id)

    session.respond(
        "getUpdates",
        [message_update("a", update_id=5), message_update("b", update_id=6)],
        [message_update("c", update_id=7)],
    )
    polling = LongPolling(bot, handle, timeout=0, backoff=NO_WAIT)
    await run_until(polling, lambda: len(received) == 3)
    assert received == [5, 6, 7]
    offsets = [request.params.get("offset") for request in session.calls("getUpdates")]
    assert offsets[:3] == [None, 7, 8]
    assert session.calls("getUpdates")[0].params["allowed_updates"][0] == "message"


async def test_errors_back_off_and_recover(session: FakeSession) -> None:
    bot = Bot("123456:TEST-TOKEN", session=session, retry=RetryPolicy(max_attempts=1))
    received: list[int] = []

    async def handle(update: Update) -> None:
        received.append(update.update_id)

    session.respond("getUpdates", NetworkError("down"), [message_update(update_id=1)])
    session.fail("getUpdates", 409, "Conflict: another getUpdates")
    polling = LongPolling(bot, handle, timeout=0, backoff=NO_WAIT, concurrent=False)
    await run_until(polling, lambda: received == [1])
    assert received == [1]


async def test_unauthorized_is_fatal(bot: Bot, session: FakeSession) -> None:
    session.fail("getUpdates", 401, "Unauthorized")
    with pytest.raises(Unauthorized):
        await LongPolling(bot, lambda update: asyncio.sleep(0), timeout=0).run()


async def test_stop_cancels_pending_request(bot: Bot, session: FakeSession) -> None:
    started = asyncio.Event()
    original_request = session.request

    async def slow_get_updates(url, payload, *, timeout):
        if not url.endswith("/getUpdates"):
            return await original_request(url, payload, timeout=timeout)
        started.set()
        await asyncio.sleep(60)
        raise AssertionError("must be cancelled")

    session.request = slow_get_updates  # type: ignore[method-assign]
    polling = LongPolling(bot, lambda update: asyncio.sleep(0), timeout=50)
    task = asyncio.create_task(polling.run())
    await asyncio.wait_for(started.wait(), timeout=1)
    polling.stop()
    await asyncio.wait_for(task, timeout=1)
    assert not polling.running


async def test_drains_running_handlers_on_stop(bot: Bot, session: FakeSession) -> None:
    finished: list[int] = []

    async def handle(update: Update) -> None:
        await asyncio.sleep(0.05)
        finished.append(update.update_id)

    session.respond("getUpdates", [message_update(update_id=1), message_update(update_id=2)])
    polling = LongPolling(bot, handle, timeout=0, max_concurrent=1)
    await run_until(polling, lambda: len(session.calls("getUpdates")) >= 2)
    assert finished == [1, 2]


async def test_handler_crash_does_not_stop_polling(bot: Bot, session: FakeSession, caplog) -> None:
    calls: list[int] = []

    async def handle(update: Update) -> None:
        calls.append(update.update_id)
        raise RuntimeError("bug")

    session.respond("getUpdates", [message_update(update_id=1)], [message_update(update_id=2)])
    polling = LongPolling(bot, handle, timeout=0)
    await run_until(polling, lambda: calls == [1, 2])
    assert calls == [1, 2] and "Failed to process update" in caplog.text


async def test_cannot_run_twice(bot: Bot) -> None:
    polling = LongPolling(bot, lambda update: asyncio.sleep(0))
    polling._running = True
    with pytest.raises(RuntimeError):
        await polling.run()
