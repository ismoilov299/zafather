"""Zafather — **Rich Messages** (Bot API 10.1 / 10.2).

Rich message — sarlavhalar, ro'yxatlar, jadvallar, kod bloklari va yig'iladigan
bo'limlardan iborat tuzilgan xabar. AI javoblarini oqim bilan yuborish uchun
ham shu ishlatiladi.

`InputRichMessage` **html** yoki **markdown** maydonini qabul qiladi (ikkalasi
emas), qo'shimcha: `is_rtl`, `skip_entity_detection`, hamda 10.2 dan `blocks`
va `media`.

    rm = RichMessage()
    rm.heading("Hisobot")
    rm.paragraph("Bugungi ", bold("natijalar"), ":")
    rm.bullets(["Sotuv o'sdi", "Xarajat kamaydi"])
    rm.code("SELECT * FROM sales;", "sql")
    rm.table([["Oy", "Summa"], ["Avgust", "12 000"]], header=True)
    rm.details("Batafsil", "Yashirin matn")

    await m.answer_rich(rm)

AI javobini oqim bilan:

    async with RichStream(bot.bot, m.chat_id) as stream:
        async for chunk in llm_stream():
            await stream.push(chunk)
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Iterable, List, Optional, Union

from .text import SafeHTML, escape

__all__ = [
    "RichMessage",
    "RichStream",
    "markdown_rich",
]


def _esc(value: Any) -> str:
    """SafeHTML bo'lsa tegmaydi, aks holda ekranlaydi."""
    return str(value) if isinstance(value, SafeHTML) else escape(str(value))


def _join(parts: Iterable[Any]) -> str:
    return "".join(_esc(p) for p in parts)


