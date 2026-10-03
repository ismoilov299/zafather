"""UZ: Zafather — FSM (holatlar mashinasi).
RU: Zafather — FSM (машина состояний).
EN: Zafather — FSM (finite state machine).

UZ: Misol / RU: Пример / EN: Example::

    class Form(StatesGroup):
        name = State()
        age = State()

    @bot.command("start")
    async def start(message: Message, state: FSMContext):
        await state.set_state(Form.name)
        await message.answer("Ismingiz?")
"""

from .context import FSMContext
from .state import ANY_STATE, State, StatesGroup
from .storage import BaseStorage, JSONStorage, MemoryStorage, RedisStorage, StorageKey
from .strategy import FSMStrategy

__all__ = [
    "ANY_STATE",
    "BaseStorage",
    "FSMContext",
    "FSMStrategy",
    "JSONStorage",
    "MemoryStorage",
    "RedisStorage",
    "State",
    "StatesGroup",
    "StorageKey",
]
