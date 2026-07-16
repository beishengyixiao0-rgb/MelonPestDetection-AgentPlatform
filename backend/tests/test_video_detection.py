"""视频检测接口测试。

测试视频上传、进度查询等路由逻辑，
使用 monkeypatch 替换实际 YOLO 推理，避免加载模型权重。
同时提供使用真实视频文件的集成测试。
"""

import os
import threading
import time
from pathlib import Path

import app.api.detection as detection_api
import pytest
from app.entity.db_models import DetectionScene, DetectionTask
from app.services.detection_service import detection_service
from app.storage.redis_client import redis_client

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def video_scene(db_session):
    scene = db_session.query(DetectionScene).filter_by(name="video_test_scene").first()
    if not scene:
        scene = DetectionScene(
            name="video_test_scene",
            display_name="视频检测测试场景",
            category="test",
            class_names=["object"],
            is_active=True,
        )
        db_session.add(scene)
        db_session.commit()
        db_session.refresh(scene)
    return scene


def auth_headers(client, username="video_test_user"):
    """创建用户并获取 Bearer Token。"""
    client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "123456",
        },
    )
    response = client.post(
        "/api/auth/login", json={"username": username, "password": "123456"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ── 鉴权测试 ─────────────────────────────────────────────────


def test_video_upload_requires_authentication(client):
    """未认证用户无法上传视频。"""
    response = client.post(
        "/api/detection/video",
        files={"file": ("test.mp4", b"not-used", "video/mp4")},
    )
    assert response.status_code == 401


def test_video_status_requires_authentication(client):
    """未认证用户无法查询视频检测进度。"""
    response = client.get("/api/detection/video/status/1")
    assert response.status_code == 401


# ── 文件格式校验 ─────────────────────────────────────────────


def test_video_rejects_unsupported_format(client):
    """不支持的视频格式应返回 400。"""
    headers = auth_headers(client, "video_format_user")
    response = client.post(
        "/api/detection/video",
        headers=headers,
        files={"file": ("test.txt", b"not a video", "text/plain")},
    )
    assert response.status_code == 400
    assert "不支持" in response.json()["error"]


def test_video_accepts_mp4_for_normal_user(
    client, user_headers, video_scene, monkeypatch
):
    """普通用户可上传视频进行检测。"""

    def fake_detect(
        video_path, conf, iou, frame_sample_rate, max_frames, scene_id, user_id, task_id
    ):
        return {
            "task_id": task_id,
            "total_frames": 100,
            "processed_frames": 10,
            "total_objects": 0,
        }

    monkeypatch.setattr(detection_service, "detect_video", fake_detect)
    response = client.post(
        "/api/detection/video",
        headers=user_headers,
        files={"file": ("test.mp4", b"fake-video", "video/mp4")},
        data={
            "conf": 0.25,
            "frame_sample_rate": 5,
            "max_frames": 50,
            "scene_id": video_scene.id,
        },
    )
    assert response.status_code == 200
    assert "task_id" in response.json()


# ── 参数传递测试 ─────────────────────────────────────────────


def test_video_detection_passes_parameters(client, video_scene, monkeypatch):
    """验证参数正确传递给检测服务。"""
    headers = auth_headers(client, "video_params_user")
    captured = {}
    completed = threading.Event()

    def fake_detect(
        video_path, conf, iou, frame_sample_rate, max_frames, scene_id, user_id, task_id
    ):
        captured.update(
            {
                "conf": conf,
                "iou": iou,
                "frame_sample_rate": frame_sample_rate,
                "max_frames": max_frames,
                "scene_id": scene_id,
                "user_id": user_id,
                "task_id": task_id,
            }
        )
        completed.set()
        return {
            "task_id": task_id,
            "total_frames": 100,
            "processed_frames": 10,
            "total_objects": 0,
        }

    monkeypatch.setattr(detection_service, "detect_video", fake_detect)
    response = client.post(
        "/api/detection/video",
        headers=headers,
        files={"file": ("test.mp4", b"fake-video", "video/mp4")},
        data={
            "conf": 0.35,
            "iou": 0.5,
            "frame_sample_rate": 10,
            "max_frames": 30,
            "scene_id": video_scene.id,
        },
    )
    assert response.status_code == 200
    assert completed.wait(1)
    assert captured["conf"] == 0.35
    assert captured["iou"] == 0.5
    assert captured["frame_sample_rate"] == 10
    assert captured["max_frames"] == 30
    assert captured["scene_id"] == video_scene.id
    assert captured["user_id"] > 0


# ── 进度查询测试 ─────────────────────────────────────────────


def test_video_status_not_found(client):
    """查询不存在的任务应返回 404。"""
    headers = auth_headers(client, "video_status_user")
    response = client.get("/api/detection/video/status/99999", headers=headers)
    assert response.status_code == 404


def test_video_status_rejects_other_users_task(
    client, db_session, admin_user, user_headers, video_scene
):
    """检测任务及 Redis 中的结果只能由创建者读取。"""
    task = DetectionTask(
        user_id=admin_user.id,
        scene_id=video_scene.id,
        task_type="video",
        status="processing",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    redis_client.set_json(
        f"video_task:{task.id}",
        {"status": "completed", "progress": 100, "result": {"secret": "owner-only"}},
        expire=60,
    )

    response = client.get(
        f"/api/detection/video/status/{task.id}", headers=user_headers
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "data", [{"frame_sample_rate": 0}, {"max_frames": 0}, {"conf": 1.1}]
)
def test_video_rejects_invalid_parameters(client, user_headers, video_scene, data):
    response = client.post(
        "/api/detection/video",
        headers=user_headers,
        files={"file": ("test.mp4", b"fake-video", "video/mp4")},
        data={"scene_id": video_scene.id, **data},
    )
    assert response.status_code == 400


def test_video_rejects_oversized_upload(client, user_headers, video_scene, monkeypatch):
    monkeypatch.setattr(detection_api, "MAX_VIDEO_SIZE_BYTES", 10)
    response = client.post(
        "/api/detection/video",
        headers=user_headers,
        files={"file": ("test.mp4", b"01234567890", "video/mp4")},
        data={"scene_id": video_scene.id},
    )
    assert response.status_code == 400


# ── 真实视频文件集成测试 ─────────────────────────────────────
# 需要将真实视频文件放到 tests/fixtures/ 目录下


def _has_test_video():
    """检查是否存在测试视频文件。"""
    if not os.path.isdir(FIXTURES_DIR):
        return None

    video_extensions = (".mp4", ".avi", ".mov", ".mkv")
    for name in os.listdir(FIXTURES_DIR):
        if name.lower().endswith(video_extensions):
            video_path = os.path.join(FIXTURES_DIR, name)
            if os.path.isfile(video_path):
                return video_path
    return None


@pytest.mark.skipif(not _has_test_video(), reason="tests/fixtures/ 目录下没有视频文件")
def test_video_upload_with_real_file(client, video_scene, monkeypatch):
    """使用真实视频文件测试上传流程。"""
    video_path = _has_test_video()
    # 确保 video_path 是字符串，不是 None
    assert video_path is not None, "Video path should not be None"

    headers = auth_headers(client, "video_real_user")

    def fake_detect(
        video_path, conf, iou, frame_sample_rate, max_frames, scene_id, user_id, task_id
    ):
        return {
            "task_id": task_id,
            "total_frames": 150,
            "processed_frames": 10,
            "fps": 30.0,
            "duration_seconds": 5.0,
            "total_objects": 3,
            "class_counts": {"apple": 3},
            "key_frames": [],
            "total_inference_time": 500.0,
        }

    monkeypatch.setattr(detection_service, "detect_video", fake_detect)

    # 使用字符串路径
    video_filename = os.path.basename(str(video_path))

    with open(str(video_path), "rb") as f:
        # 读取文件内容到内存，避免文件句柄问题
        file_content = f.read()

    response = client.post(
        "/api/detection/video",
        headers=headers,
        files={"file": (video_filename, file_content, "video/mp4")},
        data={
            "conf": 0.25,
            "frame_sample_rate": 5,
            "max_frames": 50,
            "scene_id": video_scene.id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "processing"
    assert data["filename"] == video_filename


@pytest.mark.skipif(not _has_test_video(), reason="tests/fixtures/ 目录下没有视频文件")
def test_video_detection_full_flow(client, video_scene, monkeypatch):
    """使用真实视频文件测试完整流程：上传 → 等待 → 查询结果。"""
    video_path = _has_test_video()
    # 确保 video_path 是字符串，不是 None
    assert video_path is not None, "Video path should not be None"

    headers = auth_headers(client, "video_flow_user")

    def fake_detect(
        video_path, conf, iou, frame_sample_rate, max_frames, scene_id, user_id, task_id
    ):
        time.sleep(0.5)  # 模拟处理时间
        return {
            "task_id": task_id,
            "total_frames": 150,
            "processed_frames": 10,
            "fps": 30.0,
            "duration_seconds": 5.0,
            "total_objects": 3,
            "class_counts": {"apple": 3},
            "key_frames": [],
            "total_inference_time": 500.0,
        }

    monkeypatch.setattr(detection_service, "detect_video", fake_detect)

    # 1. 上传视频
    video_filename = os.path.basename(str(video_path))

    with open(str(video_path), "rb") as f:
        file_content = f.read()

    upload_resp = client.post(
        "/api/detection/video",
        headers=headers,
        files={"file": (video_filename, file_content, "video/mp4")},
        data={
            "conf": 0.25,
            "frame_sample_rate": 5,
            "max_frames": 50,
            "scene_id": video_scene.id,
        },
    )
    assert upload_resp.status_code == 200
    task_id = upload_resp.json()["task_id"]

    # 2. 等待处理完成
    time.sleep(2)

    # 3. 查询结果
    status_resp = client.get(f"/api/detection/video/status/{task_id}", headers=headers)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["task_id"] == task_id
