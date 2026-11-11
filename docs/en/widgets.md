# HTML widgets (Bot API 10.4)

Zafather sends Telegram message widgets and handles their data and wallet queries.
Widget HTML is immutable after sending; the bot changes state separately. The
widget runs inside Telegram, without network access or text input. JavaScript
`TelegramWidget` belongs to the client, not this Python package.

## Send and answer

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

Answer every query within 15 seconds, including failures. `query.answer()` sends
no result data; `query.answer("")` sends an empty result. Neither changes state.
The runnable `examples/widget_bot.py` keeps authoritative counters on the bot,
checks actions, updates message state and handles failed edits. Its in-memory
counters expire when the process restarts; use persistent storage in a real bot.

## API and shortcuts

| Method | Purpose |
|---|---|
| `Bot.send_widget(chat_id, html, **params)` | Create a static or shared widget |
| `Bot.send_shared_widget(chat_id, widget_id, **params)` | Send an existing shared widget |
| `Bot.answer_widget_query(widget_query_id, data=None)` | Answer an original or forwarded query |
| `Bot.edit_message_widget_data(chat_id=..., message_id=..., chat_data=...)` | Edit message state |
| `Bot.edit_message_widget_data(inline_message_id=..., public_data=...)` | Edit inline message state |
| `Bot.edit_shared_widget_data(widget_id, public_data, cache_time=...)` | Edit shared state |

Both send methods return `Message`; `message.widget` is `Widget`. Caption,
caption entities, reply markup and other documented parameters pass through
`**params`. The bot's default parse mode applies to captions, never widget HTML.
Explicit `parse_mode=None` or `caption_entities` disables the default.

Message shortcuts: `answer_widget(html)`, `reply_widget(html)`,
`answer_shared_widget(widget_id)` and `edit_widget_data(...)`. Sending preserves
forum topics and explicit overrides, but does not inherit a business connection:
widget send methods have no such parameter in Bot API 10.4.
`message.external_reply.widget` is also wrapped as `Widget`.

`@app.widget_query(...)` handles `WidgetQuery`, including inline messages.
`@app.shared_widget_query(...)` handles `SharedWidgetQuery` from forwarded shared
widgets. Both accept normal filters, middleware, DI and `state=` filters, and work
on nested routers. Polling and webhook setup include both update types by default;
if supplying `allowed_updates`, include `widget_query` and `shared_widget_query`.

Original queries offer `answer(data)`, `edit_data(chat_data=..., public_data=...)`
and `edit_shared_data(public_data, cache_time=...)`. Forward queries offer only
`answer` and `edit_shared_data`: Telegram supplies no chat or message coordinates.
An inline or forwarded query has `chat_id=None` in the injected context, not the
sender's private chat ID. Inline edits use `inline_message_id` automatically.
Editing shared data from a non-shared original raises `ValueError`.

## State and limits

State and results are strings; serialize JSON explicitly with `json.dumps`.
`None` omits a field and preserves existing state; `""` clears it. `chat_data`
belongs to one message; shared `public_data` belongs to its `widget_id`.
Only the bot changes authoritative state. Check untrusted `query.data` against
server-side records; never trust localStorage for votes, ownership or payments.

Validation runs before HTTP, including direct `Bot.call`/`request` and raw inline
content dictionaries: HTML is 1–32768 UTF-8 bytes and at most 4096 bytes after
zlib level 9; state and answer data are at most 1024 UTF-8 bytes each. HTML and
state reject NUL and invalid UTF-8. `widget_size(html)` returns raw and compressed
sizes. Send plain HTML, not compressed bytes. Width and height are integer pixel
anchors; zero means automatic and Telegram clamps other integer sizes.

Message edits require either `chat_id` plus `message_id`, or `inline_message_id`,
never both. Shared cache time must be an integer of at least 5 seconds; Telegram
clamps values above 3600. Omission preserves the current period (initially 30).
Invalid input raises `TypeError` or `ValueError`; API and network errors retain
the framework's typed exceptions. Writes do not retry after an ambiguous network
failure by default. Edits may return “message is not modified”; the application
can treat that as success while still answering the query.

The client must call `TelegramWidget.watchPublicData()` for live shared state.
Use increasing revisions in state and answers to ignore stale poll results.
Throttle/coalesce shared edits to at most one per second. Requests are limited
to five per five seconds per user/bot; only one is in flight per widget.

## Inline mode and wallet

```python
from zafather import InputSharedWidgetMessageContent, InputWidgetMessageContent

content = InputWidgetMessageContent("<b>Price</b>", public_data='{"p":1}')
existing = InputSharedWidgetMessageContent("WIDGET_ID", caption="Live price")
await app.bot.answer_inline_query(inline_query_id="QUERY_ID", results=[{
    "type": "article", "id": "price", "title": "Price",
    "input_message_content": existing,
}])
```

The builders serialize with `to_dict()`. `is_shared=True` in a new inline result
creates a separate shared widget per send. To reuse one state, create it once
with `send_widget(..., is_shared=True)` and reuse `sent.widget.id`.

`query.type` automatically becomes `WidgetQueryTypeData`,
`WidgetQueryTypeSignData` or `WidgetQueryTypeSentTransaction`; unknown future
types remain `WidgetQueryType` without losing fields. Nested `wallet_card` and
`wallet` become `TonWalletCard` and `WidgetQueryWallet`. Wallet addresses and
balances remain strings. `sign_data` remains the original JSON string.
Use `F.type.type == "data"` (or the other variant names) to filter handlers.
The backend must verify signatures and transactions on-chain. A transaction
notification is not proof of payment; after a timeout, check order status before
asking the user to pay again. This package does not implement a TON verifier.

## Availability and verification

As documented on November 11, 2026, production supports private bot chats only;
widget messages are protected and cannot be forwarded. Groups, inline sending
and forwarding are test-server features. Configure
`TelegramAPIServer(test_environment=True)` via `Zafather(..., api_url=...)` for
test-server bots. Widgets cannot be sent directly to channels or copied.

Offline tests verify serialization, routing and limits, not Telegram rendering.
Before deployment, test supported clients, light/dark themes, narrow screens,
caption positions, client restarts, failed queries and shared-state refresh.

Sources: [widget guide](https://core.telegram.org/bots/widgets),
[Bot API](https://core.telegram.org/bots/api#sendwidget).
