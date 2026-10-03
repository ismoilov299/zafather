"""UZ: Zafather — matn formatlash va **premium (custom) emoji**.
RU: Zafather — форматирование текста и **premium (custom) emoji**.
EN: Zafather — text formatting and **premium (custom) emoji**.

UZ: Ikki yo'l bor / RU: Есть два способа / EN: There are two ways:

1. UZ: HTML yorliqlari (tavsiya etiladi). RU: HTML-ярлыки (рекомендуется).
   EN: HTML helpers (recommended)::

       await message.answer(f"{emoji('5368324170671202286', '🔥')} {bold('Chegirma!')}")

2. UZ: Entity ro'yxati (`parse_mode` kerak emas). RU: Список entity (`parse_mode` не нужен).
   EN: An entity list (no `parse_mode` needed)::

       tb = TextBuilder().emoji("5368324170671202286", "🔥").text(" ").bold("50%")
       await message.answer(**tb.as_kwargs())

UZ: Bot API 9.4: custom emoji yuborish uchun **bot egasida Telegram Premium** bo'lishi
yoki bot Fragment'da username sotib olgan bo'lishi kerak.
RU: Bot API 9.4: для отправки custom emoji **у владельца бота должен быть Telegram
Premium** либо бот должен иметь купленный в Fragment username.
EN: Bot API 9.4: sending custom emoji requires **Telegram Premium for the bot owner**
or a username bought on Fragment.
"""

from __future__ import annotations

import html as _html
import re
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import quote as _url_quote


class SafeHTML(str):
    """UZ: Tayyor HTML — qayta ekranlanmaydi. RU: Готовый HTML — повторно не экранируется.
    EN: Ready-made HTML that is never escaped again.
    """

    __slots__ = ()


def escape(text: Any) -> str:
    """UZ: HTML matn uchun ekranlash (`SafeHTML` o'zgarishsiz qaytadi).
    RU: Экранирование для HTML-текста (`SafeHTML` возвращается без изменений).
    EN: Escapes text for HTML (`SafeHTML` is returned unchanged).
    """
    if isinstance(text, SafeHTML):
        return str(text)
    return _html.escape(str(text), quote=False)


def escape_attribute(value: Any) -> str:
    """UZ: HTML atribut qiymati uchun ekranlash. RU: Экранирование значения HTML-атрибута.
    EN: Escapes an HTML attribute value.
    """
    return _html.escape(str(value), quote=True)


def _wrap(tag: str, text: Any, attributes: str = "") -> SafeHTML:
    return SafeHTML(f"<{tag}{attributes}>{escape(text)}</{tag}>")


def bold(text: Any) -> SafeHTML:
    return _wrap("b", text)


def italic(text: Any) -> SafeHTML:
    return _wrap("i", text)


def underline(text: Any) -> SafeHTML:
    return _wrap("u", text)


def strike(text: Any) -> SafeHTML:
    return _wrap("s", text)


def spoiler(text: Any) -> SafeHTML:
    return _wrap("tg-spoiler", text)


def code(text: Any) -> SafeHTML:
    return _wrap("code", text)


def pre(text: Any, language: str | None = None) -> SafeHTML:
    if language:
        inner = _wrap("code", text, f' class="language-{escape_attribute(language)}"')
        return SafeHTML(f"<pre>{inner}</pre>")
    return _wrap("pre", text)


def link(text: Any, url: str) -> SafeHTML:
    return _wrap("a", text, f' href="{escape_attribute(url)}"')


def mention(text: Any, user_id: int) -> SafeHTML:
    return link(text, f"tg://user?id={int(user_id)}")


def quote(text: Any, expandable: bool = False) -> SafeHTML:
    """UZ: Sitata; `expandable=True` — yig'iladigan. RU: Цитата; `expandable=True` — сворачиваемая.
    EN: A quote block; `expandable=True` makes it collapsible.
    """
    return _wrap("blockquote", text, " expandable" if expandable else "")


def emoji(custom_emoji_id: str | int, fallback: str = "⭐️") -> SafeHTML:
    """UZ: Premium (custom) emoji; `fallback` — ko'rinmasa chiqadigan oddiy emoji.
    RU: Premium (custom) emoji; `fallback` — обычный emoji, если custom не отображается.
    EN: Premium (custom) emoji; `fallback` is shown when the custom one is unavailable.
    """
    return SafeHTML(
        f'<tg-emoji emoji-id="{escape_attribute(custom_emoji_id)}">{escape(fallback)}</tg-emoji>'
    )


def hashtag(tag: str, chat_username: str | None = None) -> SafeHTML:
    """UZ: Hashtag; `chat_username` berilsa, o'sha chatda qidiradigan havola.
    RU: Хештег; с `chat_username` — ссылка на поиск в этом чате.
    EN: A hashtag; with `chat_username` it links to a search in that chat.
    """
    tag = tag.lstrip("#")
    if chat_username:
        url = f"https://t.me/{chat_username.lstrip('@')}?q={_url_quote('#' + tag)}"
        return link(f"#{tag}", url)
    return SafeHTML(escape(f"#{tag}"))


def utf16_length(value: str) -> int:
    """UZ: Telegram entity'lari UTF-16 birliklarda hisoblanadi.
    RU: Entity Telegram считаются в единицах UTF-16.
    EN: Telegram entities are measured in UTF-16 code units.
    """
    return len(value.encode("utf-16-le")) // 2


