# HTML-виджеты (Bot API 10.4)

Zafather отправляет виджеты в сообщениях Telegram и обрабатывает запросы данных
и кошелька. HTML после отправки неизменяем; бот отдельно обновляет состояние.
Виджет работает внутри Telegram без сети и текстового ввода. JavaScript-объект
`TelegramWidget` предоставляется клиентом, а не этим Python-пакетом.

## Отправка и ответ

```python
from zafather import WidgetQuery, Zafather

app = Zafather("TOKEN")

@app.command("start")
async def start(message):
    await message.answer_widget(
        "<button onclick=\"TelegramWidget.request('refresh')\">Refresh</button>",
        allow_queries=True,
        chat_data='{"n":0}',
        caption="Refresh the counter",
    )

@app.widget_query()
async def refresh(query: WidgetQuery):
    await query.answer('{"ok":true}')

app.run()
```

Отвечайте на каждый запрос за 15 секунд, включая ошибки. `query.answer()` не
передаёт данные результата; `query.answer("")` передаёт пустой результат. Оба
вызова не меняют состояние. Запускаемый `examples/widget_bot.py` хранит счётчик
на стороне бота, проверяет действия, обновляет состояние сообщения и обрабатывает
ошибки редактирования. Его счётчики в памяти исчезают при перезапуске; для
реального бота используйте постоянное хранилище.

## API и ярлыки

| Метод | Назначение |
|---|---|
| `Bot.send_widget(chat_id, html, **params)` | Создать обычный или общий виджет |
| `Bot.send_shared_widget(chat_id, widget_id, **params)` | Отправить существующий общий виджет |
| `Bot.answer_widget_query(widget_query_id, data=None)` | Ответить на исходный или пересланный запрос |
| `Bot.edit_message_widget_data(chat_id=..., message_id=..., chat_data=...)` | Изменить данные сообщения |
| `Bot.edit_message_widget_data(inline_message_id=..., public_data=...)` | Изменить данные inline-сообщения |
| `Bot.edit_shared_widget_data(widget_id, public_data, cache_time=...)` | Изменить общее состояние |

Методы отправки возвращают `Message`; `message.widget` имеет тип `Widget`.
Подпись, entities, клавиатура и остальные официальные параметры передаются через
`**params`. Стандартный parse mode бота применяется к подписи, а не HTML виджета.
`parse_mode=None` или `caption_entities` отключает стандартный parse mode.

Ярлыки сообщения: `answer_widget(html)`, `reply_widget(html)`,
`answer_shared_widget(widget_id)`, `edit_widget_data(...)`. Отправка сохраняет
тему форума и явные переопределения, но не наследует бизнес-подключение: у методов
отправки виджетов Bot API 10.4 такого параметра нет.
`message.external_reply.widget` также оборачивается в `Widget`.

`@app.widget_query(...)` обрабатывает исходные и inline-запросы `WidgetQuery`;
`@app.shared_widget_query(...)` — `SharedWidgetQuery` из пересланного общего
виджета. Работают обычные фильтры, middleware, DI, `state=` и вложенные роутеры.
Polling и установка webhook включают оба типа обновлений по умолчанию; при
собственном `allowed_updates` добавьте `widget_query` и `shared_widget_query`.

Исходные запросы имеют `answer(data)`, `edit_data(chat_data=..., public_data=...)`
и `edit_shared_data(public_data, cache_time=...)`. Пересланные — только `answer`
и `edit_shared_data`: Telegram не сообщает координаты чата/сообщения. В контексте
DI inline- и пересланного запроса `chat_id=None`, а не ID личного чата отправителя.
Inline-редактирование автоматически использует `inline_message_id`. Попытка
изменить общее состояние необщего виджета вызывает `ValueError`.

## Состояние и ограничения

