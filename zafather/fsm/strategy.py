"""UZ: FSM kaliti strategiyalari (holat kimga tegishli).
RU: Стратегии ключа FSM (кому принадлежит состояние).
EN: FSM key strategies (who owns a state).
"""

from __future__ import annotations

from enum import Enum

from .storage.base import StorageKey


class FSMStrategy(str, Enum):
    """UZ: Holat qaysi doirada saqlanishi.
    RU: В какой области хранится состояние.
    EN: The scope a state is stored in.

    UZ: `USER_IN_CHAT` — har bir chatdagi har bir foydalanuvchi (standart);
    `CHAT` — chat uchun umumiy; `GLOBAL_USER` — foydalanuvchi uchun barcha chatlarda
    bitta; `USER_IN_TOPIC`/`CHAT_TOPIC` — forum mavzusi bo'yicha alohida.
    RU: `USER_IN_CHAT` — каждый пользователь в каждом чате (по умолчанию); `CHAT` —
    общее на чат; `GLOBAL_USER` — одно на пользователя во всех чатах;
    `USER_IN_TOPIC`/`CHAT_TOPIC` — отдельно по темам форума.
    EN: `USER_IN_CHAT` — each user in each chat (default); `CHAT` — shared per chat;
    `GLOBAL_USER` — one per user across chats; `USER_IN_TOPIC`/`CHAT_TOPIC` — separate
    per forum topic.
    """

    USER_IN_CHAT = "user_in_chat"
    CHAT = "chat"
    GLOBAL_USER = "global_user"
    USER_IN_TOPIC = "user_in_topic"
    CHAT_TOPIC = "chat_topic"

    def build_key(
        self, bot_id: int, chat_id: int, user_id: int, thread_id: int | None = None
    ) -> StorageKey:
        if self is FSMStrategy.CHAT:
            return StorageKey(bot_id, chat_id, chat_id)
        if self is FSMStrategy.GLOBAL_USER:
            return StorageKey(bot_id, user_id, user_id)
        if self is FSMStrategy.USER_IN_TOPIC:
            return StorageKey(bot_id, chat_id, user_id, thread_id)
        if self is FSMStrategy.CHAT_TOPIC:
            return StorageKey(bot_id, chat_id, chat_id, thread_id)
        return StorageKey(bot_id, chat_id, user_id)


__all__ = ["FSMStrategy"]
