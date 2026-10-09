"""UZ: Telegram data-markazlari manzillari.
RU: Адреса дата-центров Telegram.
EN: Telegram data center addresses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DcOption:
    """UZ: Data-markaz manzili. RU: Адрес дата-центра. EN: A data center address."""

    id: int
    host: str
    port: int = 443


PRODUCTION_DCS: dict[int, DcOption] = {
    1: DcOption(1, "149.154.175.53"),
    2: DcOption(2, "149.154.167.51"),
    3: DcOption(3, "149.154.175.100"),
    4: DcOption(4, "149.154.167.91"),
    5: DcOption(5, "91.108.56.130"),
}

TEST_DCS: dict[int, DcOption] = {
    1: DcOption(1, "149.154.175.10"),
    2: DcOption(2, "149.154.167.40"),
    3: DcOption(3, "149.154.175.117"),
}


class DcTable:
    """UZ: Ma'lum DC manzillari; `help.getConfig` natijasi bilan yangilanadi.
    RU: Известные адреса DC; обновляются результатом `help.getConfig`.
    EN: Known DC addresses, refreshed from the `help.getConfig` result.
    """

    def __init__(
        self, test_mode: bool = False, overrides: dict[int, DcOption] | None = None
    ) -> None:
        self._options = dict(TEST_DCS if test_mode else PRODUCTION_DCS)
        self._pinned = dict(overrides or {})
        self._options.update(self._pinned)

    def get(self, dc_id: int) -> DcOption:
        try:
            return self._options[dc_id]
        except KeyError:
            raise KeyError(f"Unknown data center {dc_id}") from None

    def update_from_config(self, config: Any) -> None:
        """UZ: IPv4, media bo'lmagan va CDN bo'lmagan manzillarni oladi.
        RU: Берёт адреса IPv4, не media и не CDN.
        EN: Keeps IPv4 addresses that are neither media-only nor CDN.
        """
        for option in getattr(config, "dc_options", None) or []:
            if option.ipv6 or option.media_only or option.cdn or option.tcpo_only:
                continue
            if option.id in self._pinned:
                continue
            self._options[option.id] = DcOption(option.id, option.ip_address, option.port)

    def __contains__(self, dc_id: object) -> bool:
        return dc_id in self._options


__all__ = ["PRODUCTION_DCS", "TEST_DCS", "DcOption", "DcTable"]
