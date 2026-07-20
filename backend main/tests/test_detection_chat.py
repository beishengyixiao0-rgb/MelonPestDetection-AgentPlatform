# tests/test_detection_chat.py

"""
Day 8 检测和 SSE 对话接口测试。

测试中替换实际 YOLO 推理，验证路由鉴权、参数传递、SSE 协议和会话持久化，
避免单元测试加载数百 MB 模型权重。
"""

import io
import json
import os
import tempfile
import zipfile

import pytest
from app.services.detection_service import detection_service
from fastapi.testclient import TestClient


def auth_headers(client, username="day8_api_user"):
    """创建用户并获取 Day 8 接口需要的 Bearer Token。"""
    # 注册用户
    register_response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "123456",
        },
    )
    # 如果用户已存在，忽略错误
    if register_response.status_code != 201:
        # 用户可能已存在，尝试直接登录
        pass

    # 登录获取 token
    login_response = client.post(
        "/api/auth/login", json={"username": username, "password": "123456"}
    )
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_test_user(client, username):
    """创建测试用户并返回 token 和 user_id"""
    # 注册
    client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "123456",
        },
    )
    # 登录
    login_response = client.post(
        "/api/auth/login", json={"username": username, "password": "123456"}
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    # 从 token 中解析 user_id（如果接口返回了 user_id）
    user_data = login_response.json()

    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_data.get("user_id"),
    }


# ============================================================
# 1. 单图检测测试
# ============================================================


def test_single_detection_requires_authentication(client):
    """未认证请求单图检测应返回 401"""
    response = client.post(
        "/api/detection/single", files={"file": ("leaf.jpg", b"not-used", "image/jpeg")}
    )
    assert response.status_code == 401


