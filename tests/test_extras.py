from __future__ import annotations

import asyncio
import json

from tests.support import FakeSession, message, message_update
from zafather import (
    AlbumMiddleware,
    Bot,
    BotFarm,
    ChatActionMiddleware,
    I18n,
    Invoice,
    LabeledPrice,
    ManagedBots,
    Message,
    Router,
    ThrottlingMiddleware,
    Update,
    Zafather,
)
from zafather.i18n import normalize_locale
from zafather.managed import bot_id_from_token


async def passthrough(event, data):
    return data


# --- i18n -----------------------------------------------------------------------------------
def test_i18n_lookup_chain() -> None:
    i18n = I18n({"uz": {"hi": "Salom, {name}!"}, "en": {"hi": "Hello, {name}!", "only_en": "E"}})
    assert normalize_locale("ru_RU") == "ru" and normalize_locale(None) == ""
    assert i18n.gettext("hi", "uz", name="Ali") == "Salom, Ali!"
    assert i18n.gettext("only_en", "uz") == "E"
    assert i18n.gettext("missing", "uz") == "missing"
    assert i18n.gettext("hi", "uz") == "Salom, {name}!"
    assert i18n.gettext("hi", "uz", other=1) == "Salom, {name}!"
    assert i18n.locales == ("uz", "en")


def test_i18n_from_directory(tmp_path) -> None:
    (tmp_path / "ru.json").write_text(json.dumps({"hi": "Привет"}), encoding="utf-8")
    i18n = I18n.from_directory(tmp_path, default_locale="ru")
    assert i18n.gettext("hi") == "Привет"


async def test_i18n_middleware(app: Zafather, session: FakeSession) -> None:
    app.middleware(I18n({"ru": {"welcome": "Привет, {name}!"}, "en": {"welcome": "Hi"}}))
    locales = []

    @app.command("start")
    async def start(message: Message, _, locale):
        locales.append(locale)
        await message.answer(_("welcome", name=message.from_user.first_name))

    raw = message_update("/start")
    raw["message"]["from"]["language_code"] = "ru-RU"
    await app.feed_update(Update(raw, app.bot))
    assert locales == ["ru"] and session.last("sendMessage").params["text"] == "Привет, Ali!"


# --- middlewares ---------------------------------------------------------------------------
async def test_throttling_drops_fast_repeats() -> None:
    throttled = []
    middleware = ThrottlingMiddleware(rate=10, on_throttled=lambda event, data: throttled.append(1))
    assert await middleware(None, {"user_id": 1}, passthrough)
    assert await middleware(None, {"user_id": 1}, passthrough) is False
    assert await middleware(None, {"user_id": 2}, passthrough)
    assert await middleware(None, {"user_id": None}, passthrough)
    assert throttled == [1]


async def test_throttling_cleans_up_expired_keys() -> None:
    middleware = ThrottlingMiddleware(rate=0.0)
    for user_id in range(5):
        await middleware(None, {"user_id": user_id}, passthrough)
    middleware._next_cleanup = 0
    await middleware(None, {"user_id": 99}, passthrough)
    assert list(middleware._last_seen) == [99]


async def test_chat_action_is_sent_and_repeated(bot: Bot, session: FakeSession) -> None:
    middleware = ChatActionMiddleware(action="typing", interval=0.02)

    async def slow(event, data):
        await asyncio.sleep(0.07)
        return True

    assert await middleware(None, {"bot": bot, "chat_id": 77}, slow)
    actions = session.calls("sendChatAction")
    assert len(actions) >= 2 and actions[0].params == {"chat_id": 77, "action": "typing"}


async def test_chat_action_with_delay_skips_fast_handlers(bot: Bot, session: FakeSession) -> None:
    middleware = ChatActionMiddleware(delay=1)
    assert await middleware(None, {"bot": bot, "chat_id": 1}, passthrough)
    assert session.calls("sendChatAction") == []
    assert await middleware(None, {}, passthrough) == {}


async def test_album_groups_media_group(bot: Bot) -> None:
    middleware = AlbumMiddleware(latency=0.05)
    received = []

    async def handler(event, data):
        received.append([item.message_id for item in data["album"]])
        return True

    def album_message(message_id: int) -> Message:
        return Message(message(None, message_id=message_id, media_group_id="g1", photo=[{}]), bot)

    results = await asyncio.gather(
        middleware(album_message(2), {}, handler),
        middleware(album_message(1), {}, handler),
        middleware(album_message(3), {}, handler),
    )
    assert received == [[1, 2, 3]] and all(results)
    assert await middleware(Message(message("solo"), bot), {"x": 1}, passthrough) == {"x": 1}


# --- payments ------------------------------------------------------------------------------
async def test_invoice_and_stars(bot: Bot, session: FakeSession) -> None:
    invoice = Invoice(
        "VIP", "One month", "vip_1", prices=[LabeledPrice("Access", 250)], start_parameter="s"
    )
    assert invoice.to_dict() == {
        "title": "VIP",
        "description": "One month",
        "payload": "vip_1",
        "currency": "XTR",
        "prices": [{"label": "Access", "amount": 250}],
        "start_parameter": "s",
    }
    stars = Invoice.stars("Pro", "Pro plan", "pro", 100, photo_url="https://e/p.png").to_dict()
    assert (
        stars["prices"] == [{"label": "Pro", "amount": 100}]
        and stars["photo_url"] == "https://e/p.png"
    )
    await bot.stars.balance()
    assert session.last().method == "getMyStarBalance"
    await bot.stars.refund(5, "charge")
    assert session.last().params == {"user_id": 5, "telegram_payment_charge_id": "charge"}
    await bot.stars.transactions(limit=10)
    assert session.last().params == {"limit": 10}
    await bot.stars.business_balance("bc")
    assert session.last().method == "getBusinessAccountStarBalance"


# --- managed bots --------------------------------------------------------------------------
async def test_managed_bots_helpers(bot: Bot, session: FakeSession) -> None:
    assert ManagedBots.create_link("Manager", "@new_bot", name="Mening botim") == (
        "https://t.me/newbot/Manager/new_bot?name=Mening%20botim"
    )
    session.respond("getManagedBotToken", {"token": "999:abc"}, "999:def")
    managed = ManagedBots(bot)
    assert await managed.token(999) == "999:abc"
    assert await managed.token(999) == "999:def"
    assert session.last("getManagedBotToken").params == {"bot_id": 999}
    session.respond("replaceManagedBotToken", {"access_token": "999:new"})
    assert await managed.replace_token(999) == "999:new"
    assert bot_id_from_token("42:x") == 42


async def test_bot_farm_lifecycle(session: FakeSession) -> None:
    child_router = Router("child")
    started = []

    @child_router.command("start")
    async def start(message: Message):
        await message.answer("child bot")

    farm = BotFarm(child_router, on_start=lambda app: started.append(app.bot.id))
    app = await farm.add("777:CHILD", session=session, polling_timeout=0)
    assert started == [777] and "777:CHILD" in farm and farm.count == 1 and len(farm) == 1
    assert await farm.add("777:CHILD") is app
    await app.feed_update(Update(message_update("/start"), app.bot))
    assert session.last("sendMessage").params["text"] == "child bot"
    assert await farm.broadcast([1, 2], "hello") == 2
    await farm.stop_all()
    await asyncio.wait_for(farm.run_forever(), timeout=1)
    assert farm.count == 0 and not await farm.remove(777)
    assert repr(farm) == "<BotFarm bots=0>" and "bad" not in farm


def test_app_farm_and_spawn_share_storage(app: Zafather) -> None:
    farm = app.farm()
    assert farm.storage is app.storage and farm.router is app
