"""UZ: Zafather — matn formatlash va **premium (custom) emoji**.
RU: Zafather — форматирование текста и **premium (custom) emoji**.
EN: Zafather — text formatting and **premium (custom) emoji**.

UZ: Premium emoji ikki yo'l bilan qo'yiladi:
RU: Premium emoji можно вставить двумя способами:
EN: Premium emoji can be inserted in two ways:

1. UZ: HTML orqali (oddiy va tavsiya etiladi)::
   RU: Через HTML (просто и рекомендуется)::
   EN: Via HTML (simple and recommended)::

       from zafather import emoji, bold
       await m.answer(f"{emoji('5368324170671202286', '🔥')} {bold('Chegirma!')}")

2. UZ: Entity ro'yxati orqali (parse_mode kerak emas)::
   RU: Через список entity (parse_mode не нужен)::
   EN: Via entity list (parse_mode not required)::

       tb = TextBuilder()
       tb.emoji("5368324170671202286", "🔥").text(" Chegirma ").bold("50%")
       await m.answer(tb.text_value, entities=tb.entities)

UZ: Eslatma (Bot API 9.4): botlar custom emoji'ni to'g'ridan-to'g'ri yuborgan
xabarlarida ishlatishi mumkin, agar **bot egasida Telegram Premium** bo'lsa.
Fragment'da qo'shimcha username sotib olgan botlar uchun cheklov yo'q.
RU: Примечание (Bot API 9.4): боты могут отправлять custom emoji напрямую,
если **у владельца бота есть Telegram Premium**. Для ботов, купивших extra
username в Fragment, ограничения нет.
EN: Note (Bot API 9.4): bots can send custom emoji directly if the **bot owner
has Telegram Premium**. For bots that bought an extra username in Fragment,
there is no restriction.
"""
from __future__ import annotations

import html as _html
import re
from typing import List, Optional, Union

# --- HTML yorliqlari ----------------------------------------------------------


class SafeHTML(str):
    """UZ: Allaqachon HTML bo'lgan matn — qayta ekranlanmaydi.
    RU: Текст, который уже является HTML — повторно не экранируется.
    EN: Text that is already HTML — it is not escaped again.
    """


def escape(text: str) -> str:
    """UZ: HTML uchun xavfsiz qilish.
    RU: Экранирование для HTML.
    EN: Escaping for HTML.
    """
    if isinstance(text, SafeHTML):
        return str(text)
    return _html.escape(str(text), quote=False)


def emoji(custom_emoji_id: Union[str, int], fallback: str = "⭐️") -> str:
    """UZ: Premium (custom) emoji. `fallback` — emoji ko'rinmasa chiqadigan oddiy emoji.
    RU: Premium (custom) emoji. `fallback` — обычный emoji, если custom emoji не отображается.
    EN: Premium (custom) emoji. `fallback` is a regular emoji displayed if the custom one is unavailable.
    """
    return SafeHTML(f'<tg-emoji emoji-id="{custom_emoji_id}">{fallback}</tg-emoji>')


def bold(text: str) -> str:
    return SafeHTML(f"<b>{escape(text)}</b>")


def italic(text: str) -> str:
    return SafeHTML(f"<i>{escape(text)}</i>")


def underline(text: str) -> str:
    return SafeHTML(f"<u>{escape(text)}</u>")


def strike(text: str) -> str:
    return SafeHTML(f"<s>{escape(text)}</s>")


def spoiler(text: str) -> str:
    return SafeHTML(f"<tg-spoiler>{escape(text)}</tg-spoiler>")


def code(text: str) -> str:
    return SafeHTML(f"<code>{escape(text)}</code>")


def pre(text: str, language: Optional[str] = None) -> str:
    if language:
        return f'<pre><code class="language-{language}">{escape(text)}</code></pre>'
    return SafeHTML(f"<pre>{escape(text)}</pre>")


def link(text: str, url: str) -> str:
    return f'<a href="{url}">{escape(text)}</a>'


def mention(text: str, user_id: int) -> str:
    return f'<a href="tg://user?id={user_id}">{escape(text)}</a>'


def quote(text: str, expandable: bool = False) -> str:
    """UZ: Sitata bloki. `expandable=True` — yig'iladigan sitata.
    RU: Блок цитаты. `expandable=True` — раскрываемая цитата.
    EN: Quote block. `expandable=True` creates a collapsible quote.
    """
    attr = " expandable" if expandable else ""
    return SafeHTML(f"<blockquote{attr}>{escape(text)}</blockquote>")


def hashtag(tag: str, chat_username: Optional[str] = None) -> str:
    """UZ: Hashtag; `chat_username` berilsa, o'sha chatda qidiradi.
    RU: Hashtag; если передан `chat_username`, поиск идёт в этом чате.
    EN: Hashtag; if `chat_username` is passed, it searches in that chat.
    """
    tag = tag.lstrip("#")
    if chat_username:
        return f'<a href="https://t.me/{chat_username.lstrip("@")}?q=%23{tag}">#{tag}</a>'
    return SafeHTML(f"#{tag}")


# --- Entity quruvchi ----------------------------------------------------------


