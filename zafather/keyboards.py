"""UZ: Zafather — klaviaturalar (rangli tugmalar va premium emoji ikonkalari bilan).
RU: Zafather — клавиатуры (с цветными кнопками и иконками premium emoji).
EN: Zafather — keyboards (with colored buttons and premium emoji icons).

UZ: Misol / RU: Пример / EN: Example::

    kb = InlineKeyboard()
    kb.success("✅ Tasdiqlash", "ok").danger("🗑 O'chirish", "del")
    kb.row().primary("⭐️ Asosiy", "main", icon="5368324170671202286")
    kb.row().copy("Promokod", "ZAFATHER2026")
    await message.answer("Tanlang", reply_markup=kb)
"""

from __future__ import annotations

from typing import Any, TypeVar

from .enums import ButtonStyle

KeyboardT = TypeVar("KeyboardT", bound="BaseKeyboard")

#: UZ: Callback data uchun Telegram chegarasi (bayt).
#: RU: Ограничение Telegram для callback data (байты).
#: EN: Telegram's callback data limit (bytes).
MAX_CALLBACK_DATA_BYTES = 64

_INLINE_ACTIONS = (
    "callback_data",
    "url",
    "web_app",
    "login_url",
    "switch_inline_query",
    "switch_inline_query_current_chat",
    "switch_inline_query_chosen_chat",
    "copy_text",
    "callback_game",
    "pay",
)


def style_fields(style: str | None, icon: str | None) -> dict[str, Any]:
    """UZ: Tugma rangi (`primary`/`success`/`danger`) va premium emoji ikonkasi.
    RU: Цвет кнопки (`primary`/`success`/`danger`) и иконка premium emoji.
    EN: Button color (`primary`/`success`/`danger`) and premium emoji icon.
    """
    fields: dict[str, Any] = {}
    if style is not None:
        if style not in ButtonStyle.ALL:
            raise ValueError(f"style must be one of {ButtonStyle.ALL}, got {style!r}")
        fields["style"] = style
    if icon:
        fields["icon_custom_emoji_id"] = icon
    return fields


def validate_callback_data(value: str) -> str:
    """UZ: Callback data 1-64 bayt bo'lishi shart. RU: Callback data должна быть 1-64 байта.
    EN: Callback data must be 1-64 bytes.
    """
    size = len(value.encode("utf-8"))
    if not 1 <= size <= MAX_CALLBACK_DATA_BYTES:
        raise ValueError(f"callback_data must be 1-{MAX_CALLBACK_DATA_BYTES} bytes, got {size}")
    return value


def _poll_request(poll_type: str | None) -> dict[str, Any] | None:
    if poll_type is None:
        return None
    return {"type": poll_type} if poll_type else {}


