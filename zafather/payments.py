"""UZ: Stars va invoice uchun qulay modullar.
RU: Утилиты для Stars и invoice.
EN: Helper modules for Stars and invoice payments.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional


class LabeledPrice:
    """UZ: Invoice narx bloki.
    RU: Элемент цены для invoice.
    EN: Price entry for an invoice.
    """

    def __init__(self, label: str, amount: int) -> None:
        self.label = label
        self.amount = int(amount)

    def to_dict(self) -> dict:
        return {"label": self.label, "amount": self.amount}


class Invoice:
    """UZ: Invoice obyektini yaratish uchun yordamchi.
    RU: Вспомогательный объект для создания invoice.
    EN: Helper object for building an invoice.
    """

    def __init__(
        self,
        title: str,
        description: str,
        payload: str,
        provider_token: Optional[str] = None,
        currency: str = "XTR",
        prices: Optional[Iterable[LabeledPrice]] = None,
        provider_data: Optional[str] = None,
        start_parameter: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.title = title
        self.description = description
        self.payload = payload
        self.provider_token = provider_token
        self.currency = currency
        self.prices = list(prices or [])
        self.provider_data = provider_data
        self.start_parameter = start_parameter
        self.extra = kwargs

    def to_dict(self) -> dict:
        data: dict[str, Any] = {
            "title": self.title,
            "description": self.description,
            "payload": self.payload,
            "currency": self.currency,
            "prices": [item.to_dict() for item in self.prices],
        }
        if self.provider_token is not None:
            data["provider_token"] = self.provider_token
        if self.provider_data is not None:
            data["provider_data"] = self.provider_data
        if self.start_parameter is not None:
            data["start_parameter"] = self.start_parameter
        data.update(self.extra)
        return data


class StarsAPI:
    """UZ: Telegram Stars bilan ishlash uchun soddalashtirilgan API.
    RU: Упрощённый API для Telegram Stars.
    EN: Simplified API for Telegram Stars.
    """

    def __init__(self, bot: Any) -> None:
        self.bot = bot

    async def balance(self, user_id: Optional[int] = None, **kwargs: Any) -> Any:
        return await self.bot.request("getStarBalance", user_id=user_id, **kwargs)

    async def transactions(self, **kwargs: Any) -> Any:
        return await self.bot.request("getStarTransactions", **kwargs)

    async def refund(self, user_id: int, charge_id: str, **kwargs: Any) -> Any:
        return await self.bot.request(
            "refundStarPayment",
            user_id=user_id,
            charge_id=charge_id,
            **kwargs,
        )


__all__ = ["Invoice", "LabeledPrice", "StarsAPI"]
