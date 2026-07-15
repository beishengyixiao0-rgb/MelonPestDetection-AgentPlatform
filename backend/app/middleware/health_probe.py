"""轻量级健康探活中间件。"""

from app.api.health import health_check
from starlette.responses import JSONResponse


class HealthProbeMiddleware:
    """在业务中间件之前快速响应基础健康探活请求。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") == "http"
            and scope.get("method") in {"GET", "HEAD"}
            and scope.get("path") in {"/api/health", "/api/health/"}
        ):
            response = JSONResponse(await health_check())
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
