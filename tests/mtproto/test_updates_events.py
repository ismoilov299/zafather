from __future__ import annotations

import asyncio
from typing import Any

import pytest

from zafather.mtproto import events, parse_html
from zafather.mtproto.tl import TLObject, types
from zafather.mtproto.updates import UpdateProcessor, UpdateState, short_message

SELF_ID = 1000


class FakeClient:
    def __init__(self) -> None:
        self.self_id = SELF_ID
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, name: str):
        async def method(*args: Any, **kwargs: Any) -> str:
            self.calls.append((name, args, kwargs))
            return name

        return method


def message(text: str = "hi", *, peer: TLObject | None = None, **fields: Any) -> TLObject:
    return types.message(
        id=fields.pop("id", 1),
        peer_id=peer or types.peerUser(user_id=5),
        date=0,
        message=text,
        **fields,
    )


# --- update processor -----------------------------------------------------------------------
class Recorder:
    def __init__(self, differences: list[TLObject] | None = None) -> None:
        self.emitted: list[TLObject] = []
        self.invoked: list[TLObject] = []
        self.cached: list[Any] = []
        self.differences = differences or []

    async def invoke(self, request: TLObject) -> TLObject:
        self.invoked.append(request)
        if request.tl_name == "updates.getState":
            return types.updates.state(pts=10, qts=0, date=1, seq=0, unread_count=0)
        return self.differences.pop(0)

    async def emit(self, update: TLObject) -> None:
        self.emitted.append(update)

    def processor(self, pts: int = 10, known: bool = True) -> UpdateProcessor:
        return UpdateProcessor(
            self.invoke,
            self.emit,
            self.cached.extend,
            state=UpdateState(pts=pts),
            self_id=lambda: SELF_ID,
            known_user=lambda user_id: known,
            gap_timeout=0.01,
        )


def test_short_message_expansion() -> None:
    out = types.updateShortMessage(
        id=3, user_id=5, message="x", pts=1, pts_count=1, date=0, out=True, silent=True
    )
    expanded = short_message(out, SELF_ID)
    assert expanded.from_id.user_id == SELF_ID and expanded.peer_id.user_id == 5 and expanded.silent
    group = types.updateShortChatMessage(
        id=4, from_id=7, chat_id=9, message="g", pts=1, pts_count=1, date=0
    )
    expanded = short_message(group, SELF_ID)
    assert expanded.peer_id.chat_id == 9 and expanded.from_id.user_id == 7


async def test_pts_sequence_duplicates_and_containers() -> None:
    recorder = Recorder()
    processor = recorder.processor()
    first = types.updateNewMessage(message=message("a"), pts=11, pts_count=1)
    await processor.feed(types.updateShort(update=first, date=0))
    await processor.feed(types.updateShort(update=first, date=0))
    container = types.updates(
        updates=[types.updateNewMessage(message=message("b"), pts=12, pts_count=1)],
        users=[types.user(id=5, access_hash=1)],
        chats=[],
        date=5,
        seq=3,
    )
    await processor.feed(container)
    assert [u.message.message for u in recorder.emitted] == ["a", "b"]
    assert processor.state.pts == 12 and processor.state.seq == 3 and recorder.cached
    channel = types.updateNewChannelMessage(message=message("c"), pts=999, pts_count=1)
    await processor.feed(types.updateShort(update=channel, date=0))
    assert recorder.emitted[-1].message.message == "c" and processor.state.pts == 12
    await processor.feed(types.updateShortSentMessage(id=1, pts=13, pts_count=1, date=0))
    assert processor.state.pts == 13 and len(recorder.emitted) == 3
    await processor.feed(types.updateShort(update=first, date=0), emit=False)
    await processor.feed(types.updateShort(update=types.updateLoginToken(), date=0))
    assert recorder.emitted[-1].tl_name == "updateLoginToken"


async def test_gap_triggers_difference_after_timeout() -> None:
    difference = types.updates.difference(
        new_messages=[message("missed")],
        new_encrypted_messages=[],
        other_updates=[types.updateLoginToken()],
        chats=[],
        users=[types.user(id=5, access_hash=1)],
        state=types.updates.state(pts=20, qts=1, date=2, seq=1, unread_count=0),
    )
    recorder = Recorder([difference])
    processor = recorder.processor(pts=10)
    await processor.feed(
        types.updateShort(
            update=types.updateNewMessage(message=message("late"), pts=15, pts_count=1), date=0
        )
    )
    assert recorder.emitted == []
    await asyncio.sleep(0.05)
    assert [u.tl_name for u in recorder.emitted] == ["updateNewMessage", "updateLoginToken"]
    assert recorder.emitted[0].message.message == "missed" and processor.state.pts == 20
    await processor.close()


