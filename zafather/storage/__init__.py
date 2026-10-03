"""UZ: Eskirgan import yo'li: `zafather.fsm.storage` (yoki `zafather`) dan foydalaning.
RU: Устаревший путь импорта: используйте `zafather.fsm.storage` (или `zafather`).
EN: A deprecated import path: use `zafather.fsm.storage` (or `zafather`) instead.
"""

import warnings

from ..fsm.storage import RedisStorage

warnings.warn(
    "zafather.storage is deprecated; import RedisStorage from zafather or zafather.fsm.storage",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["RedisStorage"]
