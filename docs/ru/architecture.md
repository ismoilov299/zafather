# Архитектура

Zafather разделен на небольшие слои. У каждого слоя одна задача, и он опирается
на абстракции нижележащего слоя, поэтому любую часть можно заменить или
протестировать отдельно.

## Сторона Bot API

```text
Zafather (app.py)               фасад: router + dispatcher + polling/webhook + жизненный цикл
 ├─ Router (router.py)          обработчики, фильтры, middleware, вложенные роутеры
 ├─ Dispatcher (dispatcher.py)  контекст одного update, FSM, обработчики ошибок
 ├─ LongPolling / WebhookServer получение update
 └─ Bot (bot.py)                методы Bot API
     └─ api/                    BaseSession, PayloadBuilder, RetryPolicy, TelegramAPIServer
```

| Модуль | Ответственность |
|---|---|
| `api/session.py` | интерфейс `BaseSession` и стандартная `AiohttpSession` (только HTTP) |
| `api/request.py` | `PayloadBuilder`: значения Python в поля формы и файлы |
| `api/retry.py` | `RetryPolicy`: сетевые ошибки, `retry_after`, ответы 5xx |
| `api/server.py` | `TelegramAPIServer`: адреса Bot API, в том числе собственного сервера |
| `bot.py` | `Bot`: типизированные помощники и любой метод в виде `bot.method_name(...)` |
| `exceptions.py` | иерархия `TelegramAPIError` (`BadRequest`, `Forbidden`, `RetryAfter`, ...) |
| `types/` | обертки `TelegramObject` (`Message`, `CallbackQuery`, ...) с короткими методами |
| `handler.py` | `CallableSpec`: сигнатура обработчика разбирается один раз, аргументы передаются по имени |
| `filters.py`, `magic.py` | классы `Filter` и магический фильтр `F` |
| `router.py` | регистрация обработчиков, внешние и внутренние middleware, вложенные роутеры |
| `dispatcher.py` | контекст каждого update, контекст FSM, обработчики ошибок |
| `polling.py`, `webhook.py` | источники update с мягким `stop()` и лимитом параллельной обработки |
| `fsm/` | `State`, `StatesGroup`, `FSMContext`, стратегии ключей и хранилища |

Пишущие запросы, ответ на которые потерян (например, `sendMessage`), по умолчанию
не повторяются (`RetryPolicy(retry_unsafe_methods=False)`), поэтому сбой сети не
может отправить сообщение дважды. Читающие методы `get*` повторяются.

### SOLID на практике

- **Единственная ответственность**: HTTP, сборка запроса, повторы и адреса
  серверов живут в отдельных классах; `Bot` только объединяет их.
- **Открытость/закрытость**: новые фильтры, middleware, хранилища, сессии и
  стратегии FSM добавляются наследованием; ядро не меняется.
- **Подстановка Лисков**: любые реализации `BaseStorage` и `BaseSession`
  взаимозаменяемы; тесты подставляют `FakeSession`, не трогая `Bot`.
- **Разделение интерфейсов**: маленькие интерфейсы (`BaseSession`: `request`,
  `stream`, `close`; `BaseStorage`: состояние и данные) вместо одного большого
  базового класса.
- **Инверсия зависимостей**: `Bot(token, session=...)` и
  `Zafather(token, storage=..., session=..., retry=...)` принимают абстракции.

## Сторона MTProto (userbot)

```text
UserBot (userbot.py)                   фасад: FLOOD_WAIT, переподключение, помощники обработчиков
 └─ MTProtoClient (mtproto/client.py)  вход, сообщения, сущности, события
     ├─ UpdateProcessor (updates.py)   учет pts/qts, пропуски, getDifference
     ├─ EntityCache (entities.py)      access hash и username
     └─ MTProtoSender (sender.py)      шифрованная сессия, ack, контейнеры, переподключение
         ├─ AuthKeyGenerator (auth.py) обмен ключами Диффи-Хеллмана
         ├─ MTProtoState (state.py)    msg_id, seq_no, salt, упаковка AES-IGE
         ├─ Transport (transport/)     TCP с кадрированием Abridged или Intermediate
         └─ TL (tl/)                   парсер схемы и сериализатор (layer 229)
```

| Модуль | Ответственность |
|---|---|
| `tl/` | читает встроенную схему `.tl` во время работы; `functions` и `types` создают проверенные объекты |
| `crypto/` | AES-IGE, RSA (отпечатки, RSA_PAD), проверки DH, SRP для 2FA |
| `transport/` | интерфейс `Transport`, `TcpTransport`, `AbridgedCodec`, `IntermediateCodec` |
| `session/` | интерфейс `SessionStorage`: `MemorySession`, `FileSession` (0600, атомарно), `StringSession` |
| `dc.py` | таблица дата-центров, обновляется из `help.getConfig` |
| `errors.py` | иерархия `RPCError` (`FloodWaitError`, `PhoneMigrateError`, ...) |
| `parse.py` | HTML в `MessageEntity` со смещениями UTF-16 |
| `events.py` | `NewMessage`, `MessageEdited`, `MessageDeleted`, `CallbackQuery`, `Raw` |

## Точки расширения

| Задача | Что сделать |
|---|---|
| Другой HTTP-клиент | наследовать `BaseSession` и передать в `session=` |
| Другие правила повторов | `RetryPolicy(...)` и `retry=` |
| Постоянное хранилище FSM | наследовать `BaseStorage` (см. `RedisStorage`) |
| Свой фильтр | наследовать `Filter` или передать любую функцию |
| Middleware | `BaseMiddleware` или функция `(event, data, next_)` |
| Хранение сессии userbot | наследовать `SessionStorage` |
| Прокси или другой транспорт | `MTProtoClient(transport_factory=...)`, возвращающий `Transport` |
