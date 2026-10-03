from __future__ import annotations

import io

import pytest

from tests.support import TOKEN, FakeSession
from zafather import Bot, NetworkError, RetryAfter, TelegramAPIServer, Unauthorized
from zafather.api import RetryPolicy
from zafather.types import File, Message, User

FAST_RETRY = RetryPolicy(max_attempts=3, backoff_base=0, max_flood_wait=5)


def test_token_validation() -> None:
    with pytest.raises(ValueError):
        Bot("not-a-token")
    assert Bot(TOKEN).id == 123456


async def test_snake_case_proxy_and_wrapping(bot: Bot, session: FakeSession) -> None:
    session.respond(
        "sendMessage", {"message_id": 7, "date": 0, "chat": {"id": 5, "type": "private"}}
    )
    sent = await bot.send_message(chat_id=5, text="hi")
    assert isinstance(sent, Message) and sent.message_id == 7 and sent.get_bot() is bot
    request = session.last("sendMessage")
    assert request.params == {"chat_id": 5, "text": "hi", "parse_mode": "HTML"}


async def test_me_is_cached(bot: Bot, session: FakeSession) -> None:
    first = await bot.me()
    second = await bot.me()
    assert isinstance(first, User) and first is second and first.username == "ZafatherBot"
    assert len(session.calls("getMe")) == 1


async def test_raises_typed_api_errors(bot: Bot, session: FakeSession) -> None:
    session.fail("getChat", 401, "Unauthorized")
    with pytest.raises(Unauthorized):
        await bot.get_chat(chat_id=1)


async def test_flood_wait_is_retried(session: FakeSession) -> None:
    bot = Bot(TOKEN, session=session, retry=FAST_RETRY)
    session.fail("sendMessage", 429, "Too Many Requests", retry_after=0)
    session.respond("sendMessage", True)
    assert await bot.call("sendMessage", chat_id=1, text="x") is True
    assert len(session.calls("sendMessage")) == 2


async def test_long_flood_wait_is_raised(session: FakeSession) -> None:
    bot = Bot(TOKEN, session=session, retry=FAST_RETRY)
    session.fail("sendMessage", 429, "Too Many Requests", retry_after=999)
    with pytest.raises(RetryAfter) as caught:
        await bot.call("sendMessage", chat_id=1, text="x")
    assert caught.value.retry_after == 999


async def test_network_errors_only_resend_safe_requests(session: FakeSession) -> None:
    bot = Bot(TOKEN, session=session, retry=FAST_RETRY)
    session.respond("getChat", NetworkError("reset"), {"id": 1})
    assert (await bot.call("getChat", chat_id=1)) == {"id": 1}

    session.respond("sendMessage", NetworkError("timeout"))
    with pytest.raises(NetworkError):
        await bot.call("sendMessage", chat_id=1, text="x")
    assert len(session.calls("sendMessage")) == 1

    session.respond("sendMessage", NetworkError("refused", request_sent=False), True)
    assert await bot.call("sendMessage", chat_id=1, text="x") is True


async def test_server_errors_retry_reads_only(session: FakeSession) -> None:
    bot = Bot(TOKEN, session=session, retry=FAST_RETRY)
    session.fail("getMe", 502, "Bad Gateway")
    assert (await bot.me()).id == 123456
    session.fail("sendMessage", 502, "Bad Gateway")
    with pytest.raises(Exception, match="Bad Gateway"):
        await bot.call("sendMessage", chat_id=1, text="x")


async def test_get_updates_timeout_includes_long_poll(bot: Bot, session: FakeSession) -> None:
    session.respond("getUpdates", [])
    await bot.call("getUpdates", timeout=30)
    assert session.last("getUpdates").timeout == bot.timeout + 30


async def test_download_to_memory_stream_and_path(bot: Bot, session: FakeSession, tmp_path) -> None:
    session.files["photo.jpg"] = b"x" * 70000
    session.respond("getFile", {"file_id": "f", "file_unique_id": "u", "file_path": "photo.jpg"})
    assert await bot.download("f") == b"x" * 70000

    session.respond("getFile", {"file_id": "f", "file_unique_id": "u", "file_path": "photo.jpg"})
    buffer = io.BytesIO()
    await bot.download("f", buffer)
    assert buffer.getvalue() == b"x" * 70000

    target = tmp_path / "out.jpg"
    await bot.download(File({"file_id": "f", "file_path": "photo.jpg"}), target)
    assert target.read_bytes() == b"x" * 70000
    assert len(session.calls("getFile")) == 2


async def test_download_from_local_server(tmp_path, session: FakeSession) -> None:
    source = tmp_path / "local.bin"
    source.write_bytes(b"local")
    bot = Bot(TOKEN, api_url=TelegramAPIServer("http://localhost", is_local=True), session=session)
    session.respond("getFile", {"file_id": "f", "file_unique_id": "u", "file_path": str(source)})
    assert await bot.download("f") == b"local"


async def test_close_only_owned_session(session: FakeSession) -> None:
    await Bot(TOKEN, session=session).close()
    assert session.closed is False


async def test_explicit_helpers(bot: Bot, session: FakeSession) -> None:
    await bot.answer_pre_checkout_query("q1")
    assert session.last().params == {"pre_checkout_query_id": "q1", "ok": True}
    await bot.send_rich(5, {"html": "<p>x</p>"})
    assert session.last("sendRichMessage").params["rich_message"] == {"html": "<p>x</p>"}
    assert bot.stream_rich(5).chat_id == 5
    assert repr(bot) == "<Bot id=123456>"
