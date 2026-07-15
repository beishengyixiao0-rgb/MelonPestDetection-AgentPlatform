from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app.config.settings import settings
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.training import router as training_router
from app.api.dataset import router as dataset_router
from app.api.detection import router as detection_router
from app.api.user import router as user_router
from app.api.dashboard import router as dashboard_router
from app.api.history import router as history_router
from app.core.exceptions import register_exception_handlers
from app.middleware.request_logger import RequestLogMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.health_probe import HealthProbeMiddleware



def init_minio():
    """初始化 MinIO 存储桶"""
    from app.storage.minio_client import MinIOClient

    try:
        minio_client = MinIOClient()
        print(f"MinIO 存储桶 '{minio_client.bucket_name}' 初始化完成")
    except Exception as e:
        print(f"MinIO 初始化失败: {e}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期管理"""
    print("正在初始化服务...")
    init_minio()
    yield
    print("服务已关闭")


app = FastAPI(
    title="RSOD Agent Platform",
    version="0.1.0",
    description="基于 YOLOv11 的目标检测智能体平台 API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


original_openapi = app.openapi


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = original_openapi()
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "请输入完整的Authorization头，格式: Bearer <token>",
        }
    }
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi


# ── 注册全局异常处理器 ─────────────────────────────────
register_exception_handlers(app)


# ── 注册中间件（注意顺序）──────────────────────────────
# 中间件执行顺序：后添加的先执行（洋葱模型）
# 1. 速率限制中间件
app.add_middleware(RateLimiterMiddleware)

# 2. 请求日志中间件
app.add_middleware(RequestLogMiddleware)

# 基础探活请求在日志、限流等业务中间件之前快速返回。
app.add_middleware(HealthProbeMiddleware)

# 3. CORS 中间件必须最后注册，使限流的 429 响应也带上跨域响应头。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 注册路由
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(health_router)
app.include_router(dataset_router)
app.include_router(detection_router)
app.include_router(training_router)
app.include_router(user_router)
app.include_router(dashboard_router)
app.include_router(history_router)


@app.get("/")
def root():
    return {
        "message": "欢迎使用 RSOD Agent Platform",
        "version": "0.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
