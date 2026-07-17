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

from app.config.settings import EMBEDDING_DIM
from app.core.logger import get_logger
from app.database.session import SessionLocal
from sqlalchemy import text

logger = get_logger(__name__)

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

# SQLAlchemy 的 text() 不会将 :parameter::type 稳定识别为绑定参数。
# 使用 CAST 可同时保证 PostgreSQL 类型转换和参数安全绑定。
INSERT_EMBEDDINGS_SQL = """
INSERT INTO knowledge_embeddings (content, metadata, embedding)
VALUES (:content, CAST(:metadata AS JSONB), CAST(:embedding AS vector))
"""

# 检索 SQL 同样使用 CAST，保证 query 能被 SQLAlchemy 作为绑定参数传入。
SEARCH_EMBEDDINGS_SQL = """
SELECT
    content,
    metadata,
    1 - (embedding <=> CAST(:query AS vector)) AS similarity
FROM knowledge_embeddings
ORDER BY embedding <=> CAST(:query AS vector)
LIMIT :top_k
"""

# 带过滤条件的检索 SQL
SEARCH_EMBEDDINGS_FILTER_SQL = """
SELECT
    content,
    metadata,
    1 - (embedding <=> CAST(:query AS vector)) AS similarity
FROM knowledge_embeddings
WHERE metadata @> CAST(:filter AS JSONB)
ORDER BY embedding <=> CAST(:query AS vector)
LIMIT :top_k
"""

# 按 document_id 删除向量 SQL
DELETE_BY_DOCUMENT_ID_SQL = """
DELETE FROM knowledge_embeddings
WHERE metadata->>'document_id' = :document_id
"""


class PgvectorClient:
    """Pgvector 向量存储客户端"""

    def __init__(self):
        self._initialized = False

    def init_table(self) -> bool:
        """初始化向量表和索引"""
        if self._initialized:
            return True

        db = SessionLocal()
        try:
            # 启用 pgvector 扩展
            db.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            db.execute(text(CREATE_TABLE_SQL))
            db.execute(text(CREATE_INDEX_SQL))
            db.commit()
            self._initialized = True
            logger.info("Pgvector 表和索引初始化完成")
            return True
        except Exception as e:
            db.rollback()
            logger.error("Pgvector 初始化失败: %s", str(e))
            return False
        finally:
            db.close()

    def insert_embeddings(
        self,
        contents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] = None,
    ) -> bool:
        """
        批量插入向量数据

        Args:
            contents: 文本内容列表
            embeddings: 向量列表
            metadatas: 元数据列表
        """
        if not contents or not embeddings:
            return False
        # 写入前统一校验维度，避免数据库错误被吞掉后显示为建库成功。
        if any(len(embedding) != EMBEDDING_DIM for embedding in embeddings):
            logger.error("拒绝写入非 %d 维的向量", EMBEDDING_DIM)
            return False

        if not self.init_table():
            logger.error("向量表初始化失败")
            return False

        db = SessionLocal()
        try:
            import json

            for i in range(len(contents)):
                metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                embedding_str = "[" + ",".join(str(v) for v in embeddings[i]) + "]"

                db.execute(
                    text(INSERT_EMBEDDINGS_SQL),
                    {
                        "content": contents[i],
                        "metadata": json.dumps(metadata, ensure_ascii=False),
                        "embedding": embedding_str,
                    },
                )

            db.commit()
            logger.info("插入 %d 条向量数据", len(contents))
            return True
        except Exception as e:
            db.rollback()
            logger.error("插入向量数据失败: %s", str(e))
            return False
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
            filter_metadata: 元数据过滤条件（可选），如 {"status": "approved"}

        Returns:
            检索结果列表 [{"content": "...", "metadata": {...}, "similarity": 0.95}, ...]
        """
        if len(query_embedding) != EMBEDDING_DIM:
            logger.error("查询向量维度必须为 %d，实际为 %d", EMBEDDING_DIM, len(query_embedding))
            return []
        db = SessionLocal()
        try:
            embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
            import json

            if filter_metadata:
                filter_str = json.dumps(filter_metadata, ensure_ascii=False)
                results = db.execute(
                    text(SEARCH_EMBEDDINGS_FILTER_SQL),
                    {"query": embedding_str, "filter": filter_str, "top_k": top_k},
                ).fetchall()
            else:
                results = db.execute(
                    text(SEARCH_EMBEDDINGS_SQL),
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
                "向量检索完成: top_k=%d, filter=%s, 最高相似度=%.4f",
                top_k,
                filter_metadata,
                search_results[0]["similarity"] if search_results else 0,
            )
            return search_results

        except Exception as e:
            logger.error("向量检索失败: %s", str(e))
            return []
        finally:
            db.close()

    def delete_by_document_id(self, document_id: int) -> int:
        """
        按文档ID删除对应的所有向量

        Args:
            document_id: 文档ID

        Returns:
            删除的向量数量
        """
        db = SessionLocal()
        try:
            result = db.execute(
                text(DELETE_BY_DOCUMENT_ID_SQL),
                {"document_id": str(document_id)},
            )
            deleted_count = result.rowcount or 0
            db.commit()
            logger.info("删除文档 %d 的向量: %d 条", document_id, deleted_count)
            return deleted_count
        except Exception as e:
            db.rollback()
            logger.error("删除文档向量失败: %s", str(e))
            return 0
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