async def test_difference_slices_and_too_long() -> None:
    state = types.updates.state(pts=15, qts=0, date=0, seq=0, unread_count=0)
    slice_ = types.updates.differenceSlice(
        new_messages=[message("1")],
        new_encrypted_messages=[],
        other_updates=[],
        chats=[],
        users=[],
        intermediate_state=state,
    )
    recorder = Recorder([slice_, types.updates.differenceEmpty(date=9, seq=4)])
    processor = recorder.processor(pts=10)
    await processor.catch_up()
    assert len(recorder.emitted) == 1 and processor.state.pts == 15 and processor.state.date == 9
    too_long = Recorder([types.updates.differenceTooLong(pts=99)])
    long_processor = too_long.processor(pts=10)
    await long_processor.feed(types.updatesTooLong())
    assert long_processor.state.pts == 99


async def test_unknown_sender_fetches_difference_and_fresh_state_initializes() -> None:
    recorder = Recorder([types.updates.differenceEmpty(date=1, seq=0)])
    processor = recorder.processor(pts=10, known=False)
    await processor.feed(
        types.updateShortMessage(id=3, user_id=5, message="x", pts=11, pts_count=1, date=0)
    )
    assert [r.tl_name for r in recorder.invoked] == ["updates.getDifference"]
    fresh = Recorder()
    fresh_processor = fresh.processor(pts=0)
    await fresh_processor.catch_up()
    assert fresh_processor.state.pts == 10


# --- events ---------------------------------------------------------------------------------
def build(builder: events.EventBuilder, update: TLObject) -> Any:
    event = builder.build(update, FakeClient())  # type: ignore[arg-type]
    return event if event is not None and builder.filter(event) else None


def new(text: str, **fields: Any) -> TLObject:
    return types.updateNewMessage(message=message(text, **fields), pts=1, pts_count=1)


async def test_new_message_filters() -> None:
    assert build(events.NewMessage(), new("hello")) is not None
    match = build(events.NewMessage(pattern=r"^\.(\w+)"), new(".ping"))
    assert match.pattern_match.group(1) == "ping"
    assert build(events.NewMessage(pattern=r"^\.ping"), new("ping")) is None
    assert build(events.NewMessage(pattern=lambda text: "x" in text), new("xyz")) is not None
    assert build(events.NewMessage(outgoing=True), new("in")) is None
    assert build(events.NewMessage(incoming=True), new("out", out=True)) is None
    assert build(events.NewMessage(incoming=False), new("out", out=True)) is not None
    assert build(events.NewMessage(incoming=True, outgoing=True), new("x")) is not None
    assert build(events.NewMessage(from_users=[5]), new("x")) is not None
    assert build(events.NewMessage(from_users=[6]), new("x")) is None
    assert build(events.NewMessage(chats=[5]), new("x")) is not None
    assert build(events.NewMessage(chats=[5], blacklist_chats=True), new("x")) is None
    assert build(events.NewMessage(func=lambda e: e.text == "x"), new("y")) is None
    assert build(events.NewMessage(forwards=False), new("x")) is not None
    service = types.updateNewMessage(
        message=types.messageService(
            id=1, peer_id=types.peerUser(user_id=5), date=0, action=types.messageActionEmpty()
        ),
        pts=1,
        pts_count=1,
    )
    assert build(events.NewMessage(), service) is None
    assert build(events.NewMessage(), types.updateLoginToken()) is None


async def test_message_event_properties_and_actions() -> None:
    client = FakeClient()
    group = types.updateNewMessage(
        message=message(
            "hi", peer=types.peerChat(chat_id=9), from_id=types.peerUser(user_id=7), id=4
        ),
        pts=1,
        pts_count=1,
    )
    event = events.NewMessage().build(group, client)  # type: ignore[arg-type]
    assert event.is_group and not event.is_private and not event.is_channel
    assert (event.chat_id, event.sender_id, event.id, event.text) == (-9, 7, 4, "hi")
    await event.reply("re")
    await event.respond("hello")
    await event.edit("edited")
    await event.delete()
    await event.get_chat()
    await event.get_sender()
    names = [name for name, _, _ in client.calls]
    assert names == [
        "send_message",
        "send_message",
        "edit_message",
        "delete_messages",
        "get_entity",
        "get_entity",
    ]
    assert client.calls[0][2] == {"reply_to": 4}
    outgoing = events.NewMessage().build(new("x", out=True), client)  # type: ignore[arg-type]
    assert outgoing.sender_id == SELF_ID and "NewMessage.Event" in repr(outgoing)
    channel_post = events.NewMessage().build(new("c", peer=types.peerChannel(channel_id=3)), client)  # type: ignore[arg-type]
    assert channel_post.is_channel and channel_post.sender_id is None


