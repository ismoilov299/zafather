"""UZ: Qayta urinish siyosati (tarmoq xatolari, flood limit, server xatolari).
RU: Политика повторных попыток (сетевые ошибки, flood limit, ошибки сервера).
EN: Retry policy (network errors, flood limits, server errors).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    """UZ: So'rovni qachon va qancha kutib qayta yuborishni belgilaydi.
    RU: Определяет, когда и с какой задержкой повторять запрос.
    EN: Decides when to retry a request and how long to wait.

    UZ: `max_flood_wait` dan uzoq `retry_after` kelsa, kutilmaydi — `RetryAfter`
    xatosi chaqiruvchiga qaytariladi. Javobi yo'qolgan yozuvchi so'rovlar
    (`sendMessage` kabi) takrorlanmaydi, aks holda xabar ikki marta ketishi mumkin;
    buni `retry_unsafe_methods=True` bilan yoqish mumkin.
    RU: Если `retry_after` больше `max_flood_wait`, ожидания нет — исключение
    `RetryAfter` передаётся вызывающему коду. Изменяющие запросы (например,
    `sendMessage`) с потерянным ответом не повторяются, иначе сообщение может уйти
    дважды; это включается через `retry_unsafe_methods=True`.
    EN: When `retry_after` exceeds `max_flood_wait` the client does not sleep and
    raises `RetryAfter` to the caller instead. Mutating requests (such as
    `sendMessage`) whose response was lost are not resent, because the message could
    be delivered twice; enable that with `retry_unsafe_methods=True`.
    """

    max_attempts: int = 4
    backoff_base: float = 1.0
    backoff_factor: float = 2.0
    max_backoff: float = 30.0
    max_flood_wait: float = 60.0
    retry_server_errors: bool = True
    retry_unsafe_methods: bool = False

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.backoff_base < 0 or self.backoff_factor < 1 or self.max_backoff < 0:
            raise ValueError("Invalid backoff values")

    def can_retry(self, attempt: int) -> bool:
        """UZ: `attempt` (1 dan) — hozirgi urinish raqami.
        RU: `attempt` (с 1) — номер текущей попытки.
        EN: `attempt` (1-based) is the number of the attempt that just failed.
        """
        return attempt < self.max_attempts

    def backoff(self, attempt: int) -> float:
        delay = self.backoff_base * self.backoff_factor ** max(0, attempt - 1)
        return float(min(self.max_backoff, delay))

    def allows_resend(self, method: str, *, request_sent: bool) -> bool:
        """UZ: So'rovni qayta yuborish xavfsizmi (o'qish metodlari doim xavfsiz).
        RU: Безопасно ли повторить запрос (читающие методы всегда безопасны).
        EN: Whether resending is safe (read-only `get*` methods always are).
        """
        return not request_sent or method.startswith("get") or self.retry_unsafe_methods

    def flood_delay(self, retry_after: float) -> float | None:
        return float(retry_after) if retry_after <= self.max_flood_wait else None


#: UZ: Qayta urinishsiz. RU: Без повторов. EN: Never retry.
NO_RETRY = RetryPolicy(max_attempts=1)

__all__ = ["NO_RETRY", "RetryPolicy"]