class TextBuilder:
    """UZ: Matn + entity ro'yxatini birga quradi (parse_mode ishlatmasdan).
    RU: Собирает текст + список entity в одном объекте (без parse_mode).
    EN: Builds text + an entity list together (without parse_mode).

    UZ: `date_time` (Bot API 9.5) kabi HTML'da mavjud bo'lmagan entity'lar uchun kerak::
    RU: Нужен для entity, которых нет в HTML, например `date_time` (Bot API 9.5)::
    EN: Useful for entity types not available in HTML, such as `date_time` (Bot API 9.5)::

        tb = TextBuilder("Uchrashuv: ").date_time("1-sentabr 10:00", timestamp=1788508800)
        await m.answer(tb.text_value, entities=tb.entities)
    """

    def __init__(self, text: str = "") -> None:
        self._parts: List[str] = [text] if text else []
        self.entities: List[dict] = []

    # --- ichki -----------------------------------------------------------------
    @property
    def text_value(self) -> str:
        return "".join(self._parts)

    @property
    def _offset(self) -> int:
        """UTF-16 kod birliklarida offset (Telegram shunday hisoblaydi)."""
        return len(self.text_value.encode("utf-16-le")) // 2

    @staticmethod
    def _length(value: str) -> int:
        return len(value.encode("utf-16-le")) // 2

    def _add(self, value: str, entity_type: Optional[str] = None, **fields) -> "TextBuilder":
        if entity_type:
            self.entities.append(
                {
                    "type": entity_type,
                    "offset": self._offset,
                    "length": self._length(value),
                    **{k: v for k, v in fields.items() if v is not None},
                }
            )
        self._parts.append(value)
        return self

    # --- ommaviy API -----------------------------------------------------------
    def text(self, value: str) -> "TextBuilder":
        return self._add(value)

    def line(self, value: str = "") -> "TextBuilder":
        return self._add(value + "\n")

    def bold(self, value: str) -> "TextBuilder":
        return self._add(value, "bold")

    def italic(self, value: str) -> "TextBuilder":
        return self._add(value, "italic")

    def underline(self, value: str) -> "TextBuilder":
        return self._add(value, "underline")

    def strike(self, value: str) -> "TextBuilder":
        return self._add(value, "strikethrough")

    def spoiler(self, value: str) -> "TextBuilder":
        return self._add(value, "spoiler")

    def code(self, value: str) -> "TextBuilder":
        return self._add(value, "code")

    def pre(self, value: str, language: Optional[str] = None) -> "TextBuilder":
        return self._add(value, "pre", language=language)

    def link(self, value: str, url: str) -> "TextBuilder":
        return self._add(value, "text_link", url=url)

    def mention(self, value: str, user: dict) -> "TextBuilder":
        return self._add(value, "text_mention", user=user)

    def quote(self, value: str, expandable: bool = False) -> "TextBuilder":
        return self._add(value, "expandable_blockquote" if expandable else "blockquote")

    def emoji(self, custom_emoji_id: Union[str, int], fallback: str = "⭐️") -> "TextBuilder":
        """Premium (custom) emoji entity."""
        return self._add(fallback, "custom_emoji", custom_emoji_id=str(custom_emoji_id))

    def date_time(self, value: str, **fields) -> "TextBuilder":
        """UZ: `date_time` entity (Bot API 9.5) — sanani foydalanuvchi mahalliy
        vaqtida ko'rsatadi. Qo'shimcha maydonlar rasmiy hujjat bo'yicha
        uzatiladi (masalan `timestamp=...`).
        RU: `date_time` entity (Bot API 9.5) — показывает дату в локальном времени
        пользователя. Дополнительные поля передаются по документации
        (например, `timestamp=...`).
        EN: `date_time` entity (Bot API 9.5) shows a date in the user's local time.
        Extra fields follow the API docs (for example `timestamp=...`).
        """
        return self._add(value, "date_time", **fields)

    def entity(self, entity_type: str, value: str, **fields) -> "TextBuilder":
        """Ixtiyoriy entity turi — kelajakdagi yangiliklar uchun."""
        return self._add(value, entity_type, **fields)

    # --- natija ----------------------------------------------------------------
    def build(self) -> tuple:
        return self.text_value, self.entities

    def as_kwargs(self) -> dict:
        """`await m.answer(**tb.as_kwargs())` uchun."""
        return {"text": self.text_value, "entities": self.entities, "parse_mode": None}

    def __str__(self) -> str:
        return self.text_value

    def __len__(self) -> int:
        return len(self.text_value)


# --- yordamchilar -------------------------------------------------------------

_CUSTOM_EMOJI_RE = re.compile(r'<tg-emoji emoji-id="(\d+)">(.*?)</tg-emoji>', re.S)


def strip_custom_emoji(text: str) -> str:
    """Premium emoji teglarini oddiy emojiga tushiradi (Premium bo'lmaganda)."""
    return _CUSTOM_EMOJI_RE.sub(r"\2", text)


def extract_custom_emoji_ids(message) -> List[str]:
    """Xabardagi barcha custom_emoji_id larni qaytaradi."""
    ids = []
    for entity in (message.entities or []) + (message.caption_entities or []):
        raw = entity.raw if hasattr(entity, "raw") else entity
        if raw.get("type") == "custom_emoji" and raw.get("custom_emoji_id"):
            ids.append(raw["custom_emoji_id"])
    return ids
