"""Zafather — Mini App uchun tayyor backend server (aiohttp asosida).

    server = MiniAppServer(bot, static_dir="webapp")

    @server.api("/me")
    async def me(user, init):
        return {"id": user.id, "name": user.full_name}

    server.run()          # http://0.0.0.0:8080

Har bir `/api/...` so'rovi avtomatik tekshiriladi: `initData` `X-Telegram-Init-Data`
sarlavhasida (yoki `Authorization: tma <initData>`) kelishi kerak. Tekshiruvdan
o'tmasa handler umuman chaqirilmaydi va 401 qaytadi.
"""
from __future__ import annotations

import inspect
import json
import logging
import os
from typing import Callable, Dict, Optional

from aiohttp import web

from .webapp import WebAppAuthError, WebAppInitData, validate

log = logging.getLogger("zafather.miniapp")


class MiniAppServer:
    """Static fayllar + himoyalangan JSON API + (ixtiyoriy) webhook."""

    def __init__(
        self,
        app,
        static_dir: Optional[str] = None,
        *,
        host: str = "0.0.0.0",
        port: int = 8080,
        api_prefix: str = "/api",
        max_age: int = 3600,
        cors_origins: Optional[list] = None,
    ) -> None:
        self.app = app                      # Zafather nusxasi
        self.token = app.bot.token
        self.static_dir = static_dir
        self.host = host
        self.port = port
        self.api_prefix = api_prefix.rstrip("/")
        self.max_age = max_age
        self.cors_origins = cors_origins or []
        self.web = web.Application(middlewares=[self._cors_middleware])
        self._routes: Dict[str, Callable] = {}
        self._runner: Optional[web.AppRunner] = None

    # --- API dekoratori -------------------------------------------------------
    def api(self, path: str, methods=("POST", "GET")) -> Callable:
        """Himoyalangan endpoint. Handler kerakli argumentlarni so'raydi:
        `user`, `init`, `data`, `bot`, `request`."""

        def decorator(func: Callable) -> Callable:
            full = f"{self.api_prefix}/{path.lstrip('/')}"
            self._routes[full] = func
            for method in methods:
                self.web.router.add_route(method, full, self._make_handler(func))
            log.debug("API qo'shildi: %s %s", "/".join(methods), full)
            return func

        return decorator

    def _make_handler(self, func: Callable) -> Callable:
        async def handler(request: web.Request) -> web.Response:
            init_data = request.headers.get("X-Telegram-Init-Data", "")
            if not init_data:
                auth = request.headers.get("Authorization", "")
                if auth.lower().startswith("tma "):
                    init_data = auth[4:]

            try:
                init: WebAppInitData = validate(init_data, self.token, self.max_age)
            except WebAppAuthError as exc:
                log.warning("Tekshiruvdan o'tmadi: %s", exc)
                return web.json_response(
                    {"ok": False, "error": str(exc)}, status=401
                )

            body = {}
            if request.can_read_body:
                try:
                    body = await request.json()
                except (json.JSONDecodeError, ValueError):
                    body = dict(await request.post())

            context = {
                "request": request,
                "init": init,
                "user": init.user,
                "data": body,
                "bot": self.app.bot,
                "app": self.app,
            }
            params = inspect.signature(func).parameters
            if any(p.kind == p.VAR_KEYWORD for p in params.values()):
                kwargs = context
            else:
                kwargs = {k: v for k, v in context.items() if k in params}

            try:
                result = func(**kwargs)
                if inspect.isawaitable(result):
                    result = await result
            except Exception as exc:  # noqa: BLE001
                log.exception("API xatosi: %s", exc)
                return web.json_response(
                    {"ok": False, "error": "server xatosi"}, status=500
                )

            if isinstance(result, web.Response):
                return result
            if result is None:
                result = {"ok": True}
            if isinstance(result, dict) and "ok" not in result:
                result = {"ok": True, **result}
            return web.json_response(result)

        return handler

    # --- CORS -----------------------------------------------------------------
    @web.middleware
    async def _cors_middleware(self, request: web.Request, handler):
        if request.method == "OPTIONS":
            response = web.Response(status=204)
        else:
            response = await handler(request)
        origin = request.headers.get("Origin")
        if origin and (("*" in self.cors_origins) or (origin in self.cors_origins)):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, X-Telegram-Init-Data, Authorization"
            )
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    # --- webhook --------------------------------------------------------------
    def add_webhook(self, path: str = "/webhook", secret_token: Optional[str] = None):
        """Botni webhook rejimida shu serverga ulaydi."""

        async def handler(request: web.Request) -> web.Response:
            if secret_token:
                header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
                if header != secret_token:
                    return web.Response(status=403)
            payload = await request.json()
            await self.app.handle_webhook(payload)
            return web.Response(text="ok")

        self.web.router.add_post(path, handler)
        return self

    # --- static ---------------------------------------------------------------
    def _mount_static(self) -> None:
        if not self.static_dir:
            return
        directory = os.path.abspath(self.static_dir)
        if not os.path.isdir(directory):
            log.warning("static papkasi topilmadi: %s", directory)
            return

        index = os.path.join(directory, "index.html")

        async def serve_index(request: web.Request) -> web.Response:
            if os.path.exists(index):
                return web.FileResponse(index, headers={"Cache-Control": "no-store"})
            return web.Response(text="index.html topilmadi", status=404)

        self.web.router.add_get("/", serve_index)
        self.web.router.add_static("/", directory, show_index=False)
        log.info("Static papka: %s", directory)

    # --- ishga tushirish ------------------------------------------------------
    async def start(self) -> None:
        self._mount_static()
        self._runner = web.AppRunner(self.web)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        log.info("Mini App serveri: http://%s:%s", self.host, self.port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    async def start_with_polling(self, **polling_kwargs) -> None:
        """Serverni va botning polling'ini birga ishga tushiradi."""
        await self.start()
        try:
            await self.app.start_polling(**polling_kwargs)
        finally:
            await self.stop()

    def run(self, with_polling: bool = True, log_level: int = logging.INFO) -> None:
        """Sinxron ishga tushirish (Ctrl+C bilan to'xtatiladi)."""
        import asyncio

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        try:
            if with_polling:
                asyncio.run(self.start_with_polling())
            else:

                async def serve_forever():
                    await self.start()
                    while True:
                        await asyncio.sleep(3600)

                asyncio.run(serve_forever())
        except KeyboardInterrupt:
            log.info("To'xtatilmoqda…")

    def __repr__(self) -> str:
        return f"<MiniAppServer {self.host}:{self.port} api={len(self._routes)}>"
