#!/usr/bin/env python
"""
导入本地 knowledge_base 文档到 MinIO 和 knowledge_documents。

使用方式：
    cd backend
    python tools/import_knowledge_base_documents.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parents[1] / "knowledge_base"
MINIO_IMPORT_PREFIX = "knowledge/documents/imported"


def _extract_title(content: str, default: str) -> str:
    """优先使用 Markdown 一级标题作为知识库文档标题。"""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return default


def _find_admin_user(db):
    """导入脚本需要一个管理员作为上传者和审核者。"""
    from app.entity.db_models import Role, User, UserRole

    admin_user = (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(Role.name == "admin")
        .order_by(User.id.asc())
        .first()
    )
    if admin_user:
        return admin_user
    return db.query(User).order_by(User.id.asc()).first()


def import_knowledge_base_documents():
    from app.database.session import get_db
    from app.entity.db_models import KnowledgeDocument
    from app.rag.retriever import knowledge_retriever
    from app.storage.minio_client import MinIOClient

    if not KNOWLEDGE_BASE_DIR.exists():
        raise SystemExit(f"知识库目录不存在: {KNOWLEDGE_BASE_DIR}")

    db = next(get_db())
    admin_user = _find_admin_user(db)
    if not admin_user:
        raise SystemExit("没有可用用户，请先运行 tools/init_roles.py 创建管理员")

    minio_client = MinIOClient()
    files = sorted(KNOWLEDGE_BASE_DIR.glob("*.md")) + sorted(KNOWLEDGE_BASE_DIR.glob("*.txt"))
    if not files:
        raise SystemExit(f"目录中没有 .md 或 .txt 文档: {KNOWLEDGE_BASE_DIR}")

    print(f"=== 导入知识库文档: {len(files)} 个 ===")
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        object_name = f"{MINIO_IMPORT_PREFIX}/{file_path.name}"
        content_type = "text/markdown; charset=utf-8" if file_path.suffix.lower() == ".md" else "text/plain; charset=utf-8"

        # 使用确定 object_name，脚本重复执行时会覆盖 MinIO 对象并复用数据库记录。
        minio_client.upload_bytes(object_name, content.encode("utf-8"), content_type)

        document = db.query(KnowledgeDocument).filter(KnowledgeDocument.file_path == object_name).first()
        if not document:
            document = KnowledgeDocument(
                title=_extract_title(content, file_path.stem),
                file_path=object_name,
                uploader_id=admin_user.id,
                status="approved",
                reviewer_id=admin_user.id,
                reviewed_at=datetime.now(),
                visibility="public",
            )
            db.add(document)
            db.commit()
            db.refresh(document)
        else:
            document.title = _extract_title(content, file_path.stem)
            document.status = "approved"
            document.reviewer_id = admin_user.id
            document.reviewed_at = datetime.now()
            document.visibility = "public"
            db.commit()
            db.refresh(document)

        # 重新导入时先删除该文档旧向量，避免重复 chunk 干扰检索结果。
        deleted_count = knowledge_retriever.delete_document_index(document.id)
        chunk_count = knowledge_retriever.index_document(document.id, document.file_path, document.title)
        document.chunk_count = chunk_count
        db.commit()

        status = "indexed" if chunk_count > 0 else "index_failed"
        print(f"- {file_path.name}: document_id={document.id}, deleted_vectors={deleted_count}, chunks={chunk_count}, {status}")

    print("=== 导入完成 ===")


if __name__ == "__main__":
    import_knowledge_base_documents()
