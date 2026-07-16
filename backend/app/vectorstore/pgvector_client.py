"""
Pgvector 客户端 — 基于 PostgreSQL pgvector 扩展的向量存储

职责：
  - 创建和管理 knowledge_embeddings 表
  - 插入/更新向量数据
  - 余弦相似度检索
  - 表结构初始化和迁移

表结构：
  knowledge_embeddings (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,          -- 文本块内容
    metadata JSONB,                 -- 元数据（来源、标题等）
    embedding vector(1024),         -- 向量（维度取决于 Embedding 模型）
    created_at TIMESTAMP DEFAULT NOW()
  )

依赖：
  - PostgreSQL 需要安装 pgvector 扩展: CREATE EXTENSION IF NOT EXISTS vector;
  - Docker Compose 已使用 pgvector/pgvector:pg15 镜像
"""

from typing import Optional

from app.core.logger import get_logger
from app.database.session import SessionLocal
from sqlalchemy import text

logger = get_logger(__name__)

# 向量维度（取决于 Embedding 模型：text-embedding-v3=1024, text-embedding-3-small=1536）
EMBEDDING_DIM = 1024

# 建表 SQL
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS knowledge_embeddings (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{{}}'::jsonb,
    embedding vector({EMBEDDING_DIM}),
    created_at TIMESTAMP DEFAULT NOW()
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_vector
ON knowledge_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
"""


class PgvectorClient:
    """Pgvector 向量存储客户端"""

    def __init__(self):
        self._initialized = False

    def init_table(self):
        """初始化向量表和索引"""
        if self._initialized:
            return

        db = SessionLocal()
        try:
            # 启用 pgvector 扩展
            db.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            db.execute(text(CREATE_TABLE_SQL))
            db.execute(text(CREATE_INDEX_SQL))
            db.commit()
            self._initialized = True
            logger.info("Pgvector 表和索引初始化完成")
        except Exception as e:
            db.rollback()
            logger.error("Pgvector 初始化失败: %s", str(e))
        finally:
            db.close()

    def insert_embeddings(
        self,
        contents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] = None,
    ):
        """
        批量插入向量数据

        Args:
            contents: 文本内容列表
            embeddings: 向量列表
            metadatas: 元数据列表
        """
        if not contents or not embeddings:
            return

        db = SessionLocal()
        try:
            import json

            for i in range(len(contents)):
                metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                embedding_str = "[" + ",".join(str(v) for v in embeddings[i]) + "]"

                db.execute(
                    text(
                        "INSERT INTO knowledge_embeddings (content, metadata, embedding) "
                        "VALUES (:content, :metadata::jsonb, :embedding::vector)"
                    ),
                    {
                        "content": contents[i],
                        "metadata": json.dumps(metadata, ensure_ascii=False),
                        "embedding": embedding_str,
                    },
                )

            db.commit()
            logger.info("插入 %d 条向量数据", len(contents))
        except Exception as e:
            db.rollback()
            logger.error("插入向量数据失败: %s", str(e))
        finally:
            db.close()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 3,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        """
        余弦相似度检索

        Args:
            query_embedding: 查询向量
            top_k: 返回最相似的前 K 条结果
            filter_metadata: 元数据过滤条件（可选）

        Returns:
            检索结果列表 [{"content": "...", "metadata": {...}, "similarity": 0.95}, ...]
        """
        db = SessionLocal()
        try:
            embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

            # 余弦距离 → 相似度：similarity = 1 - distance
            sql = """
                SELECT
                    content,
                    metadata,
                    1 - (embedding <=> :query::vector) AS similarity
                FROM knowledge_embeddings
                ORDER BY embedding <=> :query::vector
                LIMIT :top_k
            """

            results = db.execute(
                text(sql),
                {"query": embedding_str, "top_k": top_k},
            ).fetchall()

            search_results = []
            for row in results:
                search_results.append(
                    {
                        "content": row[0],
                        "metadata": row[1] if isinstance(row[1], dict) else {},
                        "similarity": round(float(row[2]), 4),
                    }
                )

            logger.info(
                "向量检索完成: top_k=%d, 最高相似度=%.4f",
                top_k,
                search_results[0]["similarity"] if search_results else 0,
            )
            return search_results

        except Exception as e:
            logger.error("向量检索失败: %s", str(e))
            return []
        finally:
            db.close()

    def count(self) -> int:
        """获取向量表中的记录数"""
        db = SessionLocal()
        try:
            result = db.execute(
                text("SELECT COUNT(*) FROM knowledge_embeddings")
            ).scalar()
            return result or 0
        except Exception:
            return 0
        finally:
            db.close()

    def clear(self):
        """清空向量表"""
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM knowledge_embeddings"))
            db.commit()
            logger.info("向量表已清空")
        except Exception as e:
            db.rollback()
            logger.error("清空向量表失败: %s", str(e))
        finally:
            db.close()


pgvector_client = PgvectorClient()
