from __future__ import annotations

import base64
import json
import time
from urllib.parse import urlencode

import aiohttp
import pytest

from tests.support import TOKEN, FakeSession, message_update
from zafather import (
    MiniAppServer,
    Update,
    WebAppAuthError,
    WebAppData,
    Zafather,
    attach_link,
    direct_link,
    is_valid,
    main_app_link,
    parse_init_data,
    validate,
    validate_third_party,
)
from zafather.types import Message
from zafather.webapp import MiniApp, data_check_string, sign_init_data

USER = {"id": 279058397, "first_name": "Ali", "username": "ali", "is_premium": True}


def test_validation_accepts_signed_data() -> None:
    init = sign_init_data({"query_id": "AAH123", "user": USER, "start_param": "promo7"}, TOKEN)
    data = validate(init, TOKEN)
    assert (
        data.user.id == 279058397 and data.user.username == "ali" and data.user.full_name == "Ali"
    )
    assert data.start_param == "promo7" and data.query_id == "AAH123"
    assert data.user_id == 279058397 and data.age < 5 and "user" in data
    assert parse_init_data(init).user.id == 279058397


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda init: init.replace("279058397", "111111111"), "hash mismatch"),
        (lambda init: "user=%7B%7D&auth_date=1", "no hash"),
        (lambda init: "", "empty"),
        (lambda init: "%%%", "Malformed"),
    ],
)
def test_validation_rejects_tampering(mutate, message: str) -> None:
    init = sign_init_data({"user": USER}, TOKEN)
    with pytest.raises(WebAppAuthError, match=message):
        validate(mutate(init), TOKEN)


def test_validation_checks_token_and_age() -> None:
    init = sign_init_data({"user": USER}, TOKEN)
    assert not is_valid(init, "999999:OTHER")
    old = sign_init_data({"user": USER, "auth_date": int(time.time()) - 7200}, TOKEN)
    with pytest.raises(WebAppAuthError, match="expired"):
        validate(old, TOKEN, max_age=3600)
    assert is_valid(old, TOKEN, max_age=0)


def test_third_party_validation() -> None:
    serialization = pytest.importorskip("cryptography.hazmat.primitives.serialization")
    ed25519 = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    private = ed25519.Ed25519PrivateKey.generate()
    public_hex = (
        private.public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )
    payload = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": 7, "first_name": "Vali"}, separators=(",", ":")),
    }
    message = f"123456:WebAppData\n{data_check_string(payload.items())}".encode()
    signature = base64.urlsafe_b64encode(private.sign(message)).decode().rstrip("=")
    good = urlencode({**payload, "signature": signature})
    assert validate_third_party(good, 123456, public_key=public_hex).user.first_name == "Vali"
    forged = urlencode({**payload, "user": '{"id":8}', "signature": signature})
    with pytest.raises(WebAppAuthError):
        validate_third_party(forged, 123456, public_key=public_hex)
    with pytest.raises(WebAppAuthError, match="no signature"):
        validate_third_party(urlencode(payload), 123456, public_key=public_hex)


def test_links() -> None:
    assert direct_link("MyBot", "shop", "ref_42", mode="fullscreen") == (
        "https://t.me/MyBot/shop?startapp=ref_42&mode=fullscreen"
    )
    assert direct_link("@MyBot", "shop") == "https://t.me/MyBot/shop"
    assert main_app_link("@MyBot", "ref 42") == "https://t.me/MyBot?startapp=ref%2042"
    assert attach_link("MyBot", "x") == "https://t.me/MyBot?attach=MyBot&startattach=x"


async def test_web_app_data_filter() -> None:
    raw = message_update(None)
    raw["message"]["web_app_data"] = {"data": '{"a": 1}', "button_text": "Open"}
    event = Update(raw).event
    assert await WebAppData()(event) == {"web_app_data": {"a": 1}, "web_app_button": "Open"}
    assert await WebAppData("Other")(event) is False
    assert await WebAppData()(Message({"message_id": 1})) is False