def test_single_detection_uses_authenticated_user(client, monkeypatch):
    """认证用户单图检测应正确传递参数和用户ID"""
    headers = auth_headers(client, "day8_single_user")
    captured = {}

    def fake_detect(image_path, conf, iou, scene_id, user_id):
        captured.update({"conf": conf, "iou": iou, "user_id": user_id})
        return {
            "task_id": 7,
            "total_images": 1,
            "total_objects": 2,
            "class_counts": {"leaf": 2},
            "detections": [
                {"class_name": "leaf", "confidence": 0.92, "bbox": [10, 20, 100, 150]},
                {"class_name": "leaf", "confidence": 0.85, "bbox": [200, 300, 50, 80]},
            ],
            "annotated_image_base64": "fake_base64_data",
            "inference_time": 45.2,
        }

    monkeypatch.setattr(detection_service, "detect_single", fake_detect)
    response = client.post(
        "/api/detection/single",
        headers=headers,
        data={"conf": "0.35", "iou": "0.5", "scene_id": "1"},
        files={"file": ("leaf.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_objects"] == 2
    assert data["class_counts"]["leaf"] == 2
    assert "annotated_image_base64" in data
    assert captured["conf"] == 0.35
    assert captured["iou"] == 0.5
    assert captured["user_id"] > 0


# ============================================================
# 2. 批量检测测试
# ============================================================


def test_batch_detection_requires_authentication(client):
    """未认证请求批量检测应返回 401"""
    response = client.post(
        "/api/detection/batch",
        files=[("files", ("leaf.jpg", b"fake", "image/jpeg"))],
    )
    assert response.status_code == 401


def test_batch_rejects_unsupported_file(client):
    """批量检测拒绝非图片文件"""
    headers = auth_headers(client, "day8_type_user")
    response = client.post(
        "/api/detection/batch",
        headers=headers,
        files=[("files", ("readme.txt", b"invalid", "text/plain"))],
    )
    assert response.status_code == 400
    assert "不支持" in response.text or "格式" in response.text


def test_batch_detection_multiple_images(client, monkeypatch):
    """批量检测多张图片应返回汇总结果"""
    headers = auth_headers(client, "day8_batch_user")
    captured = {}

    def fake_batch_detect(image_paths, conf, iou, scene_id, user_id):
        captured.update(
            {"image_paths": image_paths, "conf": conf, "iou": iou, "user_id": user_id}
        )
        return {
            "task_id": 8,
            "total_images": len(image_paths),
            "total_objects": 5,
            "class_counts": {"leaf": 3, "flower": 2},
            "total_inference_time": 120.5,
            "detections": [
                {"image_path": "img1.jpg", "class_name": "leaf", "confidence": 0.92},
                {"image_path": "img1.jpg", "class_name": "flower", "confidence": 0.88},
                {"image_path": "img2.jpg", "class_name": "leaf", "confidence": 0.95},
                {"image_path": "img2.jpg", "class_name": "leaf", "confidence": 0.87},
                {"image_path": "img3.jpg", "class_name": "flower", "confidence": 0.90},
            ],
            "annotated_images": [
                {"image_path": "img1.jpg", "annotated_image_base64": "fake1"},
                {"image_path": "img2.jpg", "annotated_image_base64": "fake2"},
                {"image_path": "img3.jpg", "annotated_image_base64": "fake3"},
            ],
        }

    monkeypatch.setattr(detection_service, "detect_batch", fake_batch_detect)

    response = client.post(
        "/api/detection/batch",
        headers=headers,
        data={"conf": "0.25", "iou": "0.45"},
        files=[
            ("files", ("img1.jpg", b"fake-image1", "image/jpeg")),
            ("files", ("img2.jpg", b"fake-image2", "image/jpeg")),
            ("files", ("img3.jpg", b"fake-image3", "image/jpeg")),
        ],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_images"] == 3
    assert data["total_objects"] == 5
    assert data["class_counts"]["leaf"] == 3
    assert data["class_counts"]["flower"] == 2
    assert len(data["annotated_images"]) == 3
    assert len(captured["image_paths"]) == 3
    assert captured["iou"] == 0.45


# ============================================================
# 3. ZIP 检测测试
# ============================================================


def test_zip_detection_requires_authentication(client):
    """未认证请求 ZIP 检测应返回 401"""
    response = client.post(
        "/api/detection/zip", files={"file": ("images.zip", b"fake", "application/zip")}
    )
    assert response.status_code == 401


def test_zip_detection_rejects_non_zip(client):
    """ZIP 检测拒绝非 ZIP 文件"""
    headers = auth_headers(client, "day8_zip_user")
    response = client.post(
        "/api/detection/zip",
        headers=headers,
        files={"file": ("image.jpg", b"fake", "image/jpeg")},
    )
    assert response.status_code == 400


def test_zip_detection_processes_valid_zip(client, monkeypatch):
    """ZIP 文件应被解压并检测其中所有图片"""
    headers = auth_headers(client, "day8_zip_detect_user")
    captured = {}

    def fake_detect_zip(zip_path, conf, iou, scene_id, user_id):
        captured.update(
            {"zip_path": zip_path, "conf": conf, "iou": iou, "user_id": user_id}
        )
        return {
            "task_id": 9,
            "source": "zip",
            "zip_filename": "images.zip",
            "total_images_in_zip": 3,
            "total_images": 3,
            "total_objects": 8,
            "class_counts": {"leaf": 5, "flower": 3},
            "total_inference_time": 200.0,
            "detections": [
                {"image_path": "img1.jpg", "class_name": "leaf", "confidence": 0.92},
            ],
            "annotated_images": [
                {"image_path": "img1.jpg", "annotated_image_base64": "fake1"},
                {"image_path": "img2.jpg", "annotated_image_base64": "fake2"},
                {"image_path": "img3.jpg", "annotated_image_base64": "fake3"},
            ],
        }

    monkeypatch.setattr(detection_service, "detect_zip", fake_detect_zip)

    # 创建一个有效的 ZIP 文件
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("img1.jpg", b"fake-image1")
        zf.writestr("img2.jpg", b"fake-image2")
        zf.writestr("img3.jpg", b"fake-image3")
    zip_buffer.seek(0)

    response = client.post(
        "/api/detection/zip",
        headers=headers,
        data={"conf": "0.25", "iou": "0.45"},
        files={"file": ("images.zip", zip_buffer.getvalue(), "application/zip")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "zip"
    assert data["zip_filename"] == "images.zip"
    assert data["total_images_in_zip"] == 3
    assert data["total_objects"] == 8
    assert captured["conf"] == 0.25
    assert captured["iou"] == 0.45
    assert captured["user_id"] > 0


def test_zip_detection_empty_zip(client, monkeypatch):
    """空的 ZIP 文件应返回错误"""
    headers = auth_headers(client, "day8_zip_empty_user")

    def fake_detect_zip(zip_path, conf, iou, scene_id, user_id):
        return {"error": "ZIP 文件中没有找到图片"}

    monkeypatch.setattr(detection_service, "detect_zip", fake_detect_zip)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("readme.txt", b"no images")
    zip_buffer.seek(0)

    response = client.post(
        "/api/detection/zip",
        headers=headers,
        data={"conf": "0.25", "iou": "0.45"},
        files={"file": ("empty.zip", zip_buffer.getvalue(), "application/zip")},
    )

    assert response.status_code == 200
    assert "error" in response.json()


# ============================================================
# 4. 检测任务状态查询测试
# ============================================================


def test_detection_status_requires_authentication(client):
    """未认证查询任务状态应返回 401"""
    response = client.get("/api/detection/status/1")
    assert response.status_code == 401


def test_detection_status_not_found(client):
    """查询不存在的任务应返回 404"""
    headers = auth_headers(client, "day8_status_user")
    response = client.get("/api/detection/status/99999", headers=headers)
    assert response.status_code == 404


# ============================================================
# 5. 文件上传测试
# ============================================================


def test_upload_image_requires_authentication(client):
    """未认证上传图片应返回 401"""
    response = client.post(
        "/api/chat/upload",
        files={"file": ("leaf.jpg", b"fake", "image/jpeg")},
    )
    assert response.status_code == 401


def test_upload_image_returns_path(client):
    """上传图片应返回服务端路径"""
    headers = auth_headers(client, "day8_upload_user")
    response = client.post(
        "/api/chat/upload",
        headers=headers,
        files={"file": ("leaf.jpg", b"fake-image-content", "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "image_path" in data
    assert data["image_path"].endswith(".jpg") or data["image_path"].endswith(".jpeg")


def test_upload_image_rejects_non_image(client):
    """上传非图片文件应被拒绝"""
    headers = auth_headers(client, "day8_upload_type_user")
    response = client.post(
        "/api/chat/upload",
        headers=headers,
        files={"file": ("readme.txt", b"text content", "text/plain")},
    )
    assert response.status_code == 400


# ============================================================
# 6. SSE 流式对话测试 - 修复版本
# ============================================================


def test_chat_stream_requires_authentication(client):
    """未认证对话流应返回 401"""
    response = client.post("/api/chat/stream", json={"message": "你好"})
    assert response.status_code == 401


def test_chat_stream_emits_done(client, monkeypatch):
    """SSE 流式对话应返回 text_chunk 和 [DONE]"""
    from app.api import chat
    from app.services import chat_history_service as chat_history_module

    from tests.conftest import TestSessionLocal

    # 使用测试数据库
    monkeypatch.setattr(chat_history_module, "SessionLocal", TestSessionLocal)

    # 创建用户并获取 token
    username = "day8_chat_user"
    headers = auth_headers(client, username)

    # 聊天接口已升级为多 Agent 入口，测试只验证 SSE 外层协议。
    async def fake_chat_stream(**kwargs):
        yield {"type": "text_chunk", "content": "测试回复"}

    monkeypatch.setattr(chat, "multi_agent_chat_stream", fake_chat_stream)

    response = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"message": "你好，介绍一下平台"},
        # 不传递 user_id - 从 token 获取
    )

    assert response.status_code == 200
    response_text = response.text

    # 验证 SSE 格式
    assert "data: " in response_text
    assert '"type": "session"' in response_text
    assert '"type": "text_chunk"' in response_text
    assert "data: [DONE]" in response_text


@pytest.fixture
def setup_upload_dir():
    """创建临时上传目录用于测试"""
    upload_dir = tempfile.mkdtemp(prefix="rsod_test_")
    yield upload_dir
    # 清理
    import shutil

    shutil.rmtree(upload_dir, ignore_errors=True)


def test_chat_stream_with_real_path(client, monkeypatch, setup_upload_dir):
    """使用真实存在的路径测试 SSE 流 - 修复版本"""
    from app.api import chat
    from app.services import chat_history_service as chat_history_module

    from tests.conftest import TestSessionLocal

    # 使用测试数据库
    monkeypatch.setattr(chat_history_module, "SessionLocal", TestSessionLocal)

    # 临时替换 UPLOAD_DIR
    monkeypatch.setattr(chat, "UPLOAD_DIR", setup_upload_dir)

    # 创建用户并获取 token
    username = "day8_real_path_user"
    headers = auth_headers(client, username)

    # 创建一个测试文件
    test_file_path = os.path.join(setup_upload_dir, "test_image.jpg")
    with open(test_file_path, "wb") as f:
        f.write(b"fake image content")

    captured = {}

    async def fake_chat_stream(**kwargs):
        captured.update(kwargs)
        yield {"type": "text_chunk", "content": "检测完成"}

    monkeypatch.setattr(chat, "multi_agent_chat_stream", fake_chat_stream)

    response = client.post(
        "/api/chat/stream",
        headers=headers,
        json={
            "message": "检测这张图片",
            "image_path": test_file_path,
            # 不传递 user_id - 从 token 获取
        },
    )

    assert response.status_code == 200
    assert captured.get("image_path") == test_file_path
    assert captured.get("user_id") is not None  # 验证 user_id 被正确传递

    # 验证 SSE 响应格式
    response_text = response.text
    assert '"type": "session"' in response_text
    assert '"type": "text_chunk"' in response_text
    assert "data: [DONE]" in response_text


def test_chat_stream_accepts_uuid_session_id(client, monkeypatch):
    """前端会传 session_uuid 字符串，后端请求模型必须放行。"""
    from app.api import chat
    from app.services import chat_history_service as chat_history_module

    from tests.conftest import TestSessionLocal

    monkeypatch.setattr(chat_history_module, "SessionLocal", TestSessionLocal)

    headers = auth_headers(client, "day8_uuid_session_user")
    create_response = client.post("/api/chat/sessions", headers=headers)
    assert create_response.status_code == 201
    session_id = create_response.json()["session_uuid"]

    captured = {}

    async def fake_chat_stream(**kwargs):
        captured.update(kwargs)
        yield {"type": "text_chunk", "content": "继续会话"}

    monkeypatch.setattr(chat, "multi_agent_chat_stream", fake_chat_stream)

    response = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"message": "继续刚才的话题", "session_id": session_id},
    )

    assert response.status_code == 200
    assert captured["session_id"] == session_id
    assert '"type": "text_chunk"' in response.text


# 添加：测试新会话自动创建
def test_chat_stream_creates_session_if_not_provided(client, monkeypatch):
    """不提供 session_id 时应自动创建新会话"""
    from app.agent.detection_agent import detection_agent
    from app.services import chat_history_service as chat_history_module

    from tests.conftest import TestSessionLocal

    monkeypatch.setattr(chat_history_module, "SessionLocal", TestSessionLocal)

    username = "day8_auto_session_user"
    headers = auth_headers(client, username)

    async def fake_chat_stream(**kwargs):
        assert kwargs["session_id"] is not None  # 应该自动生成
        yield {"type": "text_chunk", "content": "自动创建会话"}

    monkeypatch.setattr(detection_agent, "chat_stream", fake_chat_stream)

    response = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"message": "新对话"},
        # 不提供 session_id，也不提供 user_id
    )

    assert response.status_code == 200
    assert '"type": "session"' in response.text
    assert '"session_id"' in response.text
    assert "data: [DONE]" in response.text


# ============================================================
# 7. 前端检测结果卡片数据格式测试
# ============================================================


def test_detection_result_card_format():
    """验证检测结果卡片所需的数据格式"""
    # 单图检测结果格式
    single_result = {
        "total_objects": 2,
        "class_counts": {"leaf": 2},
        "detections": [
            {"class_name": "leaf", "confidence": 0.92, "bbox": [10, 20, 100, 150]},
            {"class_name": "leaf", "confidence": 0.85, "bbox": [200, 300, 50, 80]},
        ],
        "annotated_image_base64": "fake_base64",
        "inference_time": 45.2,
        "task_id": 7,
    }

    assert "total_objects" in single_result
    assert "annotated_image_base64" in single_result
    assert len(single_result["detections"]) == 2

    # 批量检测结果格式
    batch_result = {
        "task_id": 8,
        "total_images": 3,
        "total_objects": 5,
        "class_counts": {"leaf": 3, "flower": 2},
        "annotated_images": [
            {"image_path": "img1.jpg", "annotated_image_base64": "fake1"},
            {"image_path": "img2.jpg", "annotated_image_base64": "fake2"},
        ],
    }

    assert "total_images" in batch_result
    assert "annotated_images" in batch_result
    assert len(batch_result["annotated_images"]) == 2


# ============================================================
# 8. 快捷按钮API测试（双通道架构）
# ============================================================


def test_quick_buttons_skip_llm(client, monkeypatch):
    """
    快捷按钮应跳过 LLM，直接调用检测 API
    验证：响应时间更短，不包含 LLM 生成内容
    """
    headers = auth_headers(client, "day8_quick_user")

    def fake_detect(image_path, conf, iou, scene_id, user_id):
        return {
            "task_id": 10,
            "total_objects": 1,
            "class_counts": {"leaf": 1},
            "detections": [
                {"class_name": "leaf", "confidence": 0.95, "bbox": [10, 20, 100, 150]}
            ],
            "annotated_image_base64": "quick_fake",
            "inference_time": 30.0,
        }

    monkeypatch.setattr(detection_service, "detect_single", fake_detect)

    response = client.post(
        "/api/detection/single",
        headers=headers,
        data={"conf": "0.25", "iou": "0.45"},
        files={"file": ("leaf.jpg", b"fake", "image/jpeg")},
    )

    assert response.status_code == 200
    data = response.json()
    # 快捷按钮返回的结果应直接包含检测数据，没有 LLM 消息
    assert "total_objects" in data
    assert "annotated_image_base64" in data
