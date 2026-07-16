"""
会话持久化与一小时活动记忆的回归测试
"""

import json
import os
import time

import pytest
from app.agent.detection_agent import detection_agent
from app.core.security import create_access_token
from app.entity.db_models import User
from app.services import chat_history_service as chat_history_module


def _history_service(monkeypatch):
    """让直接调用的服务复用 conftest 提供的隔离 SQLite 会话工厂。"""
    from tests.conftest import TestSessionLocal

    monkeypatch.setattr(chat_history_module, "SessionLocal", TestSessionLocal)
    return chat_history_module.chat_history_service


def _create_user(db_session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="test-password",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_persistent_session_keeps_order_and_isolates_users(db_session, monkeypatch):
    """数据库历史按写入顺序返回，其他用户不能读取同一会话。"""
    service = _history_service(monkeypatch)
    owner = _create_user(db_session, "memory_owner")
    other_user = _create_user(db_session, "memory_other")

    session = service.ensure_session(owner.id, "memory-session-order")
    service.append_message(owner.id, session["session_uuid"], "user", "第一条问题")
    service.append_message(owner.id, session["session_uuid"], "assistant", "第一条回答")
    service.append_message(owner.id, session["session_uuid"], "user", "第二条问题")

    history = service.get_session_history(owner.id, session["session_uuid"])
    assert [message["content"] for message in history["messages"]] == [
        "第一条问题",
        "第一条回答",
        "第二条问题",
    ]
    assert service.get_recent_messages(owner.id, session["session_uuid"], 2) == [
        {"role": "assistant", "content": "第一条回答"},
        {"role": "user", "content": "第二条问题"},
    ]
    assert service.get_session_history(other_user.id, session["session_uuid"]) is None
    renamed = service.rename_session(owner.id, session["session_uuid"], "自定义标题")
    assert renamed["title"] == "自定义标题"
    assert service.rename_session(other_user.id, session["session_uuid"], "越权标题") is None


def test_clear_and_delete_persistent_session(db_session, monkeypatch):
    """清空保留会话本身，删除会话则一并删除持久化消息。"""
    service = _history_service(monkeypatch)
    user = _create_user(db_session, "memory_cleanup")
    session = service.ensure_session(user.id, "memory-session-cleanup")
    service.append_message(user.id, session["session_uuid"], "user", "需要清空的消息")

    assert service.clear_session(user.id, session["session_uuid"])
    cleared = service.get_session_history(user.id, session["session_uuid"])
    assert cleared["messages"] == []
    assert cleared["session"]["message_count"] == 0

    assert service.delete_session(user.id, session["session_uuid"])
    assert service.get_session_history(user.id, session["session_uuid"]) is None


def test_stream_keeps_existing_events_and_returns_session_id(
    client, db_session, monkeypatch
):
    """新会话事件是附加事件，原有 text_chunk 和 DONE 协议保持不变。"""
    _history_service(monkeypatch)
    user = _create_user(db_session, "memory_stream")

    async def fake_chat_stream(**kwargs):
        assert kwargs["session_id"]
        yield {"type": "text_chunk", "content": "测试回复"}

    monkeypatch.setattr(detection_agent, "chat_stream", fake_chat_stream)
    response = client.post(
        "/api/chat/stream",
        headers={
            "Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"
        },
        json={"message": "创建会话"},
    )

    assert response.status_code == 200
    assert '"type": "session"' in response.text
    assert '"type": "text_chunk"' in response.text
    assert "data: [DONE]" in response.text


def test_create_session_endpoint(client, db_session, monkeypatch):
    """显式新建会话接口返回 201 和可用于后续流式对话的会话标识。"""
    _history_service(monkeypatch)
    user = _create_user(db_session, "memory_create")
    headers = {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}

    response = client.post("/api/chat/sessions", headers=headers)

    assert response.status_code == 201
    assert response.json()["session_uuid"]
    assert response.json()["message_count"] == 0
