"""Day11 RAG 知识库与单 Agent 多工具的无外部依赖回归测试。"""

from types import SimpleNamespace
import asyncio

from app.agent.detection_agent import ALL_TOOLS, detection_agent
from app.agent.prompts import get_detection_agent_prompt
from app.agent.tools.analysis_tool import query_user_list, reset_tool_context, set_tool_context
from app.rag import embedding as embedding_module
from app.rag import retriever as retriever_module
from app.vectorstore.pgvector_client import (
    INSERT_EMBEDDINGS_SQL,
    SEARCH_EMBEDDINGS_SQL,
)


def test_agent_binds_eight_tools_and_uses_language_prompt():
    """单 Agent 必须绑定检测、知识、统计、历史和用户列表共八个工具。"""
    tool_names = {tool_item.name for tool_item in ALL_TOOLS}

    assert len(ALL_TOOLS) == 8
    assert tool_names == {
        "detect_single_image",
        "detect_batch_images",
        "detect_zip_images_file",
        "detect_video_file",
        "search_knowledge",
        "query_detection_stats",
        "query_detection_history",
        "query_user_list",
    }
    assert "来源文件（相似度）" in get_detection_agent_prompt("zh")
    assert "fallback_to_llm" in get_detection_agent_prompt("en")


def test_non_admin_cannot_query_user_list():
    """用户列表工具必须在执行层拒绝普通用户，而非只依赖提示词。"""
    tokens = set_tool_context(user_id=1, is_admin=False)
    try:
        result = query_user_list.invoke({"limit": 1})
    finally:
        reset_tool_context(tokens)

    assert "仅管理员可查询" in result


def test_retriever_filters_low_similarity_without_external_calls(monkeypatch):
    """低于阈值的向量结果应视为未命中，交由大模型通用回答。"""
    retriever = retriever_module.KnowledgeRetriever()
    monkeypatch.setattr(retriever_module.pgvector_client, "count", lambda: 1)
    monkeypatch.setattr(
        retriever_module.embedding_service, "embed_query", lambda query: [0.0] * 1024
    )
    monkeypatch.setattr(
        retriever_module.pgvector_client,
        "search",
        lambda embedding, top_k, filter_metadata=None: [
            {"content": "无关内容", "metadata": {"source": "test.md"}, "similarity": 0.2}
        ],
    )

    assert retriever.search("无关问题") == []


def test_retriever_keeps_relevant_similarity_without_external_calls(monkeypatch):
    """相似度达到 0.30 的领域内容应保留，不能被过高阈值误过滤。"""
    retriever = retriever_module.KnowledgeRetriever()
    monkeypatch.setattr(retriever_module.settings, "RAG_SIMILARITY_THRESHOLD", 0.30)
    monkeypatch.setattr(retriever_module.pgvector_client, "count", lambda: 1)
    monkeypatch.setattr(
        retriever_module.embedding_service, "embed_query", lambda query: [0.0] * 1024
    )
    expected = {
        "content": "IoU 用于衡量两个边界框的重叠程度",
        "metadata": {"source": "yolo_detection.md"},
        "similarity": 0.3868,
    }
    monkeypatch.setattr(
        retriever_module.pgvector_client,
        "search",
        lambda embedding, top_k, filter_metadata=None: [expected],
    )

    assert retriever.search("什么是 IoU") == [expected]


def test_index_document_returns_document_chunk_count(monkeypatch):
    """单文档索引应返回当前文档分块数，不能用全库向量总数代替。"""
    retriever = retriever_module.KnowledgeRetriever()
    inserted = {}

    monkeypatch.setattr(
        retriever_module.document_loader,
        "load_single_document",
        lambda file_path, title: [{"content": "知识库内容", "metadata": {"source": "a.md"}}],
    )
    monkeypatch.setattr(
        retriever_module.document_loader,
        "split_documents",
        lambda documents, chunk_size, chunk_overlap: [
            {"content": "片段1", "metadata": {"source": "a.md"}},
            {"content": "片段2", "metadata": {"source": "a.md"}},
        ],
    )
    monkeypatch.setattr(
        retriever_module.embedding_service,
        "embed_texts",
        lambda texts: [[0.0] * 1024 for _ in texts],
    )

    def fake_insert_embeddings(contents, embeddings, metadatas):
        inserted["metadatas"] = metadatas
        return True

    monkeypatch.setattr(retriever_module.pgvector_client, "insert_embeddings", fake_insert_embeddings)

    assert retriever.index_document(7, "knowledge/documents/a.md", "测试文档") == 2
    assert inserted["metadatas"][0]["document_id"] == 7
    assert inserted["metadatas"][0]["status"] == "approved"


