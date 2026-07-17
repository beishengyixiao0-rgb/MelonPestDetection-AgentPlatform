"""
语义检索器 — 将 RAG 流程串联为完整管道

职责：
  - 知识库初始化（加载文档 → 分块 → 向量化 → 存储）
  - 语义检索（查询 → 向量化 → Pgvector 检索 → 格式化结果）
  - 知识库管理（重建索引、清空、统计）

使用方式：
  from app.rag.retriever import knowledge_retriever

  # 初始化知识库（首次启动时调用）
  knowledge_retriever.build_index()

  # 检索
  results = knowledge_retriever.search("什么是 IoU？", top_k=3)
"""

import threading

from app.config.settings import settings
from app.core.logger import get_logger
from app.rag.document_loader import document_loader
from app.rag.embedding import embedding_service
from app.vectorstore.pgvector_client import pgvector_client

logger = get_logger(__name__)


class KnowledgeRetriever:
    """知识检索器"""

    def __init__(self):
        self._index_built = False
        # 防止多个请求同时构建同一份索引并产生重复向量。
        self._build_lock = threading.Lock()

    def build_index(self, force_rebuild: bool = False) -> bool:
        """
        构建知识库索引

        流程：加载文档 → 文本分块 → 向量化 → 存入 Pgvector

        Args:
            force_rebuild: 是否强制重建（先清空再构建）
        """
        with self._build_lock:
            existing_count = pgvector_client.count()
            if not force_rebuild and existing_count > 0:
                self._index_built = True
                logger.info("知识库索引已存在 (%d 条)，跳过构建", existing_count)
                return True
            if not pgvector_client.init_table():
                return False

            logger.info("开始构建知识库索引...")
            documents = document_loader.load_documents()
            if not documents:
                logger.warning("知识库中没有文档")
                return False
            chunks = document_loader.split_documents(
                documents, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP
            )
            if not chunks:
                logger.warning("文档分块后为空")
                return False

            texts = [chunk["content"] for chunk in chunks]
            metadatas = [chunk["metadata"] for chunk in chunks]
            embeddings = embedding_service.embed_texts(texts)
            if len(embeddings) != len(texts) or any(
                not embedding for embedding in embeddings
            ):
                logger.error("文本向量化未完整成功，保留原有索引")
                return False

            # 强制重建在新向量生成成功后才清空，避免网络失败时丢失旧索引。
            if force_rebuild:
                pgvector_client.clear()
            if not pgvector_client.insert_embeddings(texts, embeddings, metadatas):
                return False

            self._index_built = True
            logger.info(
                "知识库索引构建完成: %d 个文档 → %d 个文本块 → %d 条向量",
                len(documents),
                len(chunks),
                len(texts),
            )
            return True

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        语义检索

        Args:
            query: 查询文本
            top_k: 返回最相似的前 K 条结果

        Returns:
            检索结果列表 [{"content": "...", "metadata": {...}, "similarity": 0.95}, ...]
        """
        # 搜索不隐式发起外部向量化；索引由建库接口显式创建。
        if pgvector_client.count() <= 0:
            logger.info("知识库索引不存在，跳过检索")
            return []

        # 将查询文本向量化
        query_embedding = embedding_service.embed_query(query)
        if not query_embedding:
            logger.error("查询向量化失败: %s", query)
            return []

        # 在 Pgvector 中检索
        results = pgvector_client.search(query_embedding, top_k=top_k)
        # 低相似度结果不是可靠知识来源，应交由大模型通用回答。
        return [
            result
            for result in results
            if result.get("similarity", 0) >= settings.RAG_SIMILARITY_THRESHOLD
        ]

    def format_context(self, results: list[dict]) -> str:
        """
        将检索结果格式化为 LLM 可用的上下文文本

        Args:
            results: 检索结果列表

        Returns:
            格式化后的上下文字符串
        """
        if not results:
            return "（知识库中暂无相关内容）"

        parts = []
        for i, r in enumerate(results, 1):
            source = r.get("metadata", {}).get("source", "未知")
            similarity = r.get("similarity", 0)
            parts.append(
                f"[知识片段 {i}] (来源: {source}, 相似度: {similarity:.2f})\n"
                f"{r['content']}"
            )

        return "\n\n---\n\n".join(parts)

    def get_stats(self) -> dict:
        """获取知识库统计信息"""
        count = pgvector_client.count()
        return {
            "total_chunks": count,
            "index_built": self._index_built or count > 0,
        }


knowledge_retriever = KnowledgeRetriever()
