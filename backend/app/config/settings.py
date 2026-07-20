"""
全局配置模块
使用 pydantic-settings 管理所有配置项，支持从 .env 文件和环境变量读取
加载优先级：环境变量（系统级别）> .env 文件 > 代码中的默认值
"""

from pydantic_settings import BaseSettings

# 千问 text-embedding-v3 的项目约定维度，向量表和检索客户端必须保持一致。
# 定义在配置模块但不作为 Settings 字段，避免被 .env 或环境变量覆盖。
EMBEDDING_DIM = 1024


class Settings(BaseSettings):
    """应用全局配置"""

    # ── 训练配置 ──────────────────────────────────────
    TRAIN_OUTPUT_DIR: str = "runs/train"  # 训练输出目录（模型权重、日志等）
    DATASET_BASE_DIR: str = "datasets"  # 数据集根目录

    # — 应用基础配置 —
    APP_NAME: str = "RSOD Agent Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ── 日志配置 ──────────────────────────────────────
    LOG_DIR: str = "logs"  # 日志目录（相对于 backend/）
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 单文件最大 10MB
    LOG_BACKUP_COUNT: int = 5  # 保留 5 份历史日志

    # — 数据库配置 —
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "rsod_agent"
    DB_USER: str = "rsod_admin"
    DB_PASSWORD: str = "rsod_admin"

    @property
    def DATABASE_URL(self) -> str:
        """构造 PostgreSQL 连接字符串"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # — Redis 配置 —
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @property
    def REDIS_URL(self) -> str:
        """构造 Redis 连接字符串"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # — MinIO 配置 —
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "rsod-agent-images"
    MINIO_SECURE: bool = False

    # — JWT 认证配置 —
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # — 通义千问配置（Day 8） —
    # 未配置 Key 时，对话接口仍保留本地检测路由和基础问答降级能力。
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen3.7-max-2026-05-17"
    # 留空时直连 DashScope，避免系统代理导致兼容接口连接失败。
    # 仅在网络环境明确要求代理时填写，例如：http://127.0.0.1:7890
    QWEN_PROXY: str = ""

    # 可选的 OpenAI 兼容后备配置；未配置时不会初始化远程客户端。
    # OPENAI_API_KEY: str = ""
    # OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    # OPENAI_MODEL: str = "gpt-4o-mini"

    # ── RAG / Embedding 配置 ──────────────────────────
    # 向量模型可使用独立密钥；留空时兼容回退到 QWEN_API_KEY。
    QWEN_EMBEDDING_API_KEY: str = ""
    QWEN_EMBEDDING_BASE_URL: str = ""
    EMBEDDING_MODEL: str = "text-embedding-v3"  # 通义千问 Embedding 模型
    RAG_CHUNK_SIZE: int = 500  # 文档分块大小
    RAG_CHUNK_OVERLAP: int = 50  # 分块重叠字符数
    RAG_TOP_K: int = 3  # 检索返回 Top-K 条
    RAG_SIMILARITY_THRESHOLD: float = 0.30  # 低于此相似度视为知识库未命中

    # — CORS 配置 —
    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://localhost:8080"
    )

    # — 邮件 SMTP 配置 —
    SMTP_HOST: str = "smtp.qq.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "农作物病害检测系统"

    @property
    def cors_origins_list(self) -> list:
        """将 CORS 配置字符串转为列表"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 新增


# 创建全局单例，其他模块直接 import 使用
settings = Settings()
