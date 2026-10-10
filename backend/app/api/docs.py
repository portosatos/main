"""Swagger UI at /docs that sends the CSRF header, like the frontend does (ADR-026).

Without it every "Try it out" on a POST would get 403 from CsrfHeaderMiddleware.
"""

from fastapi import APIRouter, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from app.auth.csrf import CSRF_HEADER, CSRF_VALUE

router = APIRouter(include_in_schema=False)

_BUNDLE_CALL = "SwaggerUIBundle({"
_INTERCEPTOR = (
    "SwaggerUIBundle({\n"
    f"        requestInterceptor: (req) => {{ req.headers['{CSRF_HEADER}'] = '{CSRF_VALUE}';"
    " return req; },"
)


@router.get("/docs")
async def swagger_ui(request: Request) -> HTMLResponse:
    page = get_swagger_ui_html(openapi_url=request.app.openapi_url, title=request.app.title)
    html = bytes(page.body).decode()
    if _BUNDLE_CALL not in html:  # a FastAPI upgrade changed the template
        raise RuntimeError("Swagger UI template changed: cannot add the CSRF header")
    return HTMLResponse(html.replace(_BUNDLE_CALL, _INTERCEPTOR, 1))
