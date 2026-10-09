"""UZ: Shifrlangan MTProto sessiyasi: so'rov yuborish, javob va xizmat xabarlarini qayta ishlash.
RU: Зашифрованная сессия MTProto: отправка запросов, обработка ответов и служебных сообщений.
EN: The encrypted MTProto session: sending requests and handling responses and service messages.
"""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import logging
import os
import struct
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from .auth import AuthKeyGenerator, AuthResult
from .crypto import AuthKey, RSAPublicKey
from .errors import AuthKeyNotFoundError, SecurityError, TransportError, rpc_error
from .state import MTProtoState
from .tl import TLObject, TLReader, TLSerializer, TLType, default_serializer, functions, types
from .tl.codec import GZIP_PACKED_ID
from .transport import Transport

log = logging.getLogger("zafather.mtproto.sender")

MSG_CONTAINER_ID = 0x73F1F8DC
RPC_RESULT_ID = 0xF35C6D01
RPC_ERROR_ID = 0x2144CA19

TransportFactory = Callable[[], Transport]
UpdateCallback = Callable[[TLObject], None]


@dataclass(eq=False)
class _Pending:
    request: TLObject
    body: bytes
    result_type: TLType
    future: asyncio.Future[Any]
    msg_id: int = 0
    attempts: int = field(default=0)


def _innermost(request: TLObject) -> TLObject:
    query = request.values.get("query")
    return _innermost(query) if isinstance(query, TLObject) else request