def test_embedding_rejects_non_1024_dimension(monkeypatch):
    """Embedding 服务必须拒绝非 1024 维响应，避免写入错误向量表。"""
    class FakeClient:
        def __init__(self):
            self.embeddings = self

        def create(self, model, input, dimensions):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0, 0.1])])

    monkeypatch.setattr(embedding_module.embedding_service, "_client", FakeClient())
    monkeypatch.setattr(embedding_module.embedding_service, "_model", "text-embedding-v3")

    assert embedding_module.embedding_service.embed_texts(["测试文本"]) == [[]]


def test_embedding_uses_1024_dimensions_and_batches_at_ten(monkeypatch):
    """千问接口必须显式使用 1024 维，且每批不超过其 10 条输入限制。"""
    calls = []

    class FakeClient:
        def __init__(self):
            self.embeddings = self

        def create(self, model, input, dimensions):
            calls.append({"model": model, "input": input, "dimensions": dimensions})
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.0] * 1024) for _ in input]
            )

    monkeypatch.setattr(embedding_module.embedding_service, "_client", FakeClient())
    monkeypatch.setattr(embedding_module.embedding_service, "_model", "text-embedding-v3")

    embeddings = embedding_module.embedding_service.embed_texts(
        [f"测试文本 {index}" for index in range(25)]
    )

    assert len(embeddings) == 25
    assert [len(call["input"]) for call in calls] == [10, 10, 5]
    assert all(call["dimensions"] == 1024 for call in calls)


def test_embedding_insert_sql_binds_all_parameters():
    """向量写入 SQL 必须正确绑定内容、元数据和向量三个参数。"""
    from sqlalchemy import text

    assert set(text(INSERT_EMBEDDINGS_SQL)._bindparams) == {
        "content",
        "metadata",
        "embedding",
    }


def test_embedding_search_sql_binds_query_and_limit():
    """向量检索 SQL 必须正确绑定查询向量与返回条数。"""
    from sqlalchemy import text

    assert set(text(SEARCH_EMBEDDINGS_SQL)._bindparams) == {"query", "top_k"}


def test_knowledge_build_requires_admin(client, user_headers):
    """全量重建索引属于管理员操作，普通用户不能触发。"""
    response = client.post("/api/knowledge/build", headers=user_headers)

    assert response.status_code == 403


def test_knowledge_build_failure_returns_503(client, admin_headers, monkeypatch):
    """管理员发起建库失败时必须返回真实 HTTP 错误。"""
    from app.api import knowledge
    from tests.conftest import TestSessionLocal

    monkeypatch.setattr(knowledge, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(
        knowledge.knowledge_retriever,
        "rebuild_approved_documents",
        lambda db, force_rebuild=False: {"success": False, "total_chunks": 0, "index_built": False},
    )

    response = client.post("/api/knowledge/build", headers=admin_headers)

    assert response.status_code == 503
    # 项目全局异常处理器将 HTTPException.detail 放入统一的 message 字段。
    assert response.json()["message"]["message"] == "知识库索引构建失败"


def test_batch_upload_documents_writes_minio_object_names(client, user_headers, monkeypatch):
    """批量上传应逐个写入 MinIO，并在 file_path 中保存 object_name。"""
    from app.api import knowledge
    from app.entity.db_models import KnowledgeDocument
    from tests.conftest import TestSessionLocal

    uploaded = {}

    class FakeMinIOClient:
        def upload_bytes(self, object_name, data, content_type="image/jpeg"):
            uploaded[object_name] = {"data": data, "content_type": content_type}
            return f"http://minio.test/{object_name}"

        def delete_object(self, object_name):
            uploaded.pop(object_name, None)

    monkeypatch.setattr(knowledge, "MinIOClient", FakeMinIOClient)
    monkeypatch.setattr(knowledge, "SessionLocal", TestSessionLocal)

    response = client.post(
        "/api/knowledge/documents/batch",
        headers=user_headers,
        files=[
            ("files", ("batch_a.md", b"# A\ncontent", "text/markdown")),
            ("files", ("batch_b.txt", b"B content", "text/plain")),
            ("files", ("bad.pdf", b"bad", "application/pdf")),
        ],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 2
    assert data["failed_count"] == 1
    assert len(uploaded) == 2

    db = TestSessionLocal()
    try:
        documents = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.file_path.like("knowledge/documents/%"))
            .all()
        )
        assert any(document.file_path.endswith("batch_a.md") for document in documents)
        assert all(document.status == "pending" for document in documents)
    finally:
        db.close()