class RichMessage:
    """Rich message'ni HTML ko'rinishida quradi.

    Har bir metod `self` qaytaradi — zanjir qilib yozish mumkin.

    Kamroq uchraydigan bloklar (xarita, kollaj, slayd-shou, matematik ifoda)
    uchun `tag()` va `raw()` mavjud: rasmiy hujjatdagi teg nomini bering.
    Matematik ifoda tegi `RichMessage.MATH_TAG` orqali sozlanadi.
    """

    #: Matematik ifoda tegi — rasmiy hujjatga qarab o'zgartirilishi mumkin
    MATH_TAG = "tg-math"
    #: "O'ylash" bloki (AI mulohazasi) tegi
    THINKING_TAG = "tg-thinking"

    def __init__(
        self,
        is_rtl: bool = False,
        skip_entity_detection: bool = False,
    ) -> None:
        self._parts: List[str] = []
        self._media: List[dict] = []
        self._blocks: List[dict] = []
        self.is_rtl = is_rtl
        self.skip_entity_detection = skip_entity_detection

    # --- matn bloklari --------------------------------------------------------
    def heading(self, *parts: Any, level: int = 1) -> "RichMessage":
        """Bo'lim sarlavhasi (1–6)."""
        level = max(1, min(6, level))
        self._parts.append(f"<h{level}>{_join(parts)}</h{level}>")
        return self

    def paragraph(self, *parts: Any) -> "RichMessage":
        """Oddiy abzats."""
        self._parts.append(f"<p>{_join(parts)}</p>")
        return self

    #: qisqa nom
    p = paragraph

    def quote(self, *parts: Any, expandable: bool = False) -> "RichMessage":
        """Sitata bloki. `expandable=True` — yig'iladigan."""
        attr = " expandable" if expandable else ""
        self._parts.append(f"<blockquote{attr}>{_join(parts)}</blockquote>")
        return self

    def code(self, text: str, language: Optional[str] = None) -> "RichMessage":
        """Kod bloki. `language` berilsa sintaksis bo'yaladi."""
        body = escape(text)
        if language:
            self._parts.append(f'<pre><code class="language-{language}">{body}</code></pre>')
        else:
            self._parts.append(f"<pre>{body}</pre>")
        return self

    def divider(self) -> "RichMessage":
        """Ajratuvchi chiziq."""
        self._parts.append("<hr>")
        return self

    def thinking(self, *parts: Any) -> "RichMessage":
        """AI mulohazasi bloki — javob tayyorlanayotganda ko'rsatiladi."""
        self._parts.append(f"<{self.THINKING_TAG}>{_join(parts)}</{self.THINKING_TAG}>")
        return self

    def math(self, expression: str) -> "RichMessage":
        """Matematik ifoda (LaTeX). Teg `RichMessage.MATH_TAG` bilan sozlanadi."""
        self._parts.append(f"<{self.MATH_TAG}>{escape(expression)}</{self.MATH_TAG}>")
        return self

    # --- ro'yxatlar -----------------------------------------------------------
    def bullets(self, items: Iterable[Any]) -> "RichMessage":
        """Belgili ro'yxat."""
        body = "".join(f"<li>{_esc(item)}</li>" for item in items)
        self._parts.append(f"<ul>{body}</ul>")
        return self

    def numbered(self, items: Iterable[Any], start: int = 1) -> "RichMessage":
        """Raqamli ro'yxat."""
        body = "".join(f"<li>{_esc(item)}</li>" for item in items)
        attr = f' start="{start}"' if start != 1 else ""
        self._parts.append(f"<ol{attr}>{body}</ol>")
        return self

    def checklist(self, items: Iterable[Union[str, tuple]]) -> "RichMessage":
        """Belgilanadigan ro'yxat: `["Bajarildi", ("Bajarilmadi", False)]`."""
        rows = []
        for item in items:
            text, done = item if isinstance(item, tuple) else (item, True)
            checked = " checked" if done else ""
            rows.append(f'<li type="checkbox"{checked}>{_esc(text)}</li>')
        self._parts.append(f"<ul>{''.join(rows)}</ul>")
        return self

    # --- jadval ---------------------------------------------------------------
    def table(self, rows: Iterable[Iterable[Any]], header: bool = False) -> "RichMessage":
        """Jadval. `header=True` bo'lsa birinchi qator sarlavha bo'ladi."""
        html_rows = []
        for index, row in enumerate(rows):
            cell = "th" if (header and index == 0) else "td"
            cells = "".join(f"<{cell}>{_esc(value)}</{cell}>" for value in row)
            html_rows.append(f"<tr>{cells}</tr>")
        self._parts.append(f"<table>{''.join(html_rows)}</table>")
        return self

    # --- yig'iladigan bo'lim --------------------------------------------------
    def details(self, summary: Any, *content: Any) -> "RichMessage":
        """Yig'iladigan bo'lim: sarlavha bosilganda ichki matn ochiladi."""
        self._parts.append(
            f"<details><summary>{_esc(summary)}</summary>{_join(content)}</details>"
        )
        return self

    # --- media (10.2) ---------------------------------------------------------
    def image(self, src: str, caption: Optional[str] = None) -> "RichMessage":
        """Rasm. `src` — file_id yoki URL.

        Media'ni aniq ko'rsatish uchun `add_media()` bilan birga ishlating
        (Bot API 10.2 `InputRichMessageMedia`).
        """
        alt = f' alt="{escape(caption)}"' if caption else ""
        self._parts.append(f'<img src="{src}"{alt}>')
        return self

    def add_media(self, item: dict) -> "RichMessage":
        """`media` ro'yxatiga `InputRichMessageMedia` qo'shadi (10.2)."""
        self._media.append(item)
        return self

    # --- kengaytirish ---------------------------------------------------------
    def tag(self, name: str, *content: Any, **attrs: Any) -> "RichMessage":
        """Ixtiyoriy teg — hujjatdagi yangi bloklar uchun."""
        rendered = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items() if v is not None)
        self._parts.append(f"<{name}{rendered}>{_join(content)}</{name}>")
        return self

    def raw(self, html: str) -> "RichMessage":
        """Tayyor HTML'ni o'zgartirmasdan qo'shadi."""
        self._parts.append(html)
        return self

    def block(self, block_type: str, **fields: Any) -> "RichMessage":
        """`blocks` ro'yxatiga blok qo'shadi (Bot API 10.2 usuli).

        HTML o'rniga blok obyektlari bilan ishlashni xohlasangiz — maydon
        nomlari rasmiy hujjatdagidek beriladi.
        """
        self._blocks.append({"type": block_type, **fields})
        return self

    # --- natija ---------------------------------------------------------------
    @property
    def html(self) -> str:
        return "".join(self._parts)

    def to_dict(self) -> dict:
        """`sendRichMessage` uchun `InputRichMessage` obyekti."""
        payload: Dict[str, Any] = {}
        if self._blocks:
            payload["blocks"] = self._blocks
        if self._parts:
            payload["html"] = self.html
        if self._media:
            payload["media"] = self._media
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
        return f"<RichMessage blocks={len(self._parts)} chars={len(self.html)}>"