class TextBuilder:
    """UZ: Matn va entity ro'yxatini birga quradi (`parse_mode` ishlatmasdan).
    RU: Собирает текст вместе со списком entity (без `parse_mode`).
    EN: Builds text together with its entity list (without `parse_mode`).

    UZ: `date_time` (9.5) kabi HTML'da yo'q entity'lar uchun ham kerak::
    RU: Нужен и для entity, которых нет в HTML, например `date_time` (9.5)::
    EN: Also needed for entities HTML lacks, such as `date_time` (9.5)::

        tb = TextBuilder("Uchrashuv: ").date_time("1-sentabr 10:00", unix_time=1788508800)
        await message.answer(**tb.as_kwargs())
    """

    def __init__(self, text: str = "") -> None:
        self._parts: list[str] = [text] if text else []
        self._length = utf16_length(text)
        self.entities: list[dict[str, Any]] = []

    @property
    def text_value(self) -> str:
        return "".join(self._parts)

    def _add(self, value: str, entity_type: str | None = None, **fields: Any) -> TextBuilder:
        length = utf16_length(value)
        if entity_type and length:
            entity = {"type": entity_type, "offset": self._length, "length": length}
            entity.update({key: item for key, item in fields.items() if item is not None})
            self.entities.append(entity)
        self._parts.append(value)
        self._length += length
        return self

    def text(self, value: str) -> TextBuilder:
        return self._add(value)

    def line(self, value: str = "") -> TextBuilder:
        return self._add(value + "\n")

    def bold(self, value: str) -> TextBuilder:
        return self._add(value, "bold")

    def italic(self, value: str) -> TextBuilder:
        return self._add(value, "italic")

    def underline(self, value: str) -> TextBuilder:
        return self._add(value, "underline")

    def strike(self, value: str) -> TextBuilder:
        return self._add(value, "strikethrough")

    def spoiler(self, value: str) -> TextBuilder:
        return self._add(value, "spoiler")

    def code(self, value: str) -> TextBuilder:
        return self._add(value, "code")

    def pre(self, value: str, language: str | None = None) -> TextBuilder:
        return self._add(value, "pre", language=language)

    def link(self, value: str, url: str) -> TextBuilder:
        return self._add(value, "text_link", url=url)

    def mention(self, value: str, user: Mapping[str, Any]) -> TextBuilder:
        return self._add(value, "text_mention", user=dict(user))

    def quote(self, value: str, expandable: bool = False) -> TextBuilder:
        return self._add(value, "expandable_blockquote" if expandable else "blockquote")

    def emoji(self, custom_emoji_id: str | int, fallback: str = "⭐️") -> TextBuilder:
        """UZ: Premium emoji entity. RU: Entity premium emoji. EN: A premium emoji entity."""
        return self._add(fallback, "custom_emoji", custom_emoji_id=str(custom_emoji_id))

    def date_time(self, value: str, **fields: Any) -> TextBuilder:
        """UZ: `date_time` entity (9.5); maydonlar rasmiy hujjat bo'yicha beriladi.
        RU: Entity `date_time` (9.5); поля передаются по официальной документации.
        EN: A `date_time` entity (9.5); fields follow the official documentation.
        """
        return self._add(value, "date_time", **fields)

    def entity(self, entity_type: str, value: str, **fields: Any) -> TextBuilder:
        """UZ: Istalgan entity turi. RU: Любой тип entity. EN: Any entity type."""
        return self._add(value, entity_type, **fields)

    def build(self) -> tuple[str, list[dict[str, Any]]]:
        return self.text_value, list(self.entities)

    def as_kwargs(self, text_field: str = "text") -> dict[str, Any]:
        """UZ: `await message.answer(**tb.as_kwargs())` uchun.
        RU: Для `await message.answer(**tb.as_kwargs())`.
        EN: For `await message.answer(**tb.as_kwargs())`.
        """
        entities_field = "entities" if text_field == "text" else f"{text_field}_entities"
        return {
            text_field: self.text_value,
            entities_field: list(self.entities),
            "parse_mode": None,
        }

    def __str__(self) -> str:
        return self.text_value

    def __len__(self) -> int:
        return len(self.text_value)


_CUSTOM_EMOJI_RE = re.compile(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>', re.S)


def strip_custom_emoji(text: str) -> str:
    """UZ: Premium emoji teglarini oddiy emojiga almashtiradi.
    RU: Заменяет теги premium emoji обычными emoji.
    EN: Replaces premium emoji tags with their plain fallbacks.
    """
    return _CUSTOM_EMOJI_RE.sub(r"\1", text)


def extract_custom_emoji_ids(entities: Iterable[Any]) -> list[str]:
    """UZ: Entity'lardagi barcha `custom_emoji_id` lar. RU: Все `custom_emoji_id` из entity.
    EN: Every `custom_emoji_id` found in the entities.
    """
    ids = []
    for entity in entities:
        raw = entity.raw if hasattr(entity, "raw") else entity
        if raw.get("type") == "custom_emoji" and raw.get("custom_emoji_id"):
            ids.append(str(raw["custom_emoji_id"]))
    return ids


__all__ = [
    "SafeHTML",
    "TextBuilder",
    "bold",
    "code",
    "emoji",
    "escape",
    "escape_attribute",
    "extract_custom_emoji_ids",
    "hashtag",
    "italic",
    "link",
    "mention",
    "pre",
    "quote",
    "spoiler",
    "strike",
    "strip_custom_emoji",
    "underline",
    "utf16_length",
]