async def test_mini_app_methods(app: Zafather, session: FakeSession) -> None:
    mini_app = app.mini_app
    assert isinstance(mini_app, MiniApp) and app.mini_app is mini_app
    await mini_app.set_menu_button("Open", "https://app")
    assert session.last().params["menu_button"] == {
        "type": "web_app",
        "text": "Open",
        "web_app": {"url": "https://app"},
    }
    await mini_app.answer_text("q1", "Done", id="1")
    sent = session.last("answerWebAppQuery").params
    assert (
        sent["web_app_query_id"] == "q1"
        and sent["result"]["input_message_content"]["message_text"] == "Done"
    )
    await mini_app.set_emoji_status(5, "777")
    assert session.last().params == {"user_id": 5, "emoji_status_custom_emoji_id": "777"}
    init = sign_init_data({"user": USER}, TOKEN)
    assert app.validate_init_data(init).user_id == USER["id"]


async def test_mini_app_server(session: FakeSession, unused_tcp_port: int) -> None:
    app = Zafather(TOKEN, session=session)
    server = MiniAppServer(
        app, port=unused_tcp_port, host="127.0.0.1", cors_origins=["https://web.app"]
    )

    @server.api("/me")
    async def me(user, init):
        return {"id": user.id, "name": user.full_name, "start": init.start_param}

    @server.api("/notify")
    async def notify(user, data, bot):
        await bot.call("sendMessage", chat_id=user.id, text=data.get("text", ""))
        return {"sent": True}

    @server.api("/raw")
    def raw(**kwargs):
        return {"keys": sorted(kwargs)}

    @server.api("/broken")
    async def broken():
        raise RuntimeError("bug")

    server.add_webhook("/hook", secret_token="abc")

    @app.message()
    async def on_message(message):
        await message.answer("webhook ok")

    await server.start()
    init = sign_init_data(
        {"user": {"id": 42, "first_name": "Ali", "last_name": "Valiev"}, "start_param": "ref9"},
        TOKEN,
    )
    base = f"http://127.0.0.1:{unused_tcp_port}"
    headers = {"X-Telegram-Init-Data": init}
    try:
        async with aiohttp.ClientSession() as client:
            async with client.post(f"{base}/api/me", headers=headers, json={}) as response:
                body = await response.json()
            assert response.status == 200 and body == {
                "ok": True,
                "id": 42,
                "name": "Ali Valiev",
                "start": "ref9",
            }
            async with client.post(f"{base}/api/me", json={}) as response:
                assert response.status == 401 and (await response.json())["ok"] is False
            async with client.post(
                f"{base}/api/me", headers={"Authorization": f"tma {init}"}
            ) as response:
                assert response.status == 200
            async with client.post(
                f"{base}/api/notify", headers=headers, json={"text": "salom"}
            ) as response:
                assert (await response.json())["sent"] is True
            assert session.last("sendMessage").params == {
                "chat_id": 42,
                "text": "salom",
                "parse_mode": "HTML",
            }
            async with client.get(f"{base}/api/raw", headers=headers) as response:
                assert (await response.json())["keys"] == [
                    "app",
                    "bot",
                    "data",
                    "init",
                    "request",
                    "user",
                ]
            async with client.post(f"{base}/api/broken", headers=headers) as response:
                assert response.status == 500
            async with client.options(
                f"{base}/api/me", headers={"Origin": "https://web.app"}
            ) as response:
                assert response.status == 204
                assert response.headers["Access-Control-Allow-Origin"] == "https://web.app"
            hook_headers = {"X-Telegram-Bot-Api-Secret-Token": "abc"}
            async with client.post(
                f"{base}/hook", json=message_update("x"), headers=hook_headers
            ) as response:
                assert response.status == 200
    finally:
        await server.stop()
    assert session.last("sendMessage").params["text"] == "webhook ok"
    assert repr(server).startswith("<MiniAppServer 127.0.0.1")
