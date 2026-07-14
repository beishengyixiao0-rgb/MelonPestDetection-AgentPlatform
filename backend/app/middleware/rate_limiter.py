"""
速率限制中间件

职责：
    - 限制特定 API 端点的请求频率
    - 防止恶意攻击和滥用
    - 使用 Redis 存储请求计数（降级到内存存储）

速率限制配置：
    - /api/detection/video: 每分钟 5 次
    - /api/detection/batch: 每分钟 5 次
    - /api/detection/zip: 每分钟 3 次
    - /api/training/train: 每分钟 2 次
    - 默认: 每分钟 100 次
"""

import os
import time
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.storage.redis_client import redis_client

# 测试环境中禁用速率限制
DISABLE_RATE_LIMIT = os.environ.get("DISABLE_RATE_LIMIT", "").lower() in ("1", "true", "yes")


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """API 速率限制中间件"""

    RATE_LIMITS = {
        "/api/detection/video/status": {"limit": 60, "window": 60},
        "/api/detection/status": {"limit": 60, "window": 60},
        "/api/detection/video": {"limit": 5, "window": 60},
        "/api/detection/batch": {"limit": 5, "window": 60},
        "/api/detection/zip": {"limit": 3, "window": 60},
        "/api/training/train": {"limit": 2, "window": 60},
    }

    DEFAULT_LIMIT = {"limit": 100, "window": 60}

    async def dispatch(self, request: Request, call_next):
        if DISABLE_RATE_LIMIT:
            return await call_next(request)
        path = request.url.path

        for pattern, config in self.RATE_LIMITS.items():
            if path.startswith(pattern):
                limit = config["limit"]
                window = config["window"]
                break
        else:
            limit = self.DEFAULT_LIMIT["limit"]
            window = self.DEFAULT_LIMIT["window"]

        client_ip = request.client.host if request.client else "unknown"
        user_id = getattr(request.state, "user_id", None)

        if user_id:
            key = f"rate_limit:{path}:user:{user_id}"
        else:
            key = f"rate_limit:{path}:ip:{client_ip}"

        current_time = int(time.time())
        window_key = f"{key}:{current_time // window}"

        try:
            count = redis_client.get(window_key)
            count = int(count) if count else 0

            if count >= limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "请求过于频繁，请稍后再试",
                        "retry_after": window - (current_time % window),
                    },
                )

            redis_client.set(window_key, str(count + 1), expire=window)
        except Exception as e:
            print(f"Rate limiting error: {e}")

        response = await call_next(request)
        return response