def test_chat_stream_passes_admin_flag(client, user_headers, monkeypatch):
    """聊天 API 必须把当前用户管理员身份传给多 Agent 入口。"""
    from app.api import chat as chat_api
    from app.services import chat_history_service as chat_history_module
    from tests.conftest import TestSessionLocal

    captured = {}
    # 聊天历史服务使用独立 SessionLocal，测试中必须切换到 conftest 的 SQLite。
    monkeypatch.setattr(chat_history_module, "SessionLocal", TestSessionLocal)

    async def fake_chat_stream(**kwargs):
        captured.update(kwargs)
        yield {"type": "text_chunk", "content": "测试回复"}

    monkeypatch.setattr(chat_api, "multi_agent_chat_stream", fake_chat_stream)
    response = client.post(
        "/api/chat/stream",
        headers=user_headers,
        json={"message": "测试管理员上下文"},
    )

    assert response.status_code == 200
    assert captured["is_admin"] is False


def test_multi_agent_routes_attachment_directly_to_detection(monkeypatch):
    """带附件路径的请求是明确检测意图，不应依赖 Supervisor 猜路由。"""
    from app.agent import multi_agent as multi_agent_module

    captured = {}

    async def fail_supervisor(*_args, **_kwargs):
        raise AssertionError("attachment requests should skip supervisor")

    async def fake_detection_stream(**kwargs):
        captured.update(kwargs)
        yield {"type": "text_chunk", "content": "检测完成"}

    monkeypatch.setattr(multi_agent_module, "supervisor_route", fail_supervisor)
    monkeypatch.setattr(multi_agent_module.detection_agent, "chat_stream", fake_detection_stream)

    async def collect_events():
        return [
            event
            async for event in multi_agent_module.multi_agent_chat_stream(
                message="检测这个附件",
                image_path="/tmp/rsod_uploads/test.jpg",
                user_id=1,
                session_id="session_1",
            )
        ]

    events = asyncio.run(collect_events())

    assert events == [{"type": "text_chunk", "content": "检测完成"}]
    assert captured["image_path"] == "/tmp/rsod_uploads/test.jpg"


def test_multi_agent_routes_analysis_keywords_without_supervisor(monkeypatch):
    """检测统计和用户列表是明确分析意图，不应依赖 Supervisor 猜路由。"""
    from app.agent import multi_agent as multi_agent_module

    captured = []

    async def fail_supervisor(*_args, **_kwargs):
        raise AssertionError("analysis keyword requests should skip supervisor")

    async def fake_analysis_stream(**kwargs):
        captured.append(kwargs["message"])
        yield {"type": "text_chunk", "content": "分析完成"}

    monkeypatch.setattr(multi_agent_module, "supervisor_route", fail_supervisor)
    monkeypatch.setattr(multi_agent_module.analysis_agent, "chat_stream", fake_analysis_stream)

    async def collect_for(message):
        return [
            event
            async for event in multi_agent_module.multi_agent_chat_stream(
                message=message,
                user_id=1,
                session_id="session_1",
                is_admin=True,
            )
        ]

    assert asyncio.run(collect_for("我检测了多少次")) == [{"type": "text_chunk", "content": "分析完成"}]
    assert asyncio.run(collect_for("给出用户列表")) == [{"type": "text_chunk", "content": "分析完成"}]
    assert captured == ["我检测了多少次", "给出用户列表"]


def test_chat_stream_passes_superuser_as_admin(client, db_session, monkeypatch):
    """兼容旧超级管理员账号：is_superuser 也应进入工具层管理员上下文。"""
    from app.api import chat as chat_api
    from app.core.security import create_access_token
    from app.services import chat_history_service as chat_history_module
    from app.services.user_service import user_service
    from tests.conftest import TestSessionLocal

    user_service.ensure_builtin_roles(db_session)
    user = user_service.register(
        db_session,
        username="legacy_superuser",
        email="legacy_superuser@example.com",
        password="123456",
    )
    user.is_superuser = True
    db_session.commit()
    db_session.refresh(user)

    captured = {}
    monkeypatch.setattr(chat_history_module, "SessionLocal", TestSessionLocal)

    async def fake_chat_stream(**kwargs):
        captured.update(kwargs)
        yield {"type": "text_chunk", "content": "测试回复"}

    monkeypatch.setattr(chat_api, "multi_agent_chat_stream", fake_chat_stream)
    response = client.post(
        "/api/chat/stream",
        headers={"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"},
        json={"message": "给出用户列表"},
    )

    assert response.status_code == 200
    assert captured["is_admin"] is True