class MTProtoSender:
    """UZ: Bitta data-markaz bilan shifrlangan ulanish.
    RU: Зашифрованное соединение с одним дата-центром.
    EN: An encrypted connection to a single data center.

    UZ: Kalit bo'lmasa, ulanishda yangisi yaratiladi (`on_auth_key` orqali saqlanadi).
    Ulanish uzilsa avtomatik qayta ulanadi va javobsiz so'rovlarni qayta yuboradi.
    RU: Если ключа нет, при подключении создаётся новый (сохраняется через `on_auth_key`).
    При обрыве автоматически переподключается и повторяет запросы без ответа.
    EN: Without a key a new one is created on connect (persisted via `on_auth_key`). On a
    dropped connection it reconnects and resends unanswered requests.
    """

    def __init__(
        self,
        transport_factory: TransportFactory,
        *,
        dc_id: int,
        test_mode: bool = False,
        auth_key: AuthKey | None = None,
        serializer: TLSerializer | None = None,
        rsa_keys: Iterable[RSAPublicKey] | None = None,
        on_auth_key: Callable[[AuthKey | None], None] | None = None,
        on_update: UpdateCallback | None = None,
        on_reconnect: Callable[[], Awaitable[None]] | None = None,
        on_new_session: Callable[[], None] | None = None,
        on_closed: Callable[[], None] | None = None,
        request_timeout: float = 60.0,
        ping_interval: float = 60.0,
        reconnect_retries: int = 5,
        reconnect_delay: float = 1.0,
    ) -> None:
        self._transport_factory = transport_factory
        self.dc_id = dc_id
        self.test_mode = test_mode
        self.auth_key = auth_key
        self.serializer = serializer or default_serializer()
        self._rsa_keys = tuple(rsa_keys) if rsa_keys is not None else None
        self._on_auth_key = on_auth_key
        self._on_update = on_update
        self._on_reconnect = on_reconnect
        self._on_new_session = on_new_session
        self._on_closed = on_closed
        self.request_timeout = request_timeout
        self.ping_interval = ping_interval
        self.reconnect_retries = reconnect_retries
        self.reconnect_delay = reconnect_delay
        self._transport: Transport | None = None
        self._state: MTProtoState | None = None
        self._pending: dict[int, _Pending] = {}
        self._acks: set[int] = set()
        self._send_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()
        self._closing = False
        self._connected = asyncio.Event()

    # --- UZ: hayot sikli / RU: жизненный цикл / EN: lifecycle --------------------------------
    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    @property
    def state(self) -> MTProtoState:
        if self._state is None:
            raise TransportError("The sender has not connected yet")
        return self._state

    async def connect(self) -> None:
        self._closing = False
        await self._open()
        self._start(self._ping_loop())

    async def _open(self) -> None:
        transport = self._transport_factory()
        await transport.connect()
        try:
            if self.auth_key is None:
                result = await self._create_auth_key(transport)
                self.auth_key = result.auth_key
                self._state = MTProtoState(
                    result.auth_key, salt=result.server_salt, time_offset=result.time_offset
                )
                if self._on_auth_key is not None:
                    self._on_auth_key(result.auth_key)
            elif self._state is None or self._state.auth_key is not self.auth_key:
                self._state = MTProtoState(self.auth_key)
        except BaseException:
            await transport.close()
            raise
        self._transport = transport
        self._connected.set()
        self._start(self._receive_loop(transport))

    async def _create_auth_key(self, transport: Transport) -> AuthResult:
        generator = AuthKeyGenerator(
            transport,
            dc_id=self.dc_id,
            test_mode=self.test_mode,
            rsa_keys=self._rsa_keys,
            serializer=self.serializer,
        )
        return await generator.generate()

    def _start(self, coroutine: Awaitable[None]) -> None:
        task = asyncio.ensure_future(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def disconnect(self) -> None:
        self._closing = True
        self._connected.clear()
        current = asyncio.current_task()
        tasks = [task for task in self._tasks if task is not current]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self._transport is not None:
            await self._transport.close()
            self._transport = None
        self._fail_pending(TransportError("Disconnected"))

    def _fail_pending(self, error: BaseException) -> None:
        pending, self._pending = self._pending, {}
        for item in pending.values():
            if not item.future.done():
                item.future.set_exception(error)

    # --- UZ: yuborish / RU: отправка / EN: sending ---------------------------------------------
    async def send(self, request: TLObject, *, timeout: float | None = None) -> Any:
        """UZ: So'rovni yuboradi va natijani qaytaradi (`RPCError` bo'lishi mumkin).
        RU: Отправляет запрос и возвращает результат (может выбросить `RPCError`).
        EN: Sends a request and returns its result (may raise `RPCError`).
        """
        if not self.connected:
            raise TransportError("Not connected")
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        pending = _Pending(
            request,
            self.serializer.serialize(request),
            self.serializer.result_type(request),
            future,
        )
        await self._transmit(pending)
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout or self.request_timeout)
        except asyncio.TimeoutError:
            self._pending.pop(pending.msg_id, None)
            raise

    async def _transmit(self, pending: _Pending) -> None:
        state = self.state
        pending.msg_id = state.ids.next()
        pending.attempts += 1
        self._pending[pending.msg_id] = pending
        packet = state.pack(pending.msg_id, state.next_seq_no(True), pending.body)
        await self._send_packet(packet)

    async def _send_packet(self, packet: bytes) -> None:
        transport = self._transport
        if transport is None:
            raise TransportError("Not connected")
        async with self._send_lock:
            await transport.send(packet)

    async def _flush_acks(self) -> None:
        if not self._acks or self._state is None:
            return
        acks, self._acks = sorted(self._acks), set()
        body = self.serializer.serialize(types.msgs_ack(msg_ids=acks))
        packet = self._state.pack(self._state.ids.next(), self._state.next_seq_no(False), body)
        with contextlib.suppress(TransportError):
            await self._send_packet(packet)

    # --- UZ: qabul qilish / RU: приём / EN: receiving ------------------------------------------
    async def _receive_loop(self, transport: Transport) -> None:
        while True:
            try:
                packet = await transport.receive()
            except asyncio.CancelledError:
                raise
            except TransportError as exc:
                if not self._closing:
                    self._start(self._reconnect(exc))
                return
            try:
                message = self.state.unpack(packet)
                await self._process(message.msg_id, message.seq_no, message.body)
            except SecurityError as exc:
                log.warning("Dropped an invalid message: %s", exc)
                continue
            except Exception:
                log.exception("Failed to process an incoming message")
                continue
            await self._flush_acks()

    async def _process(self, msg_id: int, seq_no: int, body: bytes) -> None:
        if seq_no % 2:
            self._acks.add(msg_id)
        reader = TLReader(body)
        constructor_id = reader.peek_uint32()
        if constructor_id == MSG_CONTAINER_ID:
            reader.uint32()
            for _ in range(reader.int32()):
                inner_id, inner_seq, length = reader.int64(), reader.int32(), reader.int32()
                await self._process(inner_id, inner_seq, reader.read(length))
        elif constructor_id == GZIP_PACKED_ID:
            reader.uint32()
            await self._process(msg_id, seq_no, gzip.decompress(reader.bytes()))
        elif constructor_id == RPC_RESULT_ID:
            reader.uint32()
            self._handle_rpc_result(reader.int64(), reader)
        else:
            await self._handle_service(msg_id, self.serializer.deserialize(body))

    def _handle_rpc_result(self, req_msg_id: int, reader: TLReader) -> None:
        pending = self._pending.pop(req_msg_id, None)
        if pending is None:
            log.debug("rpc_result for unknown msg_id %s", req_msg_id)
            return
        if pending.future.done():
            return
        try:
            if reader.peek_uint32() == RPC_ERROR_ID:
                error = self.serializer.deserialize(reader.rest())
                pending.future.set_exception(
                    rpc_error(
                        error.error_code, error.error_message, _innermost(pending.request).tl_name
                    )
                )
            else:
                pending.future.set_result(self.serializer.read(reader, pending.result_type))
        except Exception as exc:
            pending.future.set_exception(exc)

    async def _handle_service(self, msg_id: int, obj: Any) -> None:
        name = obj.tl_name if isinstance(obj, TLObject) else None
        if name == "pong":
            self._resolve(obj.msg_id, obj)
        elif name == "bad_server_salt":
            self.state.salt = obj.new_server_salt
            await self._resend(obj.bad_msg_id)
        elif name == "bad_msg_notification":
            await self._handle_bad_msg(msg_id, obj)
        elif name == "new_session_created":
            self.state.salt = obj.server_salt
            if self._on_new_session is not None:
                self._on_new_session()
        elif name == "future_salts":
            self._resolve(obj.req_msg_id, obj)
        elif name in ("msg_detailed_info", "msg_new_detailed_info"):
            self._acks.add(obj.answer_msg_id)
        elif name in ("msgs_ack", "destroy_session_ok", "destroy_session_none", "msgs_state_info"):
            return
        elif isinstance(obj, TLObject) and self._on_update is not None:
            self._on_update(obj)

    def _resolve(self, msg_id: int, result: Any) -> None:
        pending = self._pending.pop(msg_id, None)
        if pending is not None and not pending.future.done():
            pending.future.set_result(result)

    async def _handle_bad_msg(self, server_msg_id: int, notice: TLObject) -> None:
        code = notice.error_code
        state = self.state
        if code in (16, 17):
            state.ids.synchronize(server_msg_id)
        elif code == 32:
            state.shift_sequence(64)
        elif code == 33:
            state.shift_sequence(-16)
        else:
            pending = self._pending.pop(notice.bad_msg_id, None)
            if pending is not None and not pending.future.done():
                pending.future.set_exception(SecurityError(f"bad_msg_notification code {code}"))
            return
        await self._resend(notice.bad_msg_id)

    async def _resend(self, bad_msg_id: int) -> None:
        pending = self._pending.pop(bad_msg_id, None)
        if pending is None or pending.future.done():
            return
        if pending.attempts >= 5:
            pending.future.set_exception(SecurityError("Request rejected too many times"))
            return
        await self._transmit(pending)

    # --- UZ: ping va qayta ulanish / RU: ping и переподключение / EN: ping and reconnect ----
    async def _ping_loop(self) -> None:
        while not self._closing:
            await asyncio.sleep(self.ping_interval)
            if not self.connected:
                continue
            ping = functions.ping_delay_disconnect(
                ping_id=struct.unpack("<q", os.urandom(8))[0],
                disconnect_delay=int(self.ping_interval + 15),
            )
            try:
                await self.send(ping, timeout=min(30.0, self.ping_interval))
            except (asyncio.TimeoutError, TransportError) as exc:
                if not self._closing and self.connected:
                    self._start(self._reconnect(exc))

    async def _reconnect(self, reason: BaseException) -> None:
        if self._closing or not self._connected.is_set():
            return
        self._connected.clear()
        log.warning("Connection to DC %s lost (%s); reconnecting", self.dc_id, reason)
        if self._transport is not None:
            await self._transport.close()
            self._transport = None
        if isinstance(reason, AuthKeyNotFoundError):
            self.auth_key = None
            self._state = None
            if self._on_auth_key is not None:
                self._on_auth_key(None)
        for attempt in range(1, self.reconnect_retries + 1):
            await asyncio.sleep(self.reconnect_delay * attempt)
            if self._closing:
                return
            try:
                await self._open()
            except (TransportError, SecurityError) as exc:
                log.warning("Reconnect attempt %s failed: %s", attempt, exc)
                continue
            await self._after_reconnect()
            return
        log.error("Could not reconnect to DC %s", self.dc_id)
        self._fail_pending(TransportError("Connection lost"))
        await self.disconnect()
        if self._on_closed is not None:
            self._on_closed()

    async def _after_reconnect(self) -> None:
        pending = sorted(self._pending.values(), key=lambda item: item.msg_id)
        self._pending = {}
        if self._on_reconnect is not None:
            try:
                await self._on_reconnect()
            except Exception:
                log.exception("Re-initialising the connection failed")
        for item in pending:
            if not item.future.done():
                await self._transmit(item)


__all__ = ["MTProtoSender", "TransportFactory", "UpdateCallback"]