Состояние и ответы — строки; сериализуйте JSON явно через `json.dumps`. `None`
пропускает поле и сохраняет данные; `""` очищает их. `chat_data` принадлежит
сообщению, общее `public_data` — его `widget_id`. Основное состояние меняет только
бот. Проверяйте недоверенное `query.data` по серверным записям; localStorage не
подходит для проверки голосов, владения или оплаты.

Проверка выполняется до HTTP, включая `Bot.call`/`request` и сырые inline-словари:
HTML — 1–32768 байт UTF-8, после zlib-9 не более 4096; каждое состояние и данные
ответа — до 1024 байт UTF-8. HTML и состояние запрещают NUL и некорректный UTF-8.
`widget_size(html)` возвращает исходный и сжатый размеры. Отправляйте HTML без
сжатия. Ширина и высота — целые пиксельные размеры; ноль означает автоматический
размер, остальные целые размеры ограничивает Telegram.

Для редактирования нужны либо `chat_id` с `message_id`, либо `inline_message_id`,
но не оба варианта. Время кеширования — целое число от 5 секунд; значения выше
3600 Telegram ограничивает до 3600. Без параметра сохраняется текущий период
(изначально 30 секунд). Некорректный ввод вызывает `TypeError`/`ValueError`;
ошибки API и сети сохраняют типы исключений framework. По умолчанию записи не
повторяются после потери ответа сети. Приложение может считать “message is not
modified” успешным исходом, но всё равно должно ответить на запрос.

Для живого общего состояния клиент вызывает `TelegramWidget.watchPublicData()`.
Добавляйте растущую ревизию в состояние и ответы, чтобы отбрасывать устаревшие
результаты опроса. Объединяйте общие правки до одной в секунду. Лимит запросов —
5 за 5 секунд на пользователя/бота; у виджета одновременно выполняется один запрос.

## Inline-режим и кошелёк

```python
from zafather import InputSharedWidgetMessageContent, InputWidgetMessageContent

content = InputWidgetMessageContent("<b>Price</b>", public_data='{"p":1}')
existing = InputSharedWidgetMessageContent("WIDGET_ID", caption="Live price")
await app.bot.answer_inline_query(inline_query_id="QUERY_ID", results=[{
    "type": "article", "id": "price", "title": "Price",
    "input_message_content": existing,
}])
```

Объекты сериализуются через `to_dict()`. `is_shared=True` в новом inline-результате
создаёт отдельный общий виджет при каждой отправке. Для одного состояния сначала
создайте виджет через `send_widget(..., is_shared=True)` и используйте повторно
`sent.widget.id`.

`query.type` автоматически становится `WidgetQueryTypeData`,
`WidgetQueryTypeSignData` или `WidgetQueryTypeSentTransaction`; неизвестные будущие
типы остаются `WidgetQueryType` без потери полей. `wallet_card` и `wallet`
оборачиваются в `TonWalletCard` и `WidgetQueryWallet`. Адреса и балансы остаются
строками; `sign_data` сохраняет исходную JSON-строку. Фильтруйте через
`F.type.type == "data"` или другие имена вариантов. Backend обязан проверять
подписи и транзакции в блокчейне. Уведомление о транзакции не доказывает оплату;
после таймаута проверьте заказ перед повторной оплатой. Пакет не реализует
проверку TON-транзакций и подписей.

## Доступность и проверка

По документации на 11 ноября 2026 production поддерживает только личные чаты с
ботом; виджеты защищены и не пересылаются. Группы, inline-отправка и пересылка —
возможности тестового сервера. Для тестовых ботов задайте
`Zafather(..., api_url=TelegramAPIServer(test_environment=True))`.
Виджеты нельзя отправлять прямо в каналы или копировать.

Офлайн-тесты проверяют сериализацию, маршрутизацию и ограничения, но не отрисовку
Telegram. Перед развёртыванием проверьте клиенты, светлую/тёмную темы, узкие экраны,
положение подписи, перезапуск, ошибки запросов и обновление общего состояния.

Источники: [руководство](https://core.telegram.org/bots/widgets),
[Bot API](https://core.telegram.org/bots/api#sendwidget).