class BaseKeyboard:
    """UZ: Qatorlar bilan ishlashning umumiy mantig'i.
    RU: Общая логика работы с рядами.
    EN: Shared row-building logic.
    """

    def __init__(self) -> None:
        self._rows: list[list[dict[str, Any]]] = [[]]

    def row(self: KeyboardT, *buttons: dict[str, Any]) -> KeyboardT:
        """UZ: Yangi qator boshlaydi (tugmalar berilsa — ular alohida qator bo'ladi).
        RU: Начинает новый ряд (переданные кнопки образуют отдельный ряд).
        EN: Starts a new row (given buttons form a row of their own).
        """
        if not self._rows[-1]:
            self._rows.pop()
        if buttons:
            self._rows.append(list(buttons))
        self._rows.append([])
        return self

    def adjust(self: KeyboardT, *sizes: int) -> KeyboardT:
        """UZ: Tugmalarni qatorlarga qayta taqsimlaydi: `adjust(2)` yoki `adjust(3, 2)`.
        RU: Перераспределяет кнопки по рядам: `adjust(2)` или `adjust(3, 2)`.
        EN: Redistributes buttons into rows: `adjust(2)` or `adjust(3, 2)`.
        """
        if not sizes:
            return self
        if any(size < 1 for size in sizes):
            raise ValueError("Row sizes must be positive")
        buttons = [button for row in self._rows for button in row]
        rows: list[list[dict[str, Any]]] = []
        index = 0
        while index < len(buttons):
            size = sizes[min(len(rows), len(sizes) - 1)]
            rows.append(buttons[index : index + size])
            index += size
        self._rows = [*rows, []]
        return self

    def extend(self: KeyboardT, other: BaseKeyboard) -> KeyboardT:
        """UZ: Boshqa klaviatura qatorlarini qo'shadi. RU: Добавляет ряды другой клавиатуры.
        EN: Appends the rows of another keyboard.
        """
        self._rows = [*self.rows, *other.rows, []]
        return self

    def _append(self: KeyboardT, button: dict[str, Any]) -> KeyboardT:
        self._rows[-1].append(button)
        return self

    @property
    def rows(self) -> list[list[dict[str, Any]]]:
        return [list(row) for row in self._rows if row]

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def __bool__(self) -> bool:
        return bool(self.rows)

    def __repr__(self) -> str:
        rows = self.rows
        return f"<{type(self).__name__} rows={len(rows)} buttons={sum(map(len, rows))}>"


