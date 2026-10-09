"""UZ: Tarjimalar va til tanlovchi middleware.
RU: Переводы и middleware выбора языка.
EN: Translations and a locale-selecting middleware.

UZ: Misol / RU: Пример / EN: Example::

    i18n = I18n({"uz": {"hello": "Salom, {name}!"}, "en": {"hello": "Hello, {name}!"}})
    app.middleware(i18n)

    @app.command("start")
    async def start(message, _):
        await message.answer(_("hello", name=message.from_user.first_name))
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .router import NextHandler

Translator = Callable[..., str]


class _KeepMissing(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def normalize_locale(locale: str | None) -> str:
    """UZ: `ru-RU`/`ru_RU` -> `ru`. RU: `ru-RU`/`ru_RU` -> `ru`. EN: `ru-RU`/`ru_RU` -> `ru`."""
    return (locale or "").replace("_", "-").split("-", 1)[0].lower()


class I18n:
    """UZ: Tarjima katalogi va middleware: foydalanuvchi `language_code` bo'yicha til
    tanlanadi, handlerga `_`, `locale` va `i18n` uzatiladi.
    RU: Каталог переводов и middleware: язык выбирается по `language_code`
    пользователя, в handler передаются `_`, `locale` и `i18n`.
    EN: Translation catalog and middleware: the locale is picked from the user's
    `language_code` and `_`, `locale` and `i18n` are injected into handlers.

    UZ: Kalit topilmasa — zaxira tildan, u ham bo'lmasa kalitning o'zi qaytadi.
    RU: Если ключ не найден — берётся резервный язык, иначе возвращается сам ключ.
    EN: A missing key falls back to the fallback locale, then to the key itself.
    """

    def __init__(
        self,
        translations: Mapping[str, Mapping[str, str]],
        default_locale: str = "en",
        fallback_locale: str | None = None,
    ) -> None:
        self.translations: dict[str, dict[str, str]] = {
            normalize_locale(locale): dict(messages) for locale, messages in translations.items()
        }
        self.default_locale = normalize_locale(default_locale)
        self.fallback_locale = normalize_locale(fallback_locale or default_locale)

    @classmethod
    def from_directory(
        cls, path: str | os.PathLike[str], default_locale: str = "en", **kwargs: Any
    ) -> I18n:
        """UZ: `<til>.json` fayllardan yuklaydi (masalan `uz.json`, `ru.json`).
        RU: Загружает из файлов `<язык>.json` (например `uz.json`, `ru.json`).
        EN: Loads `<locale>.json` files (for example `uz.json`, `ru.json`).
        """
        translations = {
            file.stem: json.loads(file.read_text(encoding="utf-8"))
            for file in sorted(Path(path).glob("*.json"))
        }
        return cls(translations, default_locale=default_locale, **kwargs)

    @property
    def locales(self) -> tuple[str, ...]:
        return tuple(self.translations)

    def locale_for(self, event: Any) -> str:
        """UZ: Event uchun til. RU: Язык для события. EN: The locale for an event."""
        user = getattr(event, "from_user", None) or getattr(event, "user", None)
        locale = normalize_locale(getattr(user, "language_code", None))
        if locale in self.translations:
            return locale
        return self.default_locale

    def gettext(self, key: str, locale: str | None = None, **values: Any) -> str:
        """UZ: Kalitni tarjima qiladi va `{nom}` joylarini to'ldiradi.
        RU: Переводит ключ и подставляет значения `{имя}`.
        EN: Translates a key and fills `{name}` placeholders.
        """
        selected = normalize_locale(locale) or self.default_locale
        for candidate in (selected, self.fallback_locale):
            text = self.translations.get(candidate, {}).get(key)
            if text is not None:
                break
        else:
            text = key
        return text.format_map(_KeepMissing(values)) if values else text

    def translator(self, locale: str) -> Translator:
        def translate(key: str, **values: Any) -> str:
            return self.gettext(key, locale, **values)

        return translate

    async def __call__(self, event: Any, data: dict[str, Any], next_: NextHandler) -> Any:
        locale = self.locale_for(event)
        return await next_(
            event, {**data, "locale": locale, "i18n": self, "_": self.translator(locale)}
        )


__all__ = ["I18n", "normalize_locale"]
