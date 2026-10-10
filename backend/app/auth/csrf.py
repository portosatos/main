"""CSRF protection (SPEC F1): every mutating request must carry `X-Requested-With: ht`.

A cross-site form cannot set custom headers, and a cross-site fetch with one needs a CORS
preflight that this API never allows. Together with SameSite=Lax this keeps other sites from
acting with the user's cookie. The check runs before routing, so it covers every route,
present and future (ADR-026).
"""

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "ht"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class CsrfHeaderMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in SAFE_METHODS:
            if Headers(scope=scope).get(CSRF_HEADER) != CSRF_VALUE:
                response = JSONResponse(
                    {"detail": f"Нужен заголовок {CSRF_HEADER}: {CSRF_VALUE}"}, status_code=403
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
