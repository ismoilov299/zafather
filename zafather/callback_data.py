"""UZ: CallbackData fabrikasi.
RU: Фабрика CallbackData.
EN: CallbackData factory.
"""
from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from typing import Any, ClassVar


class CallbackData:
    """UZ: callback_data payloadini xafsiz va qisqa qilib to'plovchi sinf.
    RU: Класс для безопасной и компактной сборки callback_data payload.
    EN: Class for compact and safe callback_data payload generation.

    UZ: Misol:
        class Action(CallbackData, prefix="act"):
            name: str
            item_id: int

        packed = Action(name="delete", item_id=42).pack()
    """

    __prefix__: ClassVar[str] = ""
    __slots__ = ()

    def __init_subclass__(cls, prefix: str = "", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if prefix:
            cls.__prefix__ = prefix

    def __init__(self, **values: Any) -> None:
        self.__dict__.update(values)

    def pack(self) -> str:
        payload = {"p": self.__prefix__, "d": self.__dict__}
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(raw) > 64:
            raise ValueError(f"callback_data payload 64 baytdan oshdi: {len(raw)} bayt")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @classmethod
    def unpack(cls, value: str) -> "CallbackData":
        try:
            padded = value + "=" * (-len(value) % 4)
            raw = base64.urlsafe_b64decode(padded.encode("ascii"))
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            raise ValueError(f"callback_data ni ochib bo'lmadi: {value!r}") from exc
        payload = data.get("d", {})
        obj = cls(**payload)
        return obj

    @classmethod
    def filter(cls, *filters):
        """UZ: `Action.filter(F.name == "delete")` uslubidagi filter.
        RU: Фильтр в стиле `Action.filter(F.name == "delete")`.
        EN: Filter style like `Action.filter(F.name == "delete")`.
        """
        def predicate(event, data: dict = None):
            payload = None
            if isinstance(data, dict):
                payload = data.get("data")
            if payload is None and hasattr(event, "data"):
                payload = getattr(event, "data")
            if payload is None and isinstance(event, dict):
                payload = event.get("data")
            if payload is None:
                return False
            try:
                obj = cls.unpack(payload)
            except ValueError:
                return False
            values = obj.__dict__
            target = SimpleNamespace(**values)
            if filters:
                match = filters[0]
                if hasattr(match, "_resolve"):
                    result = match._resolve(target)
                    return bool(result)
                return bool(match(target))
            return True

        return predicate


__all__ = ["CallbackData"]
