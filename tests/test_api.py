from __future__ import annotations

import datetime as dt
from enum import Enum

import pytest

from zafather import InlineKeyboard, InputFile, RichMessage
from zafather.api import NO_RETRY, PayloadBuilder, RetryPolicy, TelegramAPIServer
from zafather.exceptions import (
    BadRequest,
    Conflict,
    MigrateToChat,
    RetryAfter,
    ServerError,
    TelegramAPIError,
    TelegramError,
    api_error_from_response,
)


class Color(Enum):
    RED = "red"


def test_payload_drops_none_and_converts_objects() -> None:
    payload = PayloadBuilder().build(
        "sendMessage",
        {
            "chat_id": 1,
            "text": "hi",
            "reply_markup": InlineKeyboard().add("A", "a"),
            "disable_notification": None,
            "color": Color.RED,
            "when": dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        },
    )
    assert payload.fields == {
        "chat_id": 1,
        "text": "hi",
        "reply_markup": {"inline_keyboard": [[{"text": "A", "callback_data": "a"}]]},
        "color": "red",
        "when": 1767225600,
    }
    assert not payload.is_multipart


def test_default_parse_mode_rules() -> None:
    builder = PayloadBuilder("HTML")
    assert builder.build("sendMessage", {"text": "x"}).fields["parse_mode"] == "HTML"
    assert (
        "parse_mode" not in builder.build("sendMessage", {"text": "x", "parse_mode": None}).fields
    )
    with_entities = builder.build("sendMessage", {"text": "x", "entities": [{"type": "bold"}]})
    assert "parse_mode" not in with_entities.fields
    assert "parse_mode" not in builder.build("sendPhoto", {"photo": "id"}).fields
    assert (
        builder.build("sendPhoto", {"photo": "id", "caption": "c"}).fields["parse_mode"] == "HTML"
    )
    assert "parse_mode" not in builder.build("sendPoll", {"question": "q"}).fields
    explicit = builder.build("sendMessage", {"text": "x", "parse_mode": "MarkdownV2"})
    assert explicit.fields["parse_mode"] == "MarkdownV2"


def test_files_top_level_and_nested_attachments() -> None:
    photo = InputFile(b"img", filename="a.jpg")
    nested = InputFile(b"doc", filename="b.pdf")
    payload = PayloadBuilder("HTML").build(
        "sendMediaGroup",
        {
            "chat_id": 1,
            "thumbnail": photo,
            "media": [{"type": "document", "media": nested, "caption": "c"}],
        },
    )
    assert payload.files["thumbnail"] is photo
    assert payload.fields["media"] == [
        {"type": "document", "media": "attach://attachment1", "caption": "c", "parse_mode": "HTML"}
    ]
    assert payload.files["attachment1"] is nested
    assert payload.is_multipart


def test_rich_message_is_serialized_via_to_dict() -> None:
    payload = PayloadBuilder().build(
        "sendRichMessage", {"rich_message": RichMessage().heading("H")}
    )
    assert payload.fields["rich_message"] == {"html": "<h1>H</h1>"}


def test_server_urls() -> None:
    server = TelegramAPIServer("http://localhost:8081/")
    assert server.method_url("1:a", "getMe") == "http://localhost:8081/bot1:a/getMe"
    assert (
        server.file_url("1:a", "/photos/x.jpg") == "http://localhost:8081/file/bot1:a/photos/x.jpg"
    )
    test_env = TelegramAPIServer(test_environment=True)
    assert test_env.method_url("1:a", "getMe") == "https://api.telegram.org/bot1:a/test/getMe"


def test_retry_policy() -> None:
    policy = RetryPolicy(max_attempts=3, backoff_base=1, backoff_factor=2, max_backoff=3)
    assert [policy.backoff(attempt) for attempt in (1, 2, 3)] == [1, 2, 3]
    assert policy.can_retry(2) and not policy.can_retry(3)
    assert policy.flood_delay(5) == 5 and policy.flood_delay(61) is None
    assert policy.allows_resend("getMe", request_sent=True)
    assert not policy.allows_resend("sendMessage", request_sent=True)
    assert policy.allows_resend("sendMessage", request_sent=False)
    assert not NO_RETRY.can_retry(1)
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)


@pytest.mark.parametrize(
    ("response", "error_class"),
    [
        ({"error_code": 400, "description": "Bad"}, BadRequest),
        (
            {"error_code": 400, "description": "x", "parameters": {"migrate_to_chat_id": -100}},
            MigrateToChat,
        ),
        ({"error_code": 409, "description": "Conflict"}, Conflict),
        ({"error_code": 429, "description": "Flood", "parameters": {"retry_after": 3}}, RetryAfter),
        ({"error_code": 502, "description": "Bad Gateway"}, ServerError),
        ({"error_code": 418, "description": "teapot"}, TelegramAPIError),
    ],
)
def test_error_mapping(response: dict, error_class: type[TelegramAPIError]) -> None:
    error = api_error_from_response("sendMessage", {"ok": False, **response})
    assert type(error) is error_class
    assert isinstance(error, TelegramError)
    assert error.method == "sendMessage"


def test_error_parameters() -> None:
    error = api_error_from_response(
        "x", {"error_code": 429, "description": "", "parameters": {"retry_after": 7}}
    )
    assert error.retry_after == 7
    migrate = api_error_from_response(
        "x", {"error_code": 400, "description": "", "parameters": {"migrate_to_chat_id": -100}}
    )
    assert migrate.migrate_to_chat_id == -100
