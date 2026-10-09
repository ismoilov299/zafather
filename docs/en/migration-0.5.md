# Migrating to 0.5

Version 0.5.0 rewrites the library around clean, replaceable layers (see
[Architecture](architecture.md)). Most bot code keeps working unchanged; this
page lists what does not.

## Requirements

- Python **3.10+** (3.9 is no longer supported).
- `requirements.txt` is gone: dependencies are declared in `pyproject.toml`
  (`pip install "zafather[dev]"` for development).

## Bot API

- Exceptions: every Bot API error is a `TelegramAPIError` subclass
  (`BadRequest`, `Unauthorized`, `Forbidden`, `NotFound`, `Conflict`,
  `RetryAfter`, `ServerError`, `MigrateToChat`). `TelegramError` stays as an
  alias, and `method`, `code`, `description` and `parameters` keep their names.
- `parse_mode=None` now really disables formatting for that call, and messages
  sent with `entities=` never get a parse mode.
- Write requests whose response was lost are not retried automatically
  (`RetryPolicy(retry_unsafe_methods=True)` restores the old behaviour).
- Managed bot updates expose the bot as `event.bot_id`; `event.bot` is always the
  client that received the update.

## FSM

- `StorageKey` is now a dataclass: `StorageKey(bot_id, chat_id, user_id,
  thread_id=None)`. Custom storages must accept it instead of a
  `(chat_id, user_id)` tuple; use `key.to_string()` to build string keys.
- `JSONStorage` writes atomically and still reads files in the 0.4 format: an old
  entry is adopted the first time its key is used.
- `RedisStorage` moved to `zafather.fsm.storage` (it is still exported from
  `zafather`). The old `zafather.storage` import path works but emits a
  `DeprecationWarning`.
- `Zafather(fsm_strategy=...)` chooses who owns a state: `FSMStrategy.USER_IN_CHAT`
  (default), `CHAT`, `GLOBAL_USER`, `USER_IN_TOPIC` or `CHAT_TOPIC`.

## Userbot (MTProto)

The experimental 0.4 MTProto building blocks were replaced by a complete client:

| 0.4 | 0.5 |
|---|---|
| `MTProtoSession` | `zafather.mtproto.FileSession`, `StringSession`, `MemorySession` (old JSON session files are still read) |
| `AbridgedTransport`, `MTProtoTransportError` | `TcpTransport` + `AbridgedCodec`, `TransportError` |
| `TLRequest`, `TLReader`, `TLWriter` (top level) | `zafather.mtproto.functions` / `types`; low-level `TLReader`/`TLWriter` in `zafather.mtproto` |
| `AuthHandshake`, `DHExchange`, `ResPQ`, `ServerDHParamsOk`, `DHGenOk` | internal: authorization keys are created automatically on `connect()` |
| `AuthKey`, `RSAPublicKey` (top level) | `zafather.mtproto.AuthKey`, `zafather.mtproto.RSAPublicKey` |
| `UserBot(..., transport=..., dc_host=..., dc_port=...)` | `UserBot(..., transport_factory=..., dc_overrides=...)` |
| `userbot.invoke(raw_bytes)` | `userbot.invoke(functions.<method>(...))` |

`UserBot`, `MTProtoClient`, `Events` and `EventBuilder` are still exported from
`zafather`.

## Tests

The test files moved to `tests/` and run with `pytest` (see
[Testing and docs rule](testing-and-docs.md)).
