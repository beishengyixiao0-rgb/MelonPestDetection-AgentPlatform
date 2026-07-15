"""Day 8 检测和 SSE 对话接口测试。

测试中替换实际 YOLO 推理，验证路由鉴权、参数传递、SSE 协议和会话持久化，
避免单元测试加载数百 MB 模型权重。
"""

from app.services.detection_service import detection_service


def auth_headers(client, username="day8_api_user"):
    """创建用户并获取 Day 8 接口需要的 Bearer Token。"""
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "123456"},
    )
    response = client.post("/api/auth/login", json={"username": username, "password": "123456"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_single_detection_requires_authentication(client):
    response = client.post("/api/detection/single", files={"file": ("leaf.jpg", b"not-used", "image/jpeg")})
    assert response.status_code == 401


def test_single_detection_uses_authenticated_user(client, monkeypatch):
    headers = auth_headers(client, "day8_single_user")
    captured = {}

    def fake_detect(image_path, conf, iou, scene_id, user_id):
        captured.update({"conf": conf, "iou": iou, "user_id": user_id})
        return {"task_id": 7, "total_images": 1, "total_objects": 2, "class_counts": {"leaf": 2}}

    monkeypatch.setattr(detection_service, "detect_single", fake_detect)
    response = client.post(
        "/api/detection/single",
        headers=headers,
        data={"conf": "0.35", "iou": "0.5"},
        files={"file": ("leaf.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json()["total_objects"] == 2
    assert captured["conf"] == 0.35
    assert captured["iou"] == 0.5
    assert captured["user_id"] > 0


def test_batch_rejects_unsupported_file(client):
    headers = auth_headers(client, "day8_type_user")
    response = client.post(
        "/api/detection/batch",
        headers=headers,
        files=[("files", ("readme.txt", b"invalid", "text/plain"))],
    )
    assert response.status_code == 400


def test_chat_stream_emits_done(client):
    headers = auth_headers(client, "day8_chat_user")
    response = client.post("/api/chat/stream", headers=headers, json={"message": "你好，介绍一下平台"})
    assert response.status_code == 200
    assert "data: [DONE]" in response.text
    assert '"type": "text_chunk"' in response.text


def test_chat_stream_passes_multiple_image_paths_to_agent(client, monkeypatch):
    """Agent SSE 通道应保留所有多图附件路径，而不是只传第一张。"""
    from app.agent.detection_agent import detection_agent
    from app.api.chat import UPLOAD_DIR

    headers = auth_headers(client, "day8_multi_image_user")
    captured = {}

    async def fake_chat_stream(**kwargs):
        captured.update(kwargs)
        yield {"type": "text_chunk", "content": "批量检测完成"}

    monkeypatch.setattr(detection_agent, "chat_stream", fake_chat_stream)
    image_paths = [f"{UPLOAD_DIR}/one.jpg", f"{UPLOAD_DIR}/two.jpg"]
    response = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"message": "检测这些图片", "image_paths": image_paths},
    )

    assert response.status_code == 200
    assert captured["image_paths"] == image_paths
    assert captured["image_path"] is None
