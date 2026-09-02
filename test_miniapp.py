"""Zafather — Mini App testlari (Telegram'ga ulanmasdan)."""
import asyncio
import base64
import json
import sys
import time
from urllib.parse import urlencode

import aiohttp

from zafather import (
    MiniAppServer,
    WebAppAuthError,
    Zafather,
    direct_link,
    is_valid,
    main_app_link,
    parse_init_data,
    validate,
    validate_third_party,
)
from zafather.webapp import _check_string, sign

TOKEN = "123456:AA-TEST-TOKEN"
PORT = 8099

ok = fail = 0


def check(cond, label):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ok  — {label}")
    else:
        fail += 1
        print(f"  XATO — {label}")


def test_validation():
    print("initData tekshiruvi:")
    init = sign(
        {
            "query_id": "AAH123",
            "user": {"id": 279058397, "first_name": "Ali", "username": "ali", "is_premium": True},
            "chat_type": "private",
            "start_param": "promo7",
        },
        TOKEN,
    )
    data = validate(init, TOKEN)
    check(data.user.id == 279058397, "to'g'ri initData qabul qilindi")
    check(data.user.username == "ali" and data.user.full_name == "Ali", "user JSON parse qilindi")
    check(data.start_param == "promo7" and data.query_id == "AAH123", "start_param / query_id")
    check(data.user_id == 279058397 and data.age < 5, "user_id va age")

    check(not is_valid(init.replace("279058397", "111111111"), TOKEN), "o'zgartirilgan user rad etildi")
    check(not is_valid(init, "999999:BOSHQA"), "boshqa token rad etildi")

    try:
        validate("user=%7B%7D&auth_date=1", TOKEN)
        no_hash = False
    except WebAppAuthError as exc:
        no_hash = "hash" in str(exc)
    check(no_hash, "hash yo'q -> WebAppAuthError")

    old = sign({"user": {"id": 1, "first_name": "A"}, "auth_date": str(int(time.time()) - 7200)}, TOKEN)
    try:
        validate(old, TOKEN, max_age=3600)
        expired = False
    except WebAppAuthError as exc:
        expired = "eskirgan" in str(exc)
    check(expired, "eskirgan initData rad etildi")
    check(is_valid(old, TOKEN, max_age=0), "max_age=0 -> muddat tekshirilmaydi")
    check(parse_init_data(init).user.id == 279058397, "parse_init_data()")


def test_third_party():
    print("\nUchinchi tomon tekshiruvi (Ed25519):")
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        print("  o'tkazib yuborildi — `pip install cryptography`")
        return

    private = Ed25519PrivateKey.generate()
    public_hex = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()
    bot_id = 123456
    payload = {
        "auth_date": str(int(time.time())),
        "query_id": "AAH1",
        "user": json.dumps({"id": 7, "first_name": "Vali"}, separators=(",", ":")),
    }
    check_string = f"{bot_id}:WebAppData\n" + _check_string(list(payload.items()))
    signature = base64.urlsafe_b64encode(private.sign(check_string.encode())).decode().rstrip("=")

    good = urlencode({**payload, "signature": signature})
    check(validate_third_party(good, bot_id, public_key=public_hex).user.first_name == "Vali",
          "to'g'ri imzo qabul qilindi")

    forged = urlencode({
        **payload,
        "user": json.dumps({"id": 8, "first_name": "Soxta"}, separators=(",", ":")),
        "signature": signature,
    })
    try:
        validate_third_party(forged, bot_id, public_key=public_hex)
        rejected = False
    except WebAppAuthError:
        rejected = True
    check(rejected, "soxta imzo rad etildi")


def test_links():
    print("\nHavolalar:")
    check(
        direct_link("MyBot", "shop", "ref_42", mode="fullscreen")
        == "https://t.me/MyBot/shop?startapp=ref_42&mode=fullscreen",
        "direct_link()",
    )
    check(main_app_link("@MyBot", "ref 42") == "https://t.me/MyBot?startapp=ref%2042", "main_app_link()")


async def test_server():
    print("\nBackend server:")
    app = Zafather(TOKEN)
    sent = []

    async def fake(method, **kwargs):
        sent.append((method, kwargs))
        return {"ok": True}

    app.bot.request = fake
    app.bot.send_message = lambda **kw: fake("sendMessage", **kw)

    server = MiniAppServer(app, port=PORT, max_age=3600)

    @server.api("/me")
    async def me(user, init):
        return {"id": user.id, "name": user.full_name, "start": init.start_param}

    @server.api("/notify")
    async def notify(user, data, bot):
        await bot.send_message(chat_id=user.id, text=data.get("text", ""))
        return {"sent": True}

    @server.api("/raw")
    async def raw(**kwargs):
        return {"keys": sorted(kwargs)}

    await server.start()
    init = sign({"user": {"id": 42, "first_name": "Ali", "last_name": "Valiev"},
                 "start_param": "ref9"}, TOKEN)
    base = f"http://127.0.0.1:{PORT}/api"

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{base}/me", headers={"X-Telegram-Init-Data": init}, json={}) as r:
            body = await r.json()
        check(r.status == 200 and body["id"] == 42 and body["name"] == "Ali Valiev", "to'g'ri initData -> 200")
        check(body["ok"] is True and body["start"] == "ref9", "javobda ok=True va start_param")

        async with session.post(f"{base}/me", json={}) as r:
            body = await r.json()
        check(r.status == 401 and body["ok"] is False, "initData'siz -> 401")

        async with session.post(
            f"{base}/me", headers={"X-Telegram-Init-Data": init.replace("42", "99")}, json={}
        ) as r:
            status = r.status
        check(status == 401, "o'zgartirilgan initData -> 401")

        async with session.post(f"{base}/me", headers={"Authorization": "tma " + init}, json={}) as r:
            body = await r.json()
        check(r.status == 200 and body["id"] == 42, "'Authorization: tma' sarlavhasi")

        async with session.post(
            f"{base}/notify", headers={"X-Telegram-Init-Data": init}, json={"text": "salom"}
        ) as r:
            await r.json()
        check(sent and sent[-1][1] == {"chat_id": 42, "text": "salom"}, "handler botdan xabar yubordi")

        async with session.post(f"{base}/raw", headers={"X-Telegram-Init-Data": init}, json={}) as r:
            body = await r.json()
        check(
            body["keys"] == ["app", "bot", "data", "init", "request", "user"],
            "handlerga barcha argumentlar uzatildi",
        )

    await server.stop()
    await app.bot.close()


def main():
    test_validation()
    test_third_party()
    test_links()
    asyncio.run(test_server())
    print(f"\nNatija: {ok} ta test o'tdi, {fail} ta xato.")
    return fail


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
