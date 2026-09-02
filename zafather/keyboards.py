"""Zafather — klaviaturalar (Bot API 10.2).

Rangli tugmalar (9.4+) va premium emoji ikonkalari qo'llab-quvvatlanadi::

    kb = InlineKeyboard()
    kb.success("✅ Tasdiqlash", callback_data="ok")
    kb.danger("🗑 O'chirish", callback_data="del")
    kb.primary("⭐️ Asosiy", callback_data="main", icon="5368324170671202286")
    kb.row()
    kb.copy("Promokodni nusxalash", "ZAFATHER2026")
    await m.answer("Tanlang", reply_markup=kb)
"""
from __future__ import annotations

from typing import List, Optional, Union

from .enums import ButtonStyle


def _style_fields(style: Optional[str], icon: Optional[str]) -> dict:
    """style — 'primary' | 'success' | 'danger', icon — custom_emoji_id."""
    extra = {}
    if style:
        if style not in ButtonStyle.ALL:
            raise ValueError(
                f"style faqat {ButtonStyle.ALL} dan biri bo'lishi mumkin, berildi: {style!r}"
            )
        extra["style"] = style
    if icon:
        extra["icon_custom_emoji_id"] = icon
    return extra


class BaseKeyboard:
    """Umumiy quruvchi mantiq (qatorlar, adjust, to_dict)."""

    def __init__(self) -> None:
        self._rows: List[list] = [[]]

    # --- qatorlar -------------------------------------------------------------
    def row(self, *buttons) -> "BaseKeyboard":
        if self._rows and not self._rows[-1]:
            self._rows.pop()
        if buttons:
            self._rows.append(list(buttons))
        self._rows.append([])
        return self

    def adjust(self, *sizes: int) -> "BaseKeyboard":
        flat = [b for row in self._rows for b in row]
        if not sizes:
            return self
        rows, index, i = [], 0, 0
        while index < len(flat):
            size = sizes[min(i, len(sizes) - 1)]
            rows.append(flat[index : index + size])
            index += size
            i += 1
        self._rows = rows + [[]]
        return self

    def _append(self, button: dict) -> "BaseKeyboard":
        if not self._rows:
            self._rows.append([])
        self._rows[-1].append(button)
        return self

    def _clean(self) -> List[list]:
        return [row for row in self._rows if row]

    def extend(self, other: "BaseKeyboard") -> "BaseKeyboard":
        """Boshqa klaviaturaning qatorlarini qo'shadi."""
        self.row()
        self._rows = self._clean() + other._clean() + [[]]
        return self

    def to_dict(self) -> dict:
        raise NotImplementedError

    def __bool__(self) -> bool:
        return bool(self._clean())

    def __repr__(self) -> str:
        rows = self._clean()
        return f"<{type(self).__name__} rows={len(rows)} buttons={sum(len(r) for r in rows)}>"


