"""UZ: Zafather — Mini App uchun tayyor backend server (aiohttp).
RU: Zafather — готовый backend-сервер для Mini App (aiohttp).
EN: Zafather — a ready-made Mini App backend server (aiohttp).

UZ: Har bir `/api/...` so'rovi avtomatik tekshiriladi: `initData`
`X-Telegram-Init-Data` sarlavhasida (yoki `Authorization: tma <initData>`) kelishi
kerak; tekshiruvdan o'tmasa handler chaqirilmaydi va 401 qaytadi.
RU: Каждый запрос `/api/...` проверяется автоматически: `initData` передаётся в
заголовке `X-Telegram-Init-Data` (или `Authorization: tma <initData>`); при неудаче
handler не вызывается и возвращается 401.
EN: Every `/api/...` request is validated automatically: `initData` must arrive in the
`X-Telegram-Init-Data` header (or `Authorization: tma <initData>`); otherwise the
handler is not called and 401 is returned.

::

    server = app.serve_mini_app(static_dir="webapp")

    @server.api("/me")
    async def me(user, init):
        return {"id": user.id, "name": user.full_name}

    server.run()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Any, TypeVar

from aiohttp import web

from .handler import CallableSpec
from .webapp import WebAppAuthError, WebAppInitData, validate
from .webhook import WebhookRequestHandler

if TYPE_CHECKING:
    from .app import Zafather

log = logging.getLogger("zafather.miniapp")

ApiHandlerT = TypeVar("ApiHandlerT", bound=Callable[..., Any])
Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

INIT_DATA_HEADER = "X-Telegram-Init-Data"


def extract_init_data(request: web.Request) -> str:
    """UZ: So'rovdan `initData` ni oladi. RU: Извлекает `initData` из запроса.
    EN: Extracts `initData` from a request.
    """
    init_data = request.headers.get(INIT_DATA_HEADER, "")
    if init_data:
        return init_data
    authorization = request.headers.get("Authorization", "")
    return authorization[4:] if authorization.lower().startswith("tma ") else ""


async def _request_body(request: web.Request) -> dict[str, Any]:
    if not request.can_read_body:
        return {}
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return dict(await request.post())
    return body if isinstance(body, dict) else {"value": body}


def _json_response(result: Any) -> web.StreamResponse:
    if isinstance(result, web.StreamResponse):
        return result
    if result is None:
        result = {"ok": True}
    elif isinstance(result, dict) and "ok" not in result:
        result = {"ok": True, **result}
    return web.json_response(result)


class MiniAppServer:
    """UZ: Static fayllar + himoyalangan JSON API + (ixtiyoriy) webhook.
    RU: Статика + защищённый JSON API + (опционально) webhook.
    EN: Static files + a protected JSON API + an optional webhook.

    UZ: API handleri kerakli argumentlarni so'raydi: `user`, `init`, `data`, `bot`,
    `app`, `request`.
    RU: API-handler запрашивает нужные аргументы: `user`, `init`, `data`, `bot`, `app`,
    `request`.
    EN: An API handler asks for what it needs: `user`, `init`, `data`, `bot`, `app`,
    `request`.
    """

    def __init__(
        self,
        app: Zafather,
        static_dir: str | None = None,
        *,
        host: str = "0.0.0.0",
        port: int = 8080,
        api_prefix: str = "/api",
        max_age: int = 3600,
        cors_origins: Iterable[str] | None = None,
    ) -> None:
        self.app = app
        self.static_dir = static_dir
        self.host = host
        self.port = port
        self.api_prefix = api_prefix.rstrip("/")
        self.max_age = max_age
        self.cors_origins = frozenset(cors_origins or ())
        self.web = web.Application(middlewares=[self._cors_middleware])
        self._routes: dict[str, CallableSpec] = {}
        self._webhook: WebhookRequestHandler | None = None
        self._runner: web.AppRunner | None = None

    # --- UZ: API / RU: API / EN: API ---------------------------------------------------------
    def api(
        self, path: str, methods: Iterable[str] = ("POST", "GET")
    ) -> Callable[[ApiHandlerT], ApiHandlerT]:
        """UZ: Himoyalangan endpoint qo'shadi. RU: Добавляет защищённый endpoint.
        EN: Registers a protected endpoint.
        """

        def decorator(function: ApiHandlerT) -> ApiHandlerT:
            full_path = f"{self.api_prefix}/{path.lstrip('/')}"
            spec = CallableSpec(function, positional=0)
            self._routes[full_path] = spec
            for method in methods:
                self.web.router.add_route(method, full_path, self._make_handler(spec))
            return function

        return decorator

    def _authorize(self, request: web.Request) -> WebAppInitData:
        return validate(extract_init_data(request), self.app.bot.token, self.max_age)

    def _make_handler(self, spec: CallableSpec) -> Handler:
        async def handler(request: web.Request) -> web.StreamResponse:
            try:
                init = self._authorize(request)
            except WebAppAuthError as exc:
                log.warning("Rejected Mini App request: %s", exc)
                return web.json_response({"ok": False, "error": str(exc)}, status=401)
            context = {
                "request": request,
                "init": init,
                "user": init.user,
                "data": await _request_body(request),
                "bot": self.app.bot,
                "app": self.app,
            }
            try:
                result = await spec(context=context)
            except web.HTTPException:
                raise
            except Exception:
                log.exception("Mini App API handler failed: %s", request.path)
                return web.json_response({"ok": False, "error": "internal error"}, status=500)
            return _json_response(result)

        return handler

    # --- CORS --------------------------------------------------------------------------------
    @web.middleware
    async def _cors_middleware(self, request: web.Request, handler: Handler) -> web.StreamResponse:
        response = (
            web.Response(status=204) if request.method == "OPTIONS" else await handler(request)
        )
        origin = request.headers.get("Origin")
        if origin and ("*" in self.cors_origins or origin in self.cors_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = (
                f"Content-Type, {INIT_DATA_HEADER}, Authorization"
            )
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Vary"] = "Origin"
        return response

    # --- UZ: webhook / RU: webhook / EN: webhook --------------------------------------------
    def add_webhook(self, path: str = "/webhook", secret_token: str | None = None) -> MiniAppServer:
        """UZ: Botni webhook rejimida shu serverga ulaydi.
        RU: Подключает бота к этому серверу в режиме webhook.
        EN: Serves the bot's webhook from this server.
        """
        self._webhook = WebhookRequestHandler(self.app.feed_raw_update, secret_token=secret_token)
        self.web.router.add_post(path, self._webhook.handle)
        return self

    # --- UZ: static / RU: статика / EN: static files -----------------------------------------
    def _mount_static(self) -> None:
        if not self.static_dir:
            return
        directory = os.path.abspath(self.static_dir)
        if not os.path.isdir(directory):
            log.warning("Static directory not found: %s", directory)
            return
        index = os.path.join(directory, "index.html")
        has_index = os.path.exists(index)

        async def serve_index(request: web.Request) -> web.StreamResponse:
            if has_index:
                return web.FileResponse(index, headers={"Cache-Control": "no-store"})
            return web.Response(text="index.html not found", status=404)

        self.web.router.add_get("/", serve_index)
        self.web.router.add_static("/", directory, show_index=False)

    # --- UZ: ishga tushirish / RU: запуск / EN: running -------------------------------------
    async def start(self) -> None:
        self._mount_static()
        self._runner = web.AppRunner(self.web)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.host, self.port).start()
        log.info("Mini App server: http://%s:%s", self.host, self.port)

    async def stop(self) -> None:
        if self._webhook is not None:
            await self._webhook.close()
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def start_with_polling(self, **polling_options: Any) -> None:
        """UZ: Server va bot polling'ini birga ishlatadi. RU: Сервер и polling вместе.
        EN: Runs the server together with bot polling.
        """
        await self.start()
        try:
            await self.app.start_polling(**polling_options)
        finally:
            await self.stop()

    def run(self, with_polling: bool = True, log_level: int = logging.INFO) -> None:
        """UZ: Sinxron ishga tushirish (Ctrl+C bilan to'xtaydi).
        RU: Синхронный запуск (остановка по Ctrl+C).
        EN: Blocking run (stops with Ctrl+C).
        """
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )

        async def serve_forever() -> None:
            await self.start()
            try:
                await asyncio.Event().wait()
            finally:
                await self.stop()

        try:
            asyncio.run(self.start_with_polling() if with_polling else serve_forever())
        except KeyboardInterrupt:
            log.info("Stopping…")

    def __repr__(self) -> str:
        return f"<MiniAppServer {self.host}:{self.port} api={len(self._routes)}>"


__all__ = ["INIT_DATA_HEADER", "MiniAppServer", "extract_init_data"]
