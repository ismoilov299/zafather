"""UZ: `examples/` dagi namunalar oflayn ishga tushiriladi (hujjat eskirmasligi uchun).
RU: Примеры из `examples/` запускаются офлайн (чтобы документация не устаревала).
EN: The `examples/` scripts are exercised offline so the documentation cannot drift.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import zafather.bot
from tests.support import FakeSession, callback_update, message, message_update
from zafather import Update

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> FakeSession:
    fake = FakeSession()
    monkeypatch.setattr(zafather.bot, "AiohttpSession", lambda: fake)
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST-TOKEN")
    return fake


def load(relative: str) -> ModuleType:
    path = EXAMPLES / relative
    spec = importlib.util.spec_from_file_location(f"example_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def feed(module: ModuleType, raw: dict[str, Any]) -> None:
    app = module.bot
    await app.feed_update(Update(raw, app.bot))


def texts(session: FakeSession) -> list[str]:
    return [request.params["text"] for request in session.calls("sendMessage")]


async def test_echo_bot(session: FakeSession) -> None:
    module = load("echo_bot.py")
    await feed(module, message_update("/start"))
    await feed(module, message_update("salom", update_id=2))
    assert texts(session) == [
        "Salom, <b>Ali</b>! Menga xohlagan matnni yozing.",
        "salom",
    ]


async def test_full_bot_questionnaire(session: FakeSession) -> None:
    module = load("full_bot.py")
    await feed(module, message_update("/start"))
    await feed(module, callback_update("menu:anketa"))
    for update_id, text in enumerate(("Ali", "abc", "20", "Toshkent"), start=10):
        await feed(module, message_update(text, update_id=update_id))
    sent = texts(session)
    assert sent[0].startswith("Assalomu alaykum, <b>Ali</b>!")
    assert sent[1:] == [
        "Ismingizni yozing:",
        "Yoshingiz nechida?",
        "Yoshni faqat raqam bilan yozing 🙂",
        "Qaysi shahardansiz?",
        "✅ Anketa qabul qilindi:\n👤 Ali\n🎂 20\n🏙 Toshkent",
    ]
    assert session.last("sendMessage").params["reply_markup"]["remove_keyboard"] is True
    await feed(module, callback_update("menu:info", update_id=30))
    assert session.last("editMessageText").params["text"].startswith("Bu bot <b>Zafather</b>")


async def test_full_bot_admin_media_and_errors(
    session: FakeSession, caplog: pytest.LogCaptureFixture
) -> None:
    module = load("full_bot.py")
    await feed(module, message_update("/stats"))
    assert texts(session)[-1] == "Bu buyruq faqat adminlar uchun."
    await feed(module, message_update("/stats", update_id=2, user_id=123456789))
    assert texts(session)[-1] == "Statistika: bot ishlayapti ✅"
    photo = message(None, photo=[{"file_id": "a", "file_unique_id": "a", "width": 1, "height": 1}])
    await feed(module, {"update_id": 3, "message": photo})
    assert texts(session)[-1] == "Rasm qabul qilindi (1 o'lchamda)."
    session.fail("sendMessage", 400, "Bad Request: chat not found")
    with caplog.at_level(logging.ERROR):
        await feed(module, message_update("/start", update_id=4))
    assert any("chat not found" in record.getMessage() for record in caplog.records)


async def test_api102_bot(session: FakeSession) -> None:
    module = load("api102_bot.py")
    await feed(module, message_update("/start"))
    markup = session.last("sendMessage").params["reply_markup"]
    styles = [button.get("style") for row in markup["inline_keyboard"] for button in row]
    assert styles[:3] == ["success", "danger", "primary"]
    await feed(module, message_update("/emoji", update_id=2))
    assert session.last("sendMessage").params["entities"]
    await feed(module, message_update("/secret", update_id=3, chat_type="group", chat_id=-5))
    assert "ephemeral_message_parameters" in session.last("sendMessage").params
    await feed(module, message_update("/like", update_id=4))
    assert session.last().method == "setMessageReaction"
    await feed(module, message_update("/newbot", update_id=5))
    assert "t.me/newbot/" in str(session.calls("sendMessage")[-2].params["reply_markup"])
    await feed(module, callback_update("act:main", update_id=6))
    assert session.last("answerCallbackQuery").params["text"] == "Tanlandi: main"


async def test_rich_bot(session: FakeSession) -> None:
    module = load("rich_bot.py")
    await feed(module, message_update("/report"))
    html = session.last("sendRichMessage").params["rich_message"]["html"]
    assert "Avgust hisoboti" in html and "<table" in html
    await feed(module, message_update("/ask", update_id=2))
    assert "/ask Zafather nima?" in texts(session)[-1]
    await feed(module, message_update("/thinking", update_id=3))
    assert "thinking" in session.last("sendRichMessage").params["rich_message"]["html"]


async def test_miniapp_bot(session: FakeSession) -> None:
    module = load("miniapp/bot.py")
    await feed(module, message_update("/start"))
    buttons = session.last("sendMessage").params["reply_markup"]["inline_keyboard"]
    assert buttons[0][0]["web_app"] == {"url": "https://example.com"}
    data = message(None, web_app_data={"data": '{"a": 1}', "button_text": "Yuborish"})
    await feed(module, {"update_id": 2, "message": data})
    assert texts(session)[-1] == "Ilovadan keldi: <code>{'a': 1}</code>"
    paths = {resource.canonical for resource in module.server.web.router.resources()}
    assert paths >= {"/api/me", "/api/click", "/api/notify"}