class InlineKeyboard(BaseKeyboard):
    """Xabar ostidagi inline tugmalar."""

    def add(
        self,
        text: str,
        callback_data: Optional[str] = None,
        *,
        url: Optional[str] = None,
        web_app: Optional[str] = None,
        login_url: Optional[dict] = None,
        switch_inline_query: Optional[str] = None,
        switch_inline_query_current_chat: Optional[str] = None,
        switch_inline_query_chosen_chat: Optional[dict] = None,
        copy_text: Optional[str] = None,
        pay: bool = False,
        style: Optional[str] = None,
        icon: Optional[str] = None,
        **kwargs,
    ) -> "InlineKeyboard":
        """Universal tugma. `style` — rang, `icon` — premium emoji id."""
        button: dict = {"text": text}
        if callback_data is not None:
            button["callback_data"] = callback_data
        if url is not None:
            button["url"] = url
        if web_app is not None:
            button["web_app"] = {"url": web_app}
        if login_url is not None:
            button["login_url"] = login_url
        if switch_inline_query is not None:
            button["switch_inline_query"] = switch_inline_query
        if switch_inline_query_current_chat is not None:
            button["switch_inline_query_current_chat"] = switch_inline_query_current_chat
        if switch_inline_query_chosen_chat is not None:
            button["switch_inline_query_chosen_chat"] = switch_inline_query_chosen_chat
        if copy_text is not None:
            button["copy_text"] = {"text": copy_text}
        if pay:
            button["pay"] = True
        button.update(_style_fields(style, icon))
        button.update(kwargs)
        # hech qanday amal berilmasa — matnning o'zi callback_data bo'ladi
        if not any(
            k in button
            for k in (
                "callback_data",
                "url",
                "web_app",
                "login_url",
                "switch_inline_query",
                "switch_inline_query_current_chat",
                "switch_inline_query_chosen_chat",
                "copy_text",
                "pay",
                "callback_game",
            )
        ):
            button["callback_data"] = text
        return self._append(button)

    # --- rangli yorliqlar -----------------------------------------------------
    def primary(self, text: str, callback_data: str = None, **kw) -> "InlineKeyboard":
        """Ko'k tugma — asosiy amal."""
        return self.add(text, callback_data, style=ButtonStyle.PRIMARY, **kw)

    def success(self, text: str, callback_data: str = None, **kw) -> "InlineKeyboard":
        """Yashil tugma — ijobiy amal."""
        return self.add(text, callback_data, style=ButtonStyle.SUCCESS, **kw)

    def danger(self, text: str, callback_data: str = None, **kw) -> "InlineKeyboard":
        """Qizil tugma — xavfli/o'chiruvchi amal."""
        return self.add(text, callback_data, style=ButtonStyle.DANGER, **kw)

    # --- maxsus turlar --------------------------------------------------------
    def link(self, text: str, url: str, **kw) -> "InlineKeyboard":
        return self.add(text, url=url, **kw)

    def app(self, text: str, url: str, **kw) -> "InlineKeyboard":
        """Mini App ochadigan tugma."""
        return self.add(text, web_app=url, **kw)

    def copy(self, text: str, value: str, **kw) -> "InlineKeyboard":
        """Bosilganda matnni nusxalaydigan tugma (Bot API 7.11+)."""
        return self.add(text, copy_text=value, **kw)

    def pay_button(self, text: str = "Pay", **kw) -> "InlineKeyboard":
        return self.add(text, pay=True, **kw)

    def switch(self, text: str, query: str = "", current_chat: bool = False, **kw):
        if current_chat:
            return self.add(text, switch_inline_query_current_chat=query, **kw)
        return self.add(text, switch_inline_query=query, **kw)

    def to_dict(self) -> dict:
        return {"inline_keyboard": self._clean()}


