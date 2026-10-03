"""UZ: Update'larni qayta ishlash: konteynerlarni yoyish, `pts` bo'shliqlarini aniqlash
va `updates.getDifference` orqali o'tkazib yuborilganlarini olish.
RU: Обработка update: распаковка контейнеров, поиск пропусков `pts` и догрузка
пропущенного через `updates.getDifference`.
EN: Update processing: flattening containers, detecting `pts` gaps and catching up via
`updates.getDifference`.

UZ: Kanal `pts` bo'shliqlari kuzatilmaydi (kanal update'lari kelgan tartibda uzatiladi).
Qisqa xabar noma'lum foydalanuvchidan kelsa, uning `access_hash` i `getDifference` bilan
olinadi.
RU: Пропуски `pts` каналов не отслеживаются (update каналов передаются как пришли). Если
короткое сообщение пришло от неизвестного пользователя, его `access_hash` загружается
через `getDifference`.
EN: Channel `pts` gaps are not tracked (channel updates are delivered as they arrive). A
short message from an unknown user triggers `getDifference` to learn its `access_hash`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .tl import TLObject, functions, types

log = logging.getLogger("zafather.mtproto.updates")

Invoke = Callable[[TLObject], Awaitable[Any]]
Emit = Callable[[TLObject], Awaitable[None]]
EntitySink = Callable[[list[Any]], None]

_SHORT_MESSAGE_FLAGS = ("out", "mentioned", "media_unread", "silent")
_SHORT_MESSAGE_FIELDS = ("fwd_from", "via_bot_id", "reply_to", "entities", "ttl_period")


@dataclass
class UpdateState:
    """UZ: `pts`, `qts`, `date`, `seq` holati. RU: Состояние `pts`, `qts`, `date`, `seq`.
    EN: The `pts`, `qts`, `date`, `seq` state.
    """

    pts: int = 0
    qts: int = 0
    date: int = 0
    seq: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> UpdateState:
        return cls(**{key: int(data.get(key, 0)) for key in ("pts", "qts", "date", "seq")})

    def to_dict(self) -> dict[str, int]:
        return {"pts": self.pts, "qts": self.qts, "date": self.date, "seq": self.seq}

    def apply(self, state: Any) -> None:
        self.pts, self.qts, self.date, self.seq = state.pts, state.qts, state.date, state.seq


def short_message(update: TLObject, self_id: int | None) -> TLObject:
    """UZ: `updateShortMessage`/`updateShortChatMessage` -> to'liq `message`.
    RU: `updateShortMessage`/`updateShortChatMessage` -> полный `message`.
    EN: Expands `updateShortMessage`/`updateShortChatMessage` into a full `message`.
    """
    values = update.values
    if update.tl_name == "updateShortChatMessage":
        peer = types.peerChat(chat_id=values["chat_id"])
        sender = types.peerUser(user_id=values["from_id"])
    else:
        peer = types.peerUser(user_id=values["user_id"])
        sender_id = self_id if values.get("out") and self_id else values["user_id"]
        sender = types.peerUser(user_id=sender_id)
    fields = {name: values[name] for name in _SHORT_MESSAGE_FLAGS if values.get(name)}
    fields.update(
        {name: values[name] for name in _SHORT_MESSAGE_FIELDS if values.get(name) is not None}
    )
    return types.message(
        id=values["id"],
        peer_id=peer,
        from_id=sender,
        date=values["date"],
        message=values["message"],
        **fields,
    )


class UpdateProcessor:
    """UZ: Kelgan `Updates` ni alohida update'larga ajratib, `emit` ga uzatadi.
    RU: Разбивает пришедшие `Updates` на отдельные update и передаёт в `emit`.
    EN: Splits incoming `Updates` into single updates and passes them to `emit`.
    """

    def __init__(
        self,
        invoke: Invoke,
        emit: Emit,
        cache_entities: EntitySink,
        *,
        state: UpdateState | None = None,
        self_id: Callable[[], int | None] = lambda: None,
        known_user: Callable[[int], bool] = lambda user_id: True,
        gap_timeout: float = 0.5,
    ) -> None:
        self._invoke = invoke
        self._emit = emit
        self._cache_entities = cache_entities
        self._self_id = self_id
        self._known_user = known_user
        self.gap_timeout = gap_timeout
        self.state = state or UpdateState()
        self._catch_up_lock = asyncio.Lock()
        self._gap_task: asyncio.Task[None] | None = None

    async def initialize(self) -> None:
        """UZ: Server holatini oladi (update'lar shundan keyin keladi).
        RU: Получает состояние сервера (после этого приходят update).
        EN: Fetches the server state (updates start flowing afterwards).
        """
        self.state.apply(await self._invoke(functions.updates.getState()))

    async def feed(self, container: TLObject, *, emit: bool = True) -> None:
        """UZ: Bitta `Updates` obyektini qayta ishlaydi. RU: Обрабатывает один объект
        `Updates`. EN: Processes one `Updates` object.
        """
        name = container.tl_name
        if name == "updatesTooLong":
            await self.catch_up()
            return
        if name in ("updateShortMessage", "updateShortChatMessage"):
            sender = container.values.get("user_id") or container.values.get("from_id")
            if emit and sender is not None and not self._known_user(sender):
                await self.catch_up()
                return
            message = short_message(container, self._self_id())
            update = types.updateNewMessage(
                message=message, pts=container.pts, pts_count=container.pts_count
            )
            await self._handle(update, emit)
            return
        if name == "updateShort":
            await self._handle(container.update, emit)
            return
        if name in ("updates", "updatesCombined"):
            self._cache_entities([*container.users, *container.chats])
            for update in container.updates:
                await self._handle(update, emit)
            if container.seq:
                self.state.seq = container.seq
            if container.date:
                self.state.date = container.date
            return
        if name == "updateShortSentMessage":
            if self._accept_pts(container) is None:
                self.request_catch_up()
            return
        log.debug("Ignoring %s", name)

    def _accept_pts(self, update: TLObject) -> bool | None:
        """UZ: True — qo'llash, False — takror, None — bo'shliq.
        RU: True — применить, False — дубликат, None — пропуск.
        EN: True — apply, False — duplicate, None — a gap.
        """
        values = update.values
        pts, count = values.get("pts"), values.get("pts_count")
        if pts is None or count is None or "Channel" in update.tl_name:
            return True
        local = self.state.pts
        if local == 0 or local + count == pts:
            self.state.pts = pts
            return True
        if local + count > pts:
            return False
        return None

    async def _handle(self, update: TLObject, emit: bool) -> None:
        accepted = self._accept_pts(update)
        if accepted is None:
            log.debug("Update gap detected at local pts %s", self.state.pts)
            self.request_catch_up()
            return
        qts = update.values.get("qts")
        if qts:
            self.state.qts = max(self.state.qts, qts)
        if accepted and emit:
            await self._emit(update)

    def request_catch_up(self) -> None:
        """UZ: `gap_timeout` dan keyin o'tkazib yuborilgan update'larni oladi (kutmaydi).
        RU: Через `gap_timeout` догружает пропущенные update (не блокирует).
        EN: Fetches missed updates after `gap_timeout` without blocking.
        """
        if self._gap_task is None or self._gap_task.done():
            self._gap_task = asyncio.ensure_future(self._delayed_catch_up())

    async def _delayed_catch_up(self) -> None:
        await asyncio.sleep(self.gap_timeout)
        try:
            await self.catch_up()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Fetching missed updates failed")

    async def close(self) -> None:
        """UZ: Rejalashtirilgan `getDifference` ni bekor qiladi.
        RU: Отменяет запланированный `getDifference`.
        EN: Cancels a scheduled `getDifference`.
        """
        if self._gap_task is not None:
            self._gap_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._gap_task
            self._gap_task = None

    async def catch_up(self) -> None:
        """UZ: O'tkazib yuborilgan update'larni oladi. RU: Догружает пропущенные update.
        EN: Fetches missed updates.
        """
        async with self._catch_up_lock:
            if not self.state.pts:
                await self.initialize()
                return
            await self._fetch_difference()

    async def _fetch_difference(self) -> None:
        while True:
            difference = await self._invoke(
                functions.updates.getDifference(
                    pts=self.state.pts, date=self.state.date, qts=self.state.qts
                )
            )
            name = difference.tl_name
            if name == "updates.differenceEmpty":
                self.state.date, self.state.seq = difference.date, difference.seq
                return
            if name == "updates.differenceTooLong":
                self.state.pts = difference.pts
                return
            self._cache_entities([*difference.users, *difference.chats])
            final = name == "updates.difference"
            self.state.apply(difference.state if final else difference.intermediate_state)
            for message in difference.new_messages:
                await self._emit(types.updateNewMessage(message=message, pts=0, pts_count=0))
            for update in difference.other_updates:
                await self._emit(update)
            if final:
                return


__all__ = ["UpdateProcessor", "UpdateState", "short_message"]
