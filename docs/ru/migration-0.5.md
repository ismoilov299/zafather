# Переход на 0.5

В версии 0.5.0 библиотека переписана на основе чистых заменяемых слоев (см.
[Архитектура](architecture.md)). Большая часть кода ботов работает без
изменений; на этой странице перечислено то, что изменилось.

## Требования

- Python **3.10+** (3.9 больше не поддерживается).
- `requirements.txt` удален: зависимости описаны в `pyproject.toml`
  (для разработки — `pip install "zafather[dev]"`).

## Bot API

- Ошибки: каждая ошибка Bot API — наследник `TelegramAPIError` (`BadRequest`,
  `Unauthorized`, `Forbidden`, `NotFound`, `Conflict`, `RetryAfter`,
  `ServerError`, `MigrateToChat`). `TelegramError` остался как псевдоним, имена
  `method`, `code`, `description` и `parameters` не изменились.
- `parse_mode=None` теперь действительно отключает форматирование для этого
  вызова, а к сообщениям с `entities=` parse mode не добавляется.
- Пишущие запросы, ответ на которые потерян, автоматически не повторяются
  (`RetryPolicy(retry_unsafe_methods=True)` возвращает прежнее поведение).
- В update управляемых ботов бот доступен как `event.bot_id`; `event.bot` — всегда
  клиент, получивший update.

## FSM

- `StorageKey` теперь dataclass: `StorageKey(bot_id, chat_id, user_id,
  thread_id=None)`. Собственные хранилища должны принимать его вместо кортежа
  `(chat_id, user_id)`; для строкового ключа используйте `key.to_string()`.
- `JSONStorage` пишет атомарно и по-прежнему читает файлы формата 0.4: старая
  запись переносится при первом использовании ее ключа.
- `RedisStorage` переехал в `zafather.fsm.storage` (экспорт из `zafather`
  сохранен). Старый путь `zafather.storage` работает, но выдает
  `DeprecationWarning`.
- `Zafather(fsm_strategy=...)` определяет владельца состояния:
  `FSMStrategy.USER_IN_CHAT` (по умолчанию), `CHAT`, `GLOBAL_USER`,
  `USER_IN_TOPIC` или `CHAT_TOPIC`.

## Userbot (MTProto)

Экспериментальные части MTProto из 0.4 заменены полноценным клиентом:

| 0.4 | 0.5 |
|---|---|
| `MTProtoSession` | `zafather.mtproto.FileSession`, `StringSession`, `MemorySession` (старые JSON-файлы сессий читаются) |
| `AbridgedTransport`, `MTProtoTransportError` | `TcpTransport` + `AbridgedCodec`, `TransportError` |
| `TLRequest`, `TLReader`, `TLWriter` (верхний уровень) | `zafather.mtproto.functions` / `types`; низкоуровневые `TLReader`/`TLWriter` — в `zafather.mtproto` |
| `AuthHandshake`, `DHExchange`, `ResPQ`, `ServerDHParamsOk`, `DHGenOk` | внутренние: ключи авторизации создаются автоматически при `connect()` |
| `AuthKey`, `RSAPublicKey` (верхний уровень) | `zafather.mtproto.AuthKey`, `zafather.mtproto.RSAPublicKey` |
| `UserBot(..., transport=..., dc_host=..., dc_port=...)` | `UserBot(..., transport_factory=..., dc_overrides=...)` |
| `userbot.invoke(raw_bytes)` | `userbot.invoke(functions.<метод>(...))` |

`UserBot`, `MTProtoClient`, `Events` и `EventBuilder` по-прежнему
экспортируются из `zafather`.

## Тесты

Файлы тестов переехали в `tests/` и запускаются через `pytest` (см.
[Правило тестов и документации](testing-and-docs.md)).