async def test_edited_deleted_callback_and_raw_events() -> None:
    edited = types.updateEditMessage(message=message("new"), pts=1, pts_count=1)
    assert build(events.MessageEdited(), edited).text == "new"
    assert build(events.NewMessage(), edited) is None
    deleted = build(
        events.MessageDeleted(),
        types.updateDeleteChannelMessages(channel_id=3, messages=[1, 2], pts=1, pts_count=2),
    )
    assert deleted.deleted_ids == [1, 2] and deleted.chat_id == -1000000000003
    private_deleted = build(
        events.MessageDeleted(), types.updateDeleteMessages(messages=[5], pts=1, pts_count=1)
    )
    assert private_deleted.chat_id is None
    callback = types.updateBotCallbackQuery(
        query_id=77,
        user_id=5,
        peer=types.peerUser(user_id=5),
        msg_id=3,
        chat_instance=1,
        data=b"menu:1",
    )
    client = FakeClient()
    event = events.CallbackQuery(data=r"menu:(\d)").build(callback, client)  # type: ignore[arg-type]
    assert event.data_match.group(1) == b"1" and event.sender_id == 5 and event.message_id == 3
    assert events.CallbackQuery(data=b"other").build(callback, client) is None  # type: ignore[arg-type]
    assert events.CallbackQuery(data=b"menu:1").build(callback, client) is not None  # type: ignore[arg-type]
    await event.answer("ok", alert=True)
    await event.respond("hi")
    await event.edit("edited")
    assert [name for name, _, _ in client.calls] == ["invoke", "send_message", "edit_message"]
    assert client.calls[0][1][0].tl_name == "messages.setBotCallbackAnswer"
    assert (
        build(events.Raw(types=["updateLoginToken"]), types.updateLoginToken()).update.tl_name
        == "updateLoginToken"
    )
    assert build(events.Raw(types=["other"]), types.updateLoginToken()) is None
    assert events.Events.NewMessage is events.NewMessage


async def test_inline_callback_cannot_respond() -> None:
    inline = types.updateBotCallbackQuery(
        query_id=1, user_id=5, peer=types.peerUser(user_id=5), msg_id=1, chat_instance=1
    )
    event = events.CallbackQuery().build(inline, FakeClient())  # type: ignore[arg-type]
    assert event.data == b""
    no_chat = events.CallbackQuery.Event(
        FakeClient(),
        types.updateInlineBotCallbackQuery(  # type: ignore[arg-type]
            query_id=1,
            user_id=5,
            msg_id=types.inputBotInlineMessageID(dc_id=1, id=1, access_hash=1),
            chat_instance=1,
        ),
    )
    with pytest.raises(ValueError):
        await no_chat.respond("x")
    with pytest.raises(ValueError):
        await no_chat.edit("x")


# --- HTML parsing ---------------------------------------------------------------------------
def test_parse_html_entities_with_utf16_offsets() -> None:
    text, entities = parse_html(
        '😀 <b>Bold <i>both</i></b> <a href="https://e.com">link</a> &lt;tag&gt; '
        '<pre><code class="language-py">x = 1</code></pre> <span class="tg-spoiler">s</span> '
        '<tg-emoji emoji-id="55">🔥</tg-emoji> <blockquote expandable>q</blockquote> '
        "<u>u</u><s>s</s><code>c</code>"
    )
    assert text.startswith("😀 Bold both link <tag> x = 1 s 🔥 q usc")
    by_type = {entity.tl_name: entity for entity in entities}
    assert by_type["messageEntityBold"].offset == 3 and by_type["messageEntityBold"].length == 9
    assert by_type["messageEntityItalic"].offset == 8
    assert by_type["messageEntityTextUrl"].url == "https://e.com"
    assert by_type["messageEntityPre"].language == "py"
    assert by_type["messageEntitySpoiler"].length == 1
    assert by_type["messageEntityCustomEmoji"].document_id == 55
    assert by_type["messageEntityBlockquote"].collapsed is True
    assert {"messageEntityUnderline", "messageEntityStrike", "messageEntityCode"} <= set(by_type)
    assert parse_html("plain") == ("plain", [])
    assert parse_html("<b></b>x") == ("x", [])