def markdown_rich(text: str, **kwargs) -> dict:
    """Markdown'dan `InputRichMessage` yasaydi (html o'rniga markdown maydoni).

        await bot.send_rich_message(chat_id=1, rich_message=markdown_rich("# Salom"))
    """
    payload = {"markdown": text}
    for key in ("is_rtl", "skip_entity_detection", "media", "blocks"):
        if kwargs.get(key):
            payload[key] = kwargs[key]
    return payload


class RichStream:
    """AI javobini bo'lak-bo'lak yuborish (`sendRichMessageDraft`).

    Har bir bo'lakda so'rov yubormaslik uchun `min_interval` (soniya) bo'yicha
    tejaladi — Telegram'ning flood-limitiga tushmaslik uchun muhim.

        async with RichStream(bot.bot, chat_id) as stream:
            async for chunk in llm():
                await stream.push(chunk)
        # chiqishda yakuniy xabar avtomatik yuboriladi
    """

    def __init__(
        self,
        bot,
        chat_id: int,
        *,
        min_interval: float = 0.7,
        as_markdown: bool = True,
        thinking: Optional[str] = None,
        **send_kwargs: Any,
    ) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.min_interval = min_interval
        self.as_markdown = as_markdown
        self.thinking = thinking
        self.send_kwargs = send_kwargs
        self._buffer: List[str] = []
        self._last_sent = 0.0
        self._dirty = False
        self.message = None

    @property
    def text(self) -> str:
        return "".join(self._buffer)

    def _payload(self, final: bool = False) -> dict:
        if self.as_markdown:
            payload: Dict[str, Any] = {"markdown": self.text}
        else:
            rich = RichMessage()
            if self.thinking and not final:
                rich.thinking(self.thinking)
            rich.paragraph(self.text)
            payload = rich.to_dict()
        return payload

    async def push(self, chunk: str, force: bool = False) -> None:
        """Yangi bo'lakni qo'shadi va kerak bo'lsa qoralamani yangilaydi."""
        if chunk:
            self._buffer.append(chunk)
            self._dirty = True
        now = time.monotonic()
        if not self._dirty:
            return
        if force or (now - self._last_sent) >= self.min_interval:
            await self._send_draft()

    async def _send_draft(self) -> None:
        self._last_sent = time.monotonic()
        self._dirty = False
        try:
            await self.bot.call(
                "sendRichMessageDraft",
                chat_id=self.chat_id,
                rich_message=self._payload(),
                **self.send_kwargs,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — qoralama xatosi oqimni to'xtatmasin
            pass

    async def finish(self, rich_message: Optional[Union[RichMessage, dict]] = None):
        """Yakuniy xabarni yuboradi (`sendRichMessage`)."""
        payload = rich_message
        if payload is None:
            payload = self._payload(final=True)
        elif isinstance(payload, RichMessage):
            payload = payload.to_dict()
        self.message = await self.bot.request(
            "sendRichMessage",
            chat_id=self.chat_id,
            rich_message=payload,
            **self.send_kwargs,
        )
        return self.message

    async def __aenter__(self) -> "RichStream":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is None and self.text:
            await self.finish()

    def __repr__(self) -> str:
        return f"<RichStream chat={self.chat_id} chars={len(self.text)}>"
