"""
文本向量化 — 将文本转换为高维向量

职责：
  - 调用 Embedding API 将文本块转换为向量
  - 调用通义千问 Embedding 模型
  - 批量处理提升效率

Embedding 模型选择：
  - 通义千问 text-embedding-v3（固定 1024 维）
"""

from typing import Optional

import httpx
from app.config.settings import EMBEDDING_DIM, settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """文本向量化服务"""

    def __init__(self):
        self._client = None
        self._model = None
        self._init_client()

    def _init_client(self):
        """初始化 Embedding 客户端"""
        try:
            from openai import OpenAI

            # 向量模型优先使用独立密钥，留空时兼容复用对话模型密钥。
            qwen_api_key = (
                getattr(settings, "QWEN_EMBEDDING_API_KEY", "").strip()
                or getattr(settings, "QWEN_API_KEY", "").strip()
            )
            if not qwen_api_key or qwen_api_key == "sk-your-qwen-api-key":
                logger.warning("未配置千问 Embedding 密钥，知识库向量化不可用")
                return

            base_url = getattr(
                settings, "QWEN_EMBEDDING_BASE_URL", ""
            ).strip() or getattr(
                settings,
                "QWEN_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            proxy = getattr(settings, "QWEN_PROXY", "").strip() or None
            # 忽略系统继承代理，避免兼容接口被错误代理配置拦截。
            self._client = OpenAI(
                api_key=qwen_api_key,
                base_url=base_url,
                http_client=httpx.Client(
                    proxy=proxy,
                    timeout=httpx.Timeout(60.0, connect=15.0),
                    trust_env=False,
                ),
            )
            self._model = getattr(settings, "EMBEDDING_MODEL", "text-embedding-v3")

            logger.info("Embedding 服务初始化完成: model=%s", self._model)
        except Exception as e:
            logger.error("Embedding 服务初始化失败: %s", str(e))
            self._client = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        批量将文本转换为向量

        Args:
            texts: 文本列表

        Returns:
            向量列表，每个向量是浮点数列表
        """
        if not self._client:
            logger.error("Embedding 客户端未初始化")
            return [[] for _ in texts]

        try:
            # DashScope text-embedding-v3 单次请求最多接收 10 条输入。
            all_embeddings = []
            batch_size = 10

            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                response = self._client.embeddings.create(
                    model=self._model,
                    input=batch,
                    # 向量表固定为 1024 维，必须显式指定避免默认维度变化。
                    dimensions=EMBEDDING_DIM,
                )
                batch_embeddings = [item.embedding for item in response.data]
                if any(
                    len(embedding) != EMBEDDING_DIM for embedding in batch_embeddings
                ):
                    raise ValueError(
                        f"Embedding 维度必须为 {EMBEDDING_DIM}，实际返回维度不匹配"
                    )
                all_embeddings.extend(batch_embeddings)
                logger.debug(
                    "向量化批次 %d: %d 条文本", i // batch_size + 1, len(batch)
                )

            logger.info(
                "向量化完成: %d 条文本, 向量维度=%d",
                len(texts),
                len(all_embeddings[0]) if all_embeddings else 0,
            )
            return all_embeddings

        except Exception as e:
            logger.error("文本向量化失败: %s", str(e))
            return [[] for _ in texts]

    def embed_query(self, query: str) -> Optional[list[float]]:
        """
        将查询文本转换为向量

        Args:
            query: 查询文本

        Returns:
            向量（浮点数列表），失败返回 None
        """
        results = self.embed_texts([query])
        if results and results[0]:
            return results[0]
        return None


embedding_service = EmbeddingService()