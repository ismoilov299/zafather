# Architecture

Zafather is split into small layers. Each layer has a single job and depends on
the abstractions of the layer below it, so any part can be replaced or tested in
isolation.

## Bot API side

```text
Zafather (app.py)               facade: router + dispatcher + polling/webhook + lifecycle
 ├─ Router (router.py)          handlers, filters, middlewares, nested routers
 ├─ Dispatcher (dispatcher.py)  context of one update, FSM, error handlers
 ├─ LongPolling / WebhookServer receive updates
 └─ Bot (bot.py)                Bot API methods
     └─ api/                    BaseSession, PayloadBuilder, RetryPolicy, TelegramAPIServer
```

| Module | Responsibility |
|---|---|
| `api/session.py` | `BaseSession` interface and the default `AiohttpSession` (HTTP only) |
| `api/request.py` | `PayloadBuilder`: Python values to form fields and files |
| `api/retry.py` | `RetryPolicy`: network errors, `retry_after`, 5xx responses |
| `api/server.py` | `TelegramAPIServer`: Bot API URLs, including a self-hosted server |
| `bot.py` | `Bot`: typed helpers plus any method as `bot.method_name(...)` |
| `exceptions.py` | the `TelegramAPIError` hierarchy (`BadRequest`, `Forbidden`, `RetryAfter`, ...) |
| `types/` | `TelegramObject` wrappers (`Message`, `CallbackQuery`, ...) with shortcuts |
| `handler.py` | `CallableSpec`: a handler signature is analysed once, arguments are injected by name |
| `filters.py`, `magic.py` | `Filter` classes and the `F` magic filter |
| `router.py` | handler registration, outer and inner middlewares, nested routers |
| `dispatcher.py` | per-update context, FSM context, error handlers |
| `polling.py`, `webhook.py` | update sources with a graceful `stop()` and a concurrency limit |
| `fsm/` | `State`, `StatesGroup`, `FSMContext`, key strategies and storages |

Write requests whose response was lost (for example `sendMessage`) are not
repeated by default (`RetryPolicy(retry_unsafe_methods=False)`), so a network
glitch cannot send a message twice. Read-only `get*` methods are retried.

### SOLID in practice

- **Single responsibility**: HTTP, payload building, retries and server URLs live
  in separate classes; `Bot` only composes them.
- **Open/closed**: new filters, middlewares, storages, sessions and FSM strategies
  are added by subclassing; the core does not change.
- **Liskov substitution**: every `BaseStorage` and `BaseSession` implementation is
  interchangeable; the tests swap in a `FakeSession` without touching `Bot`.
- **Interface segregation**: small interfaces (`BaseSession`: `request`, `stream`,
  `close`; `BaseStorage`: state and data) instead of one large base class.
- **Dependency inversion**: `Bot(token, session=...)` and
  `Zafather(token, storage=..., session=..., retry=...)` accept abstractions.

## MTProto side (userbots)

```text
UserBot (userbot.py)                   facade: FLOOD_WAIT retries, reconnects, handler helpers
 └─ MTProtoClient (mtproto/client.py)  login, messages, entities, events
     ├─ UpdateProcessor (updates.py)   pts/qts tracking, gaps, getDifference
     ├─ EntityCache (entities.py)      access hashes and usernames
     └─ MTProtoSender (sender.py)      encrypted session, acks, containers, reconnects
         ├─ AuthKeyGenerator (auth.py) Diffie-Hellman key exchange
         ├─ MTProtoState (state.py)    msg_id, seq_no, salt, AES-IGE packing
         ├─ Transport (transport/)     TCP with Abridged or Intermediate framing
         └─ TL (tl/)                   schema parser and serializer (layer 229)
```

| Module | Responsibility |
|---|---|
| `tl/` | parses the bundled `.tl` schema at runtime; `functions` and `types` build validated objects |
| `crypto/` | AES-IGE, RSA (fingerprints, RSA_PAD), DH checks, SRP for 2FA |
| `transport/` | the `Transport` interface, `TcpTransport`, `AbridgedCodec`, `IntermediateCodec` |
| `session/` | the `SessionStorage` interface: `MemorySession`, `FileSession` (0600, atomic), `StringSession` |
| `dc.py` | the data center table, refreshed from `help.getConfig` |
| `errors.py` | the `RPCError` hierarchy (`FloodWaitError`, `PhoneMigrateError`, ...) |
| `parse.py` | HTML to `MessageEntity` with UTF-16 offsets |
| `events.py` | `NewMessage`, `MessageEdited`, `MessageDeleted`, `CallbackQuery`, `Raw` |

## Extension points

| Need | Implement |
|---|---|
| Another HTTP client | subclass `BaseSession` and pass `session=` |
| Different retry behaviour | `RetryPolicy(...)` and `retry=` |
| Persistent FSM | subclass `BaseStorage` (see `RedisStorage`) |
| Custom filter | subclass `Filter` or pass any callable |
| Middleware | `BaseMiddleware` or an `(event, data, next_)` function |
| Userbot session storage | subclass `SessionStorage` |
| Proxy or another transport | `MTProtoClient(transport_factory=...)` returning a `Transport` |