class ReplyKeyboard(BaseKeyboard):
    """Klaviatura o'rnida chiqadigan tugmalar (rangli va so'rov tugmalari bilan)."""

    def __init__(
        self,
        resize: bool = True,
        one_time: bool = False,
        placeholder: Optional[str] = None,
        selective: bool = False,
        persistent: bool = False,
    ) -> None:
        super().__init__()
        self.resize = resize
        self.one_time = one_time
        self.placeholder = placeholder
        self.selective = selective
        self.persistent = persistent

    def add(
        self,
        text: str,
        *,
        request_contact: bool = False,
        request_location: bool = False,
        request_poll: Optional[str] = None,
        request_users: Optional[dict] = None,
        request_chat: Optional[dict] = None,
        request_managed_bot: Optional[dict] = None,
        web_app: Optional[str] = None,
        style: Optional[str] = None,
        icon: Optional[str] = None,
        **kwargs,
    ) -> "ReplyKeyboard":
        button: dict = {"text": text}
        if request_contact:
            button["request_contact"] = True
        if request_location:
            button["request_location"] = True
        if request_poll is not None:
            button["request_poll"] = {"type": request_poll} if request_poll else {}
        if request_users is not None:
            button["request_users"] = request_users
        if request_chat is not None:
            button["request_chat"] = request_chat
        if request_managed_bot is not None:
            button["request_managed_bot"] = request_managed_bot
        if web_app is not None:
            button["web_app"] = {"url": web_app}
        button.update(_style_fields(style, icon))
        button.update(kwargs)
        return self._append(button)

    # --- rangli yorliqlar -----------------------------------------------------
    def primary(self, text: str, **kw) -> "ReplyKeyboard":
        return self.add(text, style=ButtonStyle.PRIMARY, **kw)

    def success(self, text: str, **kw) -> "ReplyKeyboard":
        return self.add(text, style=ButtonStyle.SUCCESS, **kw)

    def danger(self, text: str, **kw) -> "ReplyKeyboard":
        return self.add(text, style=ButtonStyle.DANGER, **kw)

    # --- so'rov tugmalari -----------------------------------------------------
    def contact(self, text: str = "📱 Raqamni yuborish", **kw) -> "ReplyKeyboard":
        return self.add(text, request_contact=True, **kw)

    def location(self, text: str = "📍 Lokatsiya", **kw) -> "ReplyKeyboard":
        return self.add(text, request_location=True, **kw)

    def request_user(
        self,
        text: str,
        request_id: int = 1,
        *,
        user_is_bot: Optional[bool] = None,
        user_is_premium: Optional[bool] = None,
        max_quantity: int = 1,
        request_name: bool = True,
        request_username: bool = True,
        request_photo: bool = False,
        **kw,
    ) -> "ReplyKeyboard":
        """Foydalanuvchi(lar)ni tanlash tugmasi (KeyboardButtonRequestUsers)."""
        payload = {
            "request_id": request_id,
            "max_quantity": max_quantity,
            "request_name": request_name,
            "request_username": request_username,
            "request_photo": request_photo,
        }
        if user_is_bot is not None:
            payload["user_is_bot"] = user_is_bot
        if user_is_premium is not None:
            payload["user_is_premium"] = user_is_premium
        return self.add(text, request_users=payload, **kw)

    def request_group(
        self,
        text: str,
        request_id: int = 1,
        *,
        chat_is_channel: bool = False,
        bot_is_member: Optional[bool] = None,
        request_title: bool = True,
        request_username: bool = True,
        request_photo: bool = False,
        **kw,
    ) -> "ReplyKeyboard":
        """Guruh/kanal tanlash tugmasi (KeyboardButtonRequestChat)."""
        payload = {
            "request_id": request_id,
            "chat_is_channel": chat_is_channel,
            "request_title": request_title,
            "request_username": request_username,
            "request_photo": request_photo,
        }
        if bot_is_member is not None:
            payload["bot_is_member"] = bot_is_member
        return self.add(text, request_chat=payload, **kw)

    def request_bot(
        self,
        text: str = "🤖 Bot tanlash",
        request_id: int = 1,
        **kw,
    ) -> "ReplyKeyboard":
        """Boshqariladigan bot tanlash tugmasi (KeyboardButtonRequestManagedBot, 9.6+)."""
        payload = {"request_id": request_id}
        payload.update(kw.pop("criteria", {}) or {})
        return self.add(text, request_managed_bot=payload, **kw)

    def app(self, text: str, url: str, **kw) -> "ReplyKeyboard":
        return self.add(text, web_app=url, **kw)

    def to_dict(self) -> dict:
        markup = {
            "keyboard": self._clean(),
            "resize_keyboard": self.resize,
            "one_time_keyboard": self.one_time,
            "selective": self.selective,
            "is_persistent": self.persistent,
        }
        if self.placeholder:
            markup["input_field_placeholder"] = self.placeholder
        return markup


class RemoveKeyboard:
    def __init__(self, selective: bool = False):
        self.selective = selective

    def to_dict(self) -> dict:
        return {"remove_keyboard": True, "selective": self.selective}


class ForceReply:
    def __init__(self, placeholder: Optional[str] = None, selective: bool = False):
        self.placeholder = placeholder
        self.selective = selective

    def to_dict(self) -> dict:
        markup = {"force_reply": True, "selective": self.selective}
        if self.placeholder:
            markup["input_field_placeholder"] = self.placeholder
        return markup


# --- tez yorliqlar ------------------------------------------------------------
def confirm_keyboard(
    yes: str = "✅ Ha",
    no: str = "❌ Yo'q",
    yes_data: str = "confirm:yes",
    no_data: str = "confirm:no",
) -> InlineKeyboard:
    """Tayyor tasdiqlash klaviaturasi (yashil/qizil)."""
    kb = InlineKeyboard()
    kb.success(yes, yes_data)
    kb.danger(no, no_data)
    return kb
