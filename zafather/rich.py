"""UZ: Zafather — **Rich Messages** (Bot API 10.1 / 10.3).
RU: Zafather — **Rich Messages** (Bot API 10.1 / 10.3).
EN: Zafather — **Rich Messages** (Bot API 10.1 / 10.3).

UZ: Rich message — sarlavha, ro'yxat, jadval, kod va yig'iladigan bo'limlardan iborat
tuzilgan xabar; AI javobini oqim bilan yuborish uchun ham ishlatiladi.
RU: Rich message — структурированное сообщение с заголовками, списками, таблицами,
кодом и раскрывающимися разделами; используется и для потоковых ответов ИИ.
EN: A rich message is a structured message with headings, lists, tables, code and
collapsible sections; it also powers streamed AI answers.

::

    rm = RichMessage().heading("Hisobot").paragraph("Bugungi ", bold("natijalar"))
    rm.table([["Oy", "Summa"], ["Avgust", "12 000"]], header=True)
    await message.answer_rich(rm)

    async with RichStream(app.bot, message.chat_id) as stream:
        async for chunk in llm_stream():
            await stream.push(chunk)
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import Iterable
from types import TracebackType
from typing import TYPE_CHECKING, Any

from .text import SafeHTML, escape, escape_attribute

if TYPE_CHECKING:
    from .bot import Bot

log = logging.getLogger("zafather.rich")


def _join(parts: Iterable[Any]) -> str:
    return "".join(escape(part) for part in parts)


class RichMessage:
    """UZ: Rich message'ni HTML ko'rinishida quradi; har bir metod `self` qaytaradi.
    RU: Собирает rich message в виде HTML; каждый метод возвращает `self`.
    EN: Builds a rich message as HTML; every method returns `self`.

    UZ: Kam uchraydigan bloklar uchun `tag()`, `raw()` va `block()` bor.
    RU: Для редких блоков есть `tag()`, `raw()` и `block()`.
    EN: `tag()`, `raw()` and `block()` cover less common blocks.
    """

    #: UZ: Matematik ifoda tegi. RU: Тег математического выражения. EN: Math expression tag.
    MATH_TAG = "tg-math"
    #: UZ: AI mulohazasi tegi. RU: Тег рассуждений ИИ. EN: AI reasoning tag.
    THINKING_TAG = "tg-thinking"

    def __init__(self, is_rtl: bool = False, skip_entity_detection: bool = False) -> None:
        self._parts: list[str] = []
        self._media: list[dict[str, Any]] = []
        self._blocks: list[dict[str, Any]] = []
        self.is_rtl = is_rtl
        self.skip_entity_detection = skip_entity_detection

    def _add(self, html: str) -> RichMessage:
        self._parts.append(html)
        return self

    # --- UZ: matn bloklari / RU: текстовые блоки / EN: text blocks ----------------------------
    def heading(self, *parts: Any, level: int = 1) -> RichMessage:
        level = max(1, min(6, level))
        return self._add(f"<h{level}>{_join(parts)}</h{level}>")

    def paragraph(self, *parts: Any) -> RichMessage:
        return self._add(f"<p>{_join(parts)}</p>")

    #: UZ: Qisqa nom. RU: Короткое имя. EN: Short alias.
    p = paragraph

    def quote(self, *parts: Any, expandable: bool = False) -> RichMessage:
        attribute = " expandable" if expandable else ""
        return self._add(f"<blockquote{attribute}>{_join(parts)}</blockquote>")

    def code(self, text: str, language: str | None = None) -> RichMessage:
        body = escape(text)
        if language:
            return self._add(
                f'<pre><code class="language-{escape_attribute(language)}">{body}</code></pre>'
            )
        return self._add(f"<pre>{body}</pre>")

    def divider(self) -> RichMessage:
        return self._add("<hr>")

    def thinking(self, *parts: Any) -> RichMessage:
        return self._add(f"<{self.THINKING_TAG}>{_join(parts)}</{self.THINKING_TAG}>")

    def math(self, expression: str) -> RichMessage:
        return self._add(f"<{self.MATH_TAG}>{escape(expression)}</{self.MATH_TAG}>")

    # --- UZ: ro'yxatlar / RU: списки / EN: lists ----------------------------------------------
    def bullets(self, items: Iterable[Any]) -> RichMessage:
        return self._add(f"<ul>{''.join(f'<li>{escape(item)}</li>' for item in items)}</ul>")

    def numbered(self, items: Iterable[Any], start: int = 1) -> RichMessage:
        attribute = f' start="{int(start)}"' if start != 1 else ""
        body = "".join(f"<li>{escape(item)}</li>" for item in items)
        return self._add(f"<ol{attribute}>{body}</ol>")

    def checklist(self, items: Iterable[Any]) -> RichMessage:
        """UZ: `["Bajarildi", ("Qoldi", False)]` — satr belgilangan, juftlik holat bilan.
        RU: `["Сделано", ("Осталось", False)]` — строка отмечена, пара задаёт состояние.
        EN: `["Done", ("Pending", False)]` — a string is checked, a pair sets the state.
        """
        rows = []
        for item in items:
            text, done = item if isinstance(item, tuple) else (item, True)
            checked = " checked" if done else ""
            rows.append(f'<li type="checkbox"{checked}>{escape(text)}</li>')
        return self._add(f"<ul>{''.join(rows)}</ul>")

    # --- UZ: jadval / RU: таблица / EN: table -------------------------------------------------
    def table(self, rows: Iterable[Iterable[Any]], header: bool = False) -> RichMessage:
        html_rows = []
        for index, row in enumerate(rows):
            cell = "th" if header and index == 0 else "td"
            html_rows.append(
                "<tr>" + "".join(f"<{cell}>{escape(value)}</{cell}>" for value in row) + "</tr>"
            )
        return self._add(f"<table>{''.join(html_rows)}</table>")

    def details(self, summary: Any, *content: Any) -> RichMessage:
        return self._add(f"<details><summary>{escape(summary)}</summary>{_join(content)}</details>")

    # --- UZ: media / RU: медиа / EN: media ----------------------------------------------------
    def image(self, src: str, caption: str | None = None) -> RichMessage:
        """UZ: Rasm (`file_id` yoki URL). RU: Изображение (`file_id` или URL).
        EN: An image (`file_id` or URL).
        """
        alt = f' alt="{escape_attribute(caption)}"' if caption else ""
        return self._add(f'<img src="{escape_attribute(src)}"{alt}>')

    def add_media(self, item: dict[str, Any]) -> RichMessage:
        self._media.append(item)
        return self

    # --- UZ: kengaytma / RU: расширение / EN: extension ---------------------------------------
    def tag(self, name: str, *content: Any, **attributes: Any) -> RichMessage:
        rendered = "".join(
            f' {key.replace("_", "-")}="{escape_attribute(value)}"'
            for key, value in attributes.items()
            if value is not None
        )
        return self._add(f"<{name}{rendered}>{_join(content)}</{name}>")

    def raw(self, html: str) -> RichMessage:
        return self._add(html)

    def block(self, block_type: str, **fields: Any) -> RichMessage:
        self._blocks.append({"type": block_type, **fields})
        return self

    # --- UZ: natija / RU: результат / EN: result ----------------------------------------------
    @property
    def html(self) -> str:
        return "".join(self._parts)

    def to_dict(self) -> dict[str, Any]:
        """UZ: `InputRichMessage` obyekti. RU: Объект `InputRichMessage`.
        EN: The `InputRichMessage` object.
        """
        payload: dict[str, Any] = {}
        if self._blocks:
            payload["blocks"] = list(self._blocks)
        if self._parts:
            payload["html"] = self.html
        if self._media:
            payload["media"] = list(self._media)
        if self.is_rtl:
            payload["is_rtl"] = True
        if self.skip_entity_detection:
            payload["skip_entity_detection"] = True
        return payload

    def __bool__(self) -> bool:
        return bool(self._parts or self._blocks)

    def __len__(self) -> int:
        return len(self.html)

    def __str__(self) -> str:
        return self.html

    def __repr__(self) -> str:
        return f"<RichMessage parts={len(self._parts)} chars={len(self.html)}>"


def markdown_rich(text: str, **options: Any) -> dict[str, Any]:
    """UZ: Markdown'dan `InputRichMessage`. RU: `InputRichMessage` из Markdown.
    EN: An `InputRichMessage` built from Markdown.
    """
    payload: dict[str, Any] = {"markdown": text}
    for key in ("is_rtl", "skip_entity_detection", "media", "blocks"):
        if options.get(key):
            payload[key] = options[key]
    return payload


class RichStream:
    """UZ: AI javobini bo'lak-bo'lak yuboradi (`sendRichMessageDraft`), oxirida
    `sendRichMessage` bilan yakunlaydi.
    RU: Отправляет ответ ИИ частями (`sendRichMessageDraft`) и завершает его через
    `sendRichMessage`.
    EN: Streams an AI answer in chunks (`sendRichMessageDraft`) and finalises it with
    `sendRichMessage`.

    UZ: `min_interval` — qoralamalar orasidagi eng kam vaqt (flood-limitdan himoya).
    Qoralama xatosi oqimni to'xtatmaydi.
    RU: `min_interval` — минимальный интервал между черновиками (защита от flood-limit).
    Ошибка черновика не останавливает поток.
    EN: `min_interval` is the minimum delay between drafts (flood protection). A draft
    error never stops the stream.
    """

    def __init__(
        self,
        bot: Bot,
        chat_id: int | str,
        *,
        draft_id: int | None = None,
        min_interval: float = 0.7,
        as_markdown: bool = True,
        thinking: str | None = None,
        can_stop: bool | None = None,
        keep_on_stop: bool | None = None,
        **send_params: Any,
    ) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.draft_id = draft_id or secrets.randbelow(2_147_483_646) + 1
        self.min_interval = min_interval
        self.as_markdown = as_markdown
        self.thinking = thinking
        self.can_stop = can_stop
        self.keep_on_stop = keep_on_stop
        self.send_params = send_params
        self._chunks: list[str] = []
        self._last_sent = 0.0
        self._dirty = False
        self.message: Any = None

    @property
    def text(self) -> str:
        return "".join(self._chunks)

    def _payload(self, final: bool = False) -> dict[str, Any]:
        if self.as_markdown:
            return {"markdown": self.text}
        rich = RichMessage()
        if self.thinking and not final:
            rich.thinking(self.thinking)
        return rich.paragraph(self.text).to_dict()

    async def push(self, chunk: str, force: bool = False) -> None:
        """UZ: Bo'lak qo'shadi va vaqti kelsa qoralamani yangilaydi.
        RU: Добавляет фрагмент и при необходимости обновляет черновик.
        EN: Appends a chunk and refreshes the draft when it is due.
        """
        if chunk:
            self._chunks.append(chunk)
            self._dirty = True
        if self._dirty and (force or time.monotonic() - self._last_sent >= self.min_interval):
            await self._send_draft()

    async def _send_draft(self) -> None:
        self._last_sent = time.monotonic()
        self._dirty = False
        params: dict[str, Any] = {
            "chat_id": self.chat_id,
            "draft_id": self.draft_id,
            "rich_message": self._payload(),
            "can_stop": self.can_stop,
            "keep_on_stop": self.keep_on_stop,
            **self.send_params,
        }
        try:
            await self.bot.call("sendRichMessageDraft", **params)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.debug("Draft update failed: %s", exc)

    async def finish(self, rich_message: RichMessage | dict[str, Any] | None = None) -> Any:
        """UZ: Yakuniy xabarni yuboradi. RU: Отправляет итоговое сообщение.
        EN: Sends the final message.
        """
        payload = self._payload(final=True) if rich_message is None else rich_message
        self.message = await self.bot.request(
            "sendRichMessage", chat_id=self.chat_id, rich_message=payload, **self.send_params
        )
        return self.message

    async def __aenter__(self) -> RichStream:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None and self.text:
            await self.finish()

    def __repr__(self) -> str:
        return f"<RichStream chat={self.chat_id} chars={len(self.text)}>"


__all__ = ["RichMessage", "RichStream", "SafeHTML", "markdown_rich"]
