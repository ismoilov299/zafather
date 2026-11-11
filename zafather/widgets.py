"""UZ: Widget kirish obyektlari va Bot API chegaralarini tekshirish.
RU: Входные объекты виджетов и проверка ограничений Bot API.
EN: Widget input objects and Bot API limit validation.
"""

from __future__ import annotations

import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


def _text(value: Any, name: str, maximum: int, *, minimum: int = 0, nul: bool = False) -> bytes:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} must be valid UTF-8") from exc
    if not minimum <= len(encoded) <= maximum:
        raise ValueError(f"{name} must contain {minimum}-{maximum} UTF-8 bytes")
    if not nul and "\0" in value:
        raise ValueError(f"{name} must not contain NUL")
    return encoded


def widget_size(html: str) -> tuple[int, int]:
    """UZ: HTML va zlib-9 hajmini baytlarda qaytaradi: `widget_size('<b>Hi</b>')`.
    RU: Возвращает размеры HTML и zlib-9 в байтах: `widget_size('<b>Hi</b>')`.
    EN: Returns HTML and zlib-9 sizes in bytes: `widget_size('<b>Hi</b>')`.
    """
    encoded = _text(html, "html", 32768, minimum=1)
    return len(encoded), len(zlib.compress(encoded, 9))


def _identifier(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_content(params: Mapping[str, Any], *, shared: bool = False) -> None:
    if shared:
        _identifier(params.get("widget_id"), "widget_id")
    else:
        html = params.get("html")
        if not isinstance(html, str):
            raise TypeError("html must be a string")
        if widget_size(html)[1] > 4096:
            raise ValueError("html must not exceed 4096 bytes after zlib level 9 compression")
        for name in ("width", "height"):
            value = params.get(name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                raise TypeError(f"{name} must be an integer")
    for name in ("chat_data",) if shared else ("chat_data", "public_data"):
        if params.get(name) is not None:
            _text(params[name], name, 1024)


def validate_widget_params(method: str, params: Mapping[str, Any]) -> None:
    """UZ: Widget so'rovini tekshiradi: `validate_widget_params('sendWidget', params)`.
    RU: Проверяет запрос виджета: `validate_widget_params('sendWidget', params)`.
    EN: Validates a widget request: `validate_widget_params('sendWidget', params)`.
    """
    if method in {"sendWidget", "sendSharedWidget"}:
        _validate_content(params, shared=method == "sendSharedWidget")
    elif method in {"editMessageWidgetData", "editSharedWidgetData"}:
        for name in ("public_data", "chat_data"):
            if params.get(name) is not None:
                _text(params[name], name, 1024)
        if method == "editSharedWidgetData":
            _identifier(params.get("widget_id"), "widget_id")
            _text(params.get("public_data"), "public_data", 1024)
            cache = params.get("cache_time")
            if cache is not None:
                if not isinstance(cache, int) or isinstance(cache, bool):
                    raise TypeError("cache_time must be an integer")
                if cache < 5:
                    raise ValueError("cache_time must be at least 5 seconds")
        else:
            inline = params.get("inline_message_id")
            chat, message = params.get("chat_id"), params.get("message_id")
            if inline is not None:
                _identifier(inline, "inline_message_id")
                if chat is not None or message is not None:
                    raise ValueError("Use inline_message_id OR chat_id and message_id")
            elif chat is None or message is None:
                raise ValueError("Provide inline_message_id OR both chat_id and message_id")
    elif method == "answerWidgetQuery":
        _identifier(params.get("widget_query_id"), "widget_query_id")
        if params.get("data") is not None:
            _text(params["data"], "data", 1024, nul=True)
    elif method == "answerInlineQuery":
        results = params.get("results")
        if isinstance(results, (list, tuple)):
            for result in results:
                content = (
                    result.get("input_message_content") if isinstance(result, Mapping) else None
                )
                if isinstance(content, Mapping):
                    if "html" in content and "widget_id" in content:
                        raise ValueError("Widget content cannot contain both html and widget_id")
                    if "html" in content or "widget_id" in content:
                        _validate_content(content, shared="widget_id" in content)


@dataclass
class InputWidgetMessageContent:
    """UZ: Inline widget: `InputWidgetMessageContent('<b>Hi</b>', allow_queries=True)`.
    RU: Inline-виджет: `InputWidgetMessageContent('<b>Hi</b>', allow_queries=True)`.
    EN: Inline widget: `InputWidgetMessageContent('<b>Hi</b>', allow_queries=True)`.
    """

    html: str
    width: int | None = None
    height: int | None = None
    public_data: str | None = None
    chat_data: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    caption_entities: Sequence[Any] | None = None
    show_caption_above_media: bool | None = None
    allow_queries: bool | None = None
    is_shared: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """UZ: API lug'ati: `content.to_dict()`. RU: Словарь API: `content.to_dict()`.
        EN: API dictionary: `content.to_dict()`.
        """
        data = {key: value for key, value in vars(self).items() if value is not None}
        _validate_content(data)
        return data


@dataclass
class InputSharedWidgetMessageContent:
    """UZ: Mavjud inline widget: `InputSharedWidgetMessageContent('widget-id')`.
    RU: Существующий inline-виджет: `InputSharedWidgetMessageContent('widget-id')`.
    EN: Existing inline widget: `InputSharedWidgetMessageContent('widget-id')`.
    """

    widget_id: str
    chat_data: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    caption_entities: Sequence[Any] | None = None
    show_caption_above_media: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """UZ: API lug'ati: `content.to_dict()`. RU: Словарь API: `content.to_dict()`.
        EN: API dictionary: `content.to_dict()`.
        """
        data = {key: value for key, value in vars(self).items() if value is not None}
        _validate_content(data, shared=True)
        return data


__all__ = ["InputSharedWidgetMessageContent", "InputWidgetMessageContent", "widget_size"]
