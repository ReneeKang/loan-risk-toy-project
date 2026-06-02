"""브라우저가 /openapi.json·/docs·/redoc 을 오래 캐시하지 않도록 응답 헤더를 붙입니다."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class DisableOpenAPICacheMiddleware(BaseHTTPMiddleware):
    """Swagger UI가 예전 OpenAPI 스냅샷을 쓰는 현상 완화."""

    _NO_CACHE_PATHS = frozenset({"/openapi.json", "/docs", "/redoc"})

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        p = request.url.path
        if p in self._NO_CACHE_PATHS or p.startswith("/docs/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
