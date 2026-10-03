# Bot API Compatibility

Zafather declares its supported Telegram Bot API level through
`BOT_API_VERSION`, and the MTProto schema layer through
`zafather.mtproto.schema_layer()`.

| Zafather | Bot API | MTProto layer | Status |
|---|---:|---:|---|
| 0.5.0 | 10.3 | 229 | Current |
| 0.4.2 | 10.2 | experimental | Released |
| 0.4.1 | 10.2 | — | Released |

## Rules for 10.3

- Ephemeral messages are sent through `ephemeral_message_parameters`.
- Rich draft streams always send `draft_id`.
- The `stopped_message_generation` update is accepted by the router.

## Methods that are not wrapped yet

Every Bot API method can be called even before Zafather adds a helper for it:
`await bot.bot.any_method_name(chat_id=..., ...)` turns `snake_case` into the
`camelCase` method name and serializes the arguments. Fields whose exact name is
not settled in the official docs are passed through `**params` instead of being
hard-coded.

## Updating the MTProto schema

The TL schema ships with the package (`zafather/mtproto/tl/data/api.tl`) and is
parsed at runtime, so no code generation is needed. To move to a newer layer,
replace that file with the official schema (keeping the `// LAYER N` line),
update the expected layer in `tests/mtproto/test_tl.py` and run the test suite;
it also checks that every constructor ID matches the CRC32 of its definition.