class InlineKeyboard(BaseKeyboard):
    """UZ: Xabar ostidagi inline tugmalar. RU: Inline-кнопки под сообщением.
    EN: Inline buttons under a message.
    """

    def add(
        self,
        text: str,
        callback_data: str | None = None,
        *,
        url: str | None = None,
        web_app: str | None = None,
        login_url: dict[str, Any] | None = None,
        switch_inline_query: str | None = None,
        switch_inline_query_current_chat: str | None = None,
        switch_inline_query_chosen_chat: dict[str, Any] | None = None,
        copy_text: str | None = None,
        pay: bool = False,
        style: str | None = None,
        icon: str | None = None,
        **fields: Any,
    ) -> InlineKeyboard:
        """UZ: Universal tugma; hech qanday amal berilmasa matn `callback_data` bo'ladi.
        RU: Универсальная кнопка; без действия текст становится `callback_data`.
        EN: Universal button; without an action the text becomes `callback_data`.
        """
        button: dict[str, Any] = {"text": text}
        if callback_data is not None:
            button["callback_data"] = validate_callback_data(callback_data)
        optional = {
            "url": url,
            "web_app": {"url": web_app} if web_app is not None else None,
            "login_url": login_url,
            "switch_inline_query": switch_inline_query,
            "switch_inline_query_current_chat": switch_inline_query_current_chat,
            "switch_inline_query_chosen_chat": switch_inline_query_chosen_chat,
            "copy_text": {"text": copy_text} if copy_text is not None else None,
            "pay": True if pay else None,
        }
        button.update({key: value for key, value in optional.items() if value is not None})
        button.update(style_fields(style, icon))
        button.update(fields)
        if not any(action in button for action in _INLINE_ACTIONS):
            button["callback_data"] = validate_callback_data(text)
        return self._append(button)

    def primary(self, text: str, callback_data: str | None = None, **kwargs: Any) -> InlineKeyboard:
        """UZ: Ko'k tugma. RU: Синяя кнопка. EN: Blue button."""
        return self.add(text, callback_data, style=ButtonStyle.PRIMARY, **kwargs)

    def success(self, text: str, callback_data: str | None = None, **kwargs: Any) -> InlineKeyboard:
        """UZ: Yashil tugma. RU: Зелёная кнопка. EN: Green button."""
        return self.add(text, callback_data, style=ButtonStyle.SUCCESS, **kwargs)

    def danger(self, text: str, callback_data: str | None = None, **kwargs: Any) -> InlineKeyboard:
        """UZ: Qizil tugma. RU: Красная кнопка. EN: Red button."""
        return self.add(text, callback_data, style=ButtonStyle.DANGER, **kwargs)

    def link(self, text: str, url: str, **kwargs: Any) -> InlineKeyboard:
        return self.add(text, url=url, **kwargs)

    def app(self, text: str, url: str, **kwargs: Any) -> InlineKeyboard:
        """UZ: Mini App ochadigan tugma. RU: Кнопка, открывающая Mini App.
        EN: A button that opens a Mini App.
        """
        return self.add(text, web_app=url, **kwargs)

    def copy(self, text: str, value: str, **kwargs: Any) -> InlineKeyboard:
        """UZ: Matnni nusxalaydigan tugma. RU: Кнопка копирования текста.
        EN: A button that copies text.
        """
        return self.add(text, copy_text=value, **kwargs)

    def pay_button(self, text: str = "Pay", **kwargs: Any) -> InlineKeyboard:
        return self.add(text, pay=True, **kwargs)

    def switch(
        self, text: str, query: str = "", current_chat: bool = False, **kwargs: Any
    ) -> InlineKeyboard:
        if current_chat:
            return self.add(text, switch_inline_query_current_chat=query, **kwargs)
        return self.add(text, switch_inline_query=query, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {"inline_keyboard": self.rows}


class ReplyKeyboard(BaseKeyboard):
    """UZ: Yozish maydoni o'rnidagi tugmalar. RU: Кнопки вместо поля ввода.
    EN: Buttons shown instead of the input field.
    """

    def __init__(
        self,
        resize: bool = True,
        one_time: bool = False,
        placeholder: str | None = None,
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
        request_poll: str | None = None,
        request_users: dict[str, Any] | None = None,
        request_chat: dict[str, Any] | None = None,
        request_managed_bot: dict[str, Any] | None = None,
        web_app: str | None = None,
        style: str | None = None,
        icon: str | None = None,
        **fields: Any,
    ) -> ReplyKeyboard:
        button: dict[str, Any] = {"text": text}
        optional = {
            "request_contact": True if request_contact else None,
            "request_location": True if request_location else None,
            "request_poll": _poll_request(request_poll),
            "request_users": request_users,
            "request_chat": request_chat,
            "request_managed_bot": request_managed_bot,
            "web_app": {"url": web_app} if web_app is not None else None,
        }
        button.update({key: value for key, value in optional.items() if value is not None})
        button.update(style_fields(style, icon))
        button.update(fields)
        return self._append(button)

    def primary(self, text: str, **kwargs: Any) -> ReplyKeyboard:
        return self.add(text, style=ButtonStyle.PRIMARY, **kwargs)

    def success(self, text: str, **kwargs: Any) -> ReplyKeyboard:
        return self.add(text, style=ButtonStyle.SUCCESS, **kwargs)

    def danger(self, text: str, **kwargs: Any) -> ReplyKeyboard:
        return self.add(text, style=ButtonStyle.DANGER, **kwargs)

    def contact(self, text: str = "📱 Raqamni yuborish", **kwargs: Any) -> ReplyKeyboard:
        return self.add(text, request_contact=True, **kwargs)

    def location(self, text: str = "📍 Lokatsiya", **kwargs: Any) -> ReplyKeyboard:
        return self.add(text, request_location=True, **kwargs)

    def request_user(
        self,
        text: str,
        request_id: int = 1,
        *,
        user_is_bot: bool | None = None,
        user_is_premium: bool | None = None,
        max_quantity: int = 1,
        request_name: bool = True,
        request_username: bool = True,
        request_photo: bool = False,
        **kwargs: Any,
    ) -> ReplyKeyboard:
        """UZ: Foydalanuvchi tanlash tugmasi (KeyboardButtonRequestUsers).
        RU: Кнопка выбора пользователей (KeyboardButtonRequestUsers).
        EN: A user picker button (KeyboardButtonRequestUsers).
        """
        criteria: dict[str, Any] = {
            "request_id": request_id,
            "max_quantity": max_quantity,
            "request_name": request_name,
            "request_username": request_username,
            "request_photo": request_photo,
        }
        if user_is_bot is not None:
            criteria["user_is_bot"] = user_is_bot
        if user_is_premium is not None:
            criteria["user_is_premium"] = user_is_premium
        return self.add(text, request_users=criteria, **kwargs)

    def request_group(
        self,
        text: str,
        request_id: int = 1,
        *,
        chat_is_channel: bool = False,
        bot_is_member: bool | None = None,
        request_title: bool = True,
        request_username: bool = True,
        request_photo: bool = False,
        **kwargs: Any,
    ) -> ReplyKeyboard:
        """UZ: Guruh/kanal tanlash tugmasi (KeyboardButtonRequestChat).
        RU: Кнопка выбора группы/канала (KeyboardButtonRequestChat).
        EN: A group/channel picker button (KeyboardButtonRequestChat).
        """
        criteria: dict[str, Any] = {
            "request_id": request_id,
            "chat_is_channel": chat_is_channel,
            "request_title": request_title,
            "request_username": request_username,
            "request_photo": request_photo,
        }
        if bot_is_member is not None:
            criteria["bot_is_member"] = bot_is_member
        return self.add(text, request_chat=criteria, **kwargs)

    def request_bot(
        self,
        text: str = "🤖 Bot tanlash",
        request_id: int = 1,
        criteria: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ReplyKeyboard:
        """UZ: Boshqariladigan bot tanlash tugmasi (9.6+).
        RU: Кнопка выбора управляемого бота (9.6+).
        EN: A managed bot picker button (9.6+).
        """
        return self.add(
            text, request_managed_bot={"request_id": request_id, **(criteria or {})}, **kwargs
        )

    def app(self, text: str, url: str, **kwargs: Any) -> ReplyKeyboard:
        return self.add(text, web_app=url, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        markup: dict[str, Any] = {
            "keyboard": self.rows,
            "resize_keyboard": self.resize,
            "one_time_keyboard": self.one_time,
            "selective": self.selective,
            "is_persistent": self.persistent,
        }
        if self.placeholder:
            markup["input_field_placeholder"] = self.placeholder
        return markup


class RemoveKeyboard:
    """UZ: Reply klaviaturani olib tashlaydi. RU: Убирает reply-клавиатуру.
    EN: Removes the reply keyboard.
    """

    def __init__(self, selective: bool = False) -> None:
        self.selective = selective

    def to_dict(self) -> dict[str, Any]:
        return {"remove_keyboard": True, "selective": self.selective}


class ForceReply:
    """UZ: Foydalanuvchini javob yozishga undaydi. RU: Предлагает пользователю ответить.
    EN: Asks the user to reply.
    """

    def __init__(self, placeholder: str | None = None, selective: bool = False) -> None:
        self.placeholder = placeholder
        self.selective = selective

    def to_dict(self) -> dict[str, Any]:
        markup: dict[str, Any] = {"force_reply": True, "selective": self.selective}
        if self.placeholder:
            markup["input_field_placeholder"] = self.placeholder
        return markup


def confirm_keyboard(
    yes: str = "✅ Ha",
    no: str = "❌ Yo'q",
    yes_data: str = "confirm:yes",
    no_data: str = "confirm:no",
) -> InlineKeyboard:
    """UZ: Tayyor tasdiqlash klaviaturasi. RU: Готовая клавиатура подтверждения.
    EN: A ready-made confirmation keyboard.
    """
    return InlineKeyboard().success(yes, yes_data).danger(no, no_data)


__all__ = [
    "MAX_CALLBACK_DATA_BYTES",
    "BaseKeyboard",
    "ForceReply",
    "InlineKeyboard",
    "RemoveKeyboard",
    "ReplyKeyboard",
    "confirm_keyboard",
    "style_fields",
    "validate_callback_data",
]
