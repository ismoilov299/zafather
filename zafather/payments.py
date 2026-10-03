"""UZ: To'lovlar: invoice yordamchilari va Telegram Stars.
RU: Платежи: помощники для invoice и Telegram Stars.
EN: Payments: invoice helpers and Telegram Stars.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from .enums import Currency

if TYPE_CHECKING:
    from .bot import Bot


class LabeledPrice:
    """UZ: Narx qatori (eng kichik birlikda, Stars uchun — yulduzlar soni).
    RU: Строка цены (в минимальных единицах, для Stars — число звёзд).
    EN: A price line (in the smallest units; for Stars — the number of stars).
    """

    __slots__ = ("amount", "label")

    def __init__(self, label: str, amount: int) -> None:
        self.label = label
        self.amount = int(amount)

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "amount": self.amount}

    def __repr__(self) -> str:
        return f"LabeledPrice({self.label!r}, {self.amount})"


class Invoice:
    """UZ: Invoice parametrlarini yig'adi. RU: Собирает параметры invoice.
    EN: Collects invoice parameters::

        await bot.send_invoice(chat_id=chat_id, **invoice.to_dict())
    """

    def __init__(
        self,
        title: str,
        description: str,
        payload: str,
        provider_token: str | None = None,
        currency: str = Currency.STARS,
        prices: Iterable[LabeledPrice] | None = None,
        provider_data: str | None = None,
        start_parameter: str | None = None,
        **extra: Any,
    ) -> None:
        self.title = title
        self.description = description
        self.payload = payload
        self.provider_token = provider_token
        self.currency = currency
        self.prices = list(prices or [])
        self.provider_data = provider_data
        self.start_parameter = start_parameter
        self.extra = extra

    @classmethod
    def stars(
        cls, title: str, description: str, payload: str, amount: int, **extra: Any
    ) -> Invoice:
        """UZ: Telegram Stars (XTR) invoice'i. RU: Invoice в Telegram Stars (XTR).
        EN: A Telegram Stars (XTR) invoice.
        """
        return cls(
            title,
            description,
            payload,
            currency=Currency.STARS,
            prices=[LabeledPrice(title, amount)],
            **extra,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "title": self.title,
            "description": self.description,
            "payload": self.payload,
            "currency": self.currency,
            "prices": [price.to_dict() for price in self.prices],
        }
        optional = {
            "provider_token": self.provider_token,
            "provider_data": self.provider_data,
            "start_parameter": self.start_parameter,
        }
        data.update({key: value for key, value in optional.items() if value is not None})
        data.update(self.extra)
        return data


class StarsAPI:
    """UZ: Telegram Stars metodlari ustidagi qobiq (`bot.stars`).
    RU: Обёртка над методами Telegram Stars (`bot.stars`).
    EN: A wrapper over the Telegram Stars methods (`bot.stars`).
    """

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def balance(self) -> Any:
        """UZ: Botning Stars balansi (`getMyStarBalance`). RU: Баланс Stars бота.
        EN: The bot's own Stars balance (`getMyStarBalance`).
        """
        return await self.bot.request("getMyStarBalance")

    async def business_balance(self, business_connection_id: str) -> Any:
        """UZ: Biznes akkaunt balansi. RU: Баланс бизнес-аккаунта.
        EN: A business account balance.
        """
        return await self.bot.request(
            "getBusinessAccountStarBalance", business_connection_id=business_connection_id
        )

    async def transactions(self, offset: int | None = None, limit: int | None = None) -> Any:
        return await self.bot.request("getStarTransactions", offset=offset, limit=limit)

    async def refund(self, user_id: int, charge_id: str, **params: Any) -> Any:
        return await self.bot.request(
            "refundStarPayment", user_id=user_id, telegram_payment_charge_id=charge_id, **params
        )


__all__ = ["Invoice", "LabeledPrice", "StarsAPI"]
