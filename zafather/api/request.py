"""UZ: Python qiymatlarini Bot API so'roviga aylantirish.
RU: Преобразование значений Python в запрос Bot API.
EN: Converting Python values into a Bot API request.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..files import InputFile

#: UZ: Matnli metodlar: (matn maydoni, entity maydoni).
#: RU: Методы с текстом: (поле текста, поле entity).
#: EN: Text-bearing methods: (text field, entities field).
FORMATTED_TEXT_FIELDS: Mapping[str, tuple[str, str]] = {
    "sendMessage": ("text", "entities"),
    "editMessageText": ("text", "entities"),
    "sendPhoto": ("caption", "caption_entities"),
    "sendVideo": ("caption", "caption_entities"),
    "sendAudio": ("caption", "caption_entities"),
    "sendDocument": ("caption", "caption_entities"),
    "sendAnimation": ("caption", "caption_entities"),
    "sendVoice": ("caption", "caption_entities"),
    "sendPaidMedia": ("caption", "caption_entities"),
    "copyMessage": ("caption", "caption_entities"),
    "editMessageCaption": ("caption", "caption_entities"),
}

#: UZ: `media` maydonida InputMedia qabul qiladigan metodlar.
#: RU: Методы, принимающие InputMedia в поле `media`.
#: EN: Methods that accept InputMedia in the `media` field.
MEDIA_METHODS = frozenset({"sendMediaGroup", "editMessageMedia"})


@dataclass
class RequestPayload:
    """UZ: Tayyor so'rov: JSON maydonlari va yuklanadigan fayllar.
    RU: Готовый запрос: JSON-поля и загружаемые файлы.
    EN: A prepared request: JSON fields and files to upload.
    """

    fields: dict[str, Any] = field(default_factory=dict)
    files: dict[str, InputFile] = field(default_factory=dict)

    @property
    def is_multipart(self) -> bool:
        return bool(self.files)


class PayloadBuilder:
    """UZ: Metod parametrlaridan `RequestPayload` yasaydi.
    RU: Собирает `RequestPayload` из параметров метода.
    EN: Builds a `RequestPayload` from method parameters.

    UZ: `None` qiymatlar tashlanadi. `parse_mode=None` aniq berilsa standart
    `parse_mode` qo'shilmaydi; `entities` berilganda ham qo'shilmaydi.
    RU: Значения `None` отбрасываются. Если явно передан `parse_mode=None` или
    переданы `entities`, стандартный `parse_mode` не добавляется.
    EN: `None` values are dropped. The default `parse_mode` is not added when
    `parse_mode=None` is passed explicitly or when entities are provided.
    """

    def __init__(self, default_parse_mode: str | None = None) -> None:
        self.default_parse_mode = default_parse_mode

    def build(self, method: str, params: Mapping[str, Any]) -> RequestPayload:
        payload = RequestPayload()
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, InputFile):
                payload.files[key] = value
            else:
                payload.fields[key] = self._convert(value, payload.files)
        if "parse_mode" not in params:
            self._apply_default_parse_mode(method, payload.fields)
        return payload

    def _convert(self, value: Any, files: dict[str, InputFile]) -> Any:
        if isinstance(value, InputFile):
            name = f"attachment{len(files)}"
            files[name] = value
            return f"attach://{name}"
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dt.datetime):
            return int(value.timestamp())
        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            return self._convert(to_dict(), files)
        if isinstance(value, Mapping):
            return {
                key: self._convert(item, files) for key, item in value.items() if item is not None
            }
        if isinstance(value, (list, tuple)):
            return [self._convert(item, files) for item in value]
        return value

    def _apply_default_parse_mode(self, method: str, fields: dict[str, Any]) -> None:
        parse_mode = self.default_parse_mode
        if parse_mode is None:
            return
        text_fields = FORMATTED_TEXT_FIELDS.get(method)
        if text_fields is not None:
            text_field, entities_field = text_fields
            if text_field in fields and entities_field not in fields:
                fields["parse_mode"] = parse_mode
        if method in MEDIA_METHODS:
            media = fields.get("media")
            for item in media if isinstance(media, list) else [media]:
                if (
                    isinstance(item, dict)
                    and "caption" in item
                    and "parse_mode" not in item
                    and "caption_entities" not in item
                ):
                    item["parse_mode"] = parse_mode


__all__ = ["FORMATTED_TEXT_FIELDS", "MEDIA_METHODS", "PayloadBuilder", "RequestPayload"]
