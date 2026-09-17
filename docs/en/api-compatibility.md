# Bot API Compatibility

Zafather declares its supported Telegram Bot API level through
`BOT_API_VERSION`.

| Zafather | Bot API | Status |
|---|---:|---|
| main | 10.3 | In progress |
| 0.4.1 | 10.2 | Released |

## Rules for 10.3

- Ephemeral messages are sent through `ephemeral_message_parameters`.
- Rich draft streams always send `draft_id`.
- The `stopped_message_generation` update is accepted by the router.
