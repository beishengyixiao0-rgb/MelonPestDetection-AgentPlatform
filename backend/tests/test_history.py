"""
检测历史记录 API 测试 - 精简版（只测试API行为，不依赖数据创建）
"""

import pytest
from app.core.security import create_access_token
from app.entity.db_models import User


def _create_user(db_session, username: str) -> User:
    import time

    unique_suffix = int(time.time() * 1000) % 100000
    user = User(
        username=username,
        email=f"{username}_{unique_suffix}@example.com",
        hashed_password="test-password",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _get_user_id(user: User) -> int:
    user_id = getattr(user, "id")
    if user_id is None:
        raise ValueError("User ID is None")
    return user_id


def _get_token(user_id: int) -> str:
    return create_access_token({"sub": str(user_id)})


def _get_headers(user_id: int) -> dict:
    return {"Authorization": f"Bearer {_get_token(user_id)}"}


# ============================================================
# 认证拦截测试
# ============================================================


def test_list_tasks_authentication_required(client):
    """GET /api/history/tasks 需要认证。"""
    response = client.get("/api/history/tasks")
    assert response.status_code == 401


def test_detail_authentication_required(client):
    """GET /api/history/tasks/{id} 需要认证。"""
    response = client.get("/api/history/tasks/1")
    assert response.status_code == 401


def test_delete_authentication_required(client):
    """DELETE /api/history/tasks/{id} 需要认证。"""
    response = client.delete("/api/history/tasks/1")
    assert response.status_code == 401


def test_summary_authentication_required(client):
    """GET /api/history/summary 需要认证。"""
    response = client.get("/api/history/summary")
    assert response.status_code == 401


def test_scenes_authentication_required(client):
    """GET /api/history/scenes 需要认证。"""
    response = client.get("/api/history/scenes")
    assert response.status_code == 401


# ============================================================
# 空数据测试（新用户没有任何数据）
# ============================================================


def test_list_tasks_empty(client, db_session):
    """新用户任务列表为空。"""
    user = _create_user(db_session, "history_empty_user")
    user_id = _get_user_id(user)
    headers = _get_headers(user_id)

    response = client.get("/api/history/tasks", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_pages"] == 0


def test_summary_empty(client, db_session):
    """新用户统计为空。"""
    user = _create_user(db_session, "history_summary_empty_user")
    user_id = _get_user_id(user)
    headers = _get_headers(user_id)

    response = client.get("/api/history/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_tasks"] == 0
    assert data["today_tasks"] == 0
    assert data["status_counts"]["completed"] == 0
    assert data["status_counts"]["processing"] == 0
    assert data["status_counts"]["failed"] == 0
    assert data["status_counts"]["pending"] == 0


# ============================================================
# 无效ID测试（返回404）
# ============================================================


def test_detail_invalid(client, db_session):
    """无效任务ID返回404。"""
    user = _create_user(db_session, "history_detail_invalid_user")
    user_id = _get_user_id(user)
    headers = _get_headers(user_id)

    response = client.get("/api/history/tasks/99999", headers=headers)
    assert response.status_code == 404
    assert "任务不存在" in response.json()["error"]


def test_delete_invalid(client, db_session):
    """删除不存在的任务返回404。"""
    user = _create_user(db_session, "history_delete_invalid_user")
    user_id = _get_user_id(user)
    headers = _get_headers(user_id)

    response = client.delete("/api/history/tasks/99999", headers=headers)
    assert response.status_code == 404
    assert "任务不存在" in response.json()["error"]


# ============================================================
# 场景列表测试
# ============================================================


def test_scenes_basic(client, db_session):
    """获取场景列表。"""
    user = _create_user(db_session, "history_scenes_user")
    user_id = _get_user_id(user)
    headers = _get_headers(user_id)

    response = client.get("/api/history/scenes", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "scenes" in data
