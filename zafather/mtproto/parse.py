"""UZ: Userbot uchun HTML formatlash: HTML -> (matn, MessageEntity ro'yxati).
RU: HTML-форматирование для userbot: HTML -> (текст, список MessageEntity).
EN: HTML formatting for userbots: HTML -> (text, a MessageEntity list).

UZ: Teglar: b/strong, i/em, u/ins, s/strike/del, code, pre, a href, blockquote,
tg-spoiler, tg-emoji emoji-id. Offset'lar UTF-16 birliklarda.
RU: Теги: b/strong, i/em, u/ins, s/strike/del, code, pre, a href, blockquote,
tg-spoiler, tg-emoji emoji-id. Смещения в единицах UTF-16.
EN: Tags: b/strong, i/em, u/ins, s/strike/del, code, pre, a href, blockquote,
tg-spoiler, tg-emoji emoji-id. Offsets are UTF-16 code units.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

from .tl import TLObject, types

_SIMPLE_TAGS = {
    "b": "messageEntityBold",
    "strong": "messageEntityBold",
    "i": "messageEntityItalic",
    "em": "messageEntityItalic",
    "u": "messageEntityUnderline",
    "ins": "messageEntityUnderline",
    "s": "messageEntityStrike",
    "strike": "messageEntityStrike",
    "del": "messageEntityStrike",
    "tg-spoiler": "messageEntitySpoiler",
}


def _utf16(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.length = 0
        self.entities: list[TLObject] = []
        self._open: list[tuple[str, int, dict[str, Any]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "code" and self._open and self._open[-1][0] == "pre":
            language = attributes.get("class", "").removeprefix("language-")
            self._open[-1][2]["language"] = language
            self._open.append(("code-in-pre", self.length, {}))
            return
        if tag == "span" and "tg-spoiler" in attributes.get("class", ""):
            tag = "tg-spoiler"
        self._open.append((tag, self.length, attributes))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._open) - 1, -1, -1):
            opened, offset, attributes = self._open[index]
            if (
                opened == tag
                or (tag == "span" and opened == "tg-spoiler")
                or (tag == "code" and opened == "code-in-pre")
            ):
                del self._open[index]
                self._close(opened, offset, attributes)
                return

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        self.length += _utf16(data)

    def _close(self, tag: str, offset: int, attributes: dict[str, Any]) -> None:
        length = self.length - offset
        if length <= 0 or tag == "code-in-pre":
            return
        entity = _entity(tag, offset, length, attributes)
        if entity is not None:
            self.entities.append(entity)


def _entity(tag: str, offset: int, length: int, attributes: dict[str, Any]) -> TLObject | None:
    position = {"offset": offset, "length": length}
    simple = _SIMPLE_TAGS.get(tag)
    if simple is not None:
        return getattr(types, simple)(**position)
    if tag == "code":
        return types.messageEntityCode(**position)
    if tag == "pre":
        return types.messageEntityPre(language=attributes.get("language", ""), **position)
    if tag == "a" and attributes.get("href"):
        return types.messageEntityTextUrl(url=attributes["href"], **position)
    if tag == "blockquote":
        return types.messageEntityBlockquote(collapsed="expandable" in attributes, **position)
    if tag == "tg-emoji" and attributes.get("emoji-id"):
        return types.messageEntityCustomEmoji(document_id=int(attributes["emoji-id"]), **position)
    return None


def parse_html(html: str) -> tuple[str, list[TLObject]]:
    """UZ: HTML'ni matn va entity'larga ajratadi. RU: Разбирает HTML на текст и entity.
    EN: Splits HTML into plain text and entities.
    """
    parser = _Parser()
    parser.feed(html)
    parser.close()
    entities = sorted(parser.entities, key=lambda entity: (entity.offset, -entity.length))
    return "".join(parser.text), entities


__all__ = ["parse_html"]
