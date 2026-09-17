# Совместимость с Bot API

Zafather объявляет поддерживаемый уровень Telegram Bot API через
`BOT_API_VERSION`.

| Zafather | Bot API | Статус |
|---|---:|---|
| main | 10.3 | В работе |
| 0.4.1 | 10.2 | Опубликовано |

## Правила для 10.3

- Ephemeral-сообщения отправляются через `ephemeral_message_parameters`.
- Rich draft-потоки всегда отправляют `draft_id`.
- Update `stopped_message_generation` принимается через router.
