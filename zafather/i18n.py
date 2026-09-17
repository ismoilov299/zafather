"""UZ: Botlar uchun tarjima va locale middleware.
RU: Переводы и middleware locale для ботов.
EN: Translations and locale middleware for bots.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


class I18n:
    """UZ: Tarjima lug'ati va router middleware.
    RU: Словарь переводов и middleware для router.
    EN: Translation catalog and router middleware.

    Misol / Пример / Example::

        i18n = I18n({"en": {"hello": "Hello, {name}!"}})
        app.middleware(i18n)

        @app.command("start")
        async def start(message, _):
            await message.answer(_("hello", name="Ali"))
    """

    def __init__(
        self,
        translations: Mapping[str, Mapping[str, str]],
        default_locale: str = "en",
        fallback_locale: Optional[str] = None,
    ) -> None:
        self.translations: Dict[str, Dict[str, str]] = {
            self.normalize_locale(locale): dict(messages)
            for locale, messages in translations.items()
        }
        self.default_locale = self.normalize_locale(default_locale)
        self.fallback_locale = self.normalize_locale(fallback_locale or default_locale)

    @staticmethod
    def normalize_locale(locale: Optional[str]) -> str:
        """UZ/RU/EN: `ru-RU` kabi locale qiymatini `ru` ko'rinishiga keltiradi."""
        return (locale or "").replace("_", "-").split("-", 1)[0].lower()

    def locale_for(self, event: Any, default: Optional[str] = None) -> str:
        user = getattr(event, "from_user", None)
        locale = self.normalize_locale(getattr(user, "language_code", None))
        if locale in self.translations:
            return locale
        preferred = self.normalize_locale(default) or self.default_locale
        if preferred in self.translations:
            return preferred
        return self.fallback_locale

    def gettext(self, key: str, locale: Optional[str] = None, **kwargs: Any) -> str:
        """UZ/RU/EN: Kalit bo'yicha tarjima qiladi, topilmasa kalitning o'zini qaytaradi."""
        selected = self.normalize_locale(locale) or self.default_locale
        messages = self.translations.get(selected) or self.translations.get(self.fallback_locale, {})
        text = messages.get(key, key)
        return text.format(**kwargs) if kwargs else text

    def translator(self, locale: str):
        selected = self.normalize_locale(locale)

        def translate(key: str, **kwargs: Any) -> str:
            return self.gettext(key, selected, **kwargs)

        return translate

    async def __call__(self, event, data: dict, next_):
        locale = self.locale_for(event)
        payload = dict(data)
        payload["locale"] = locale
        payload["i18n"] = self
        payload["_"] = self.translator(locale)
        return await next_(event, payload)


__all__ = ["I18n"]
