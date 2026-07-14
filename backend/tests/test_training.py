"""
训练模块接口测试。

这些测试验证 Day06/Day07 的训练接口是否能围绕“已导入的 completed 任务”
正常工作。项目正式使用 `backend/runs/train/task_001/weights/best.pt`，
但单元测试不直接加载真实 YOLO 模型，原因是：
- 加载 ultralytics/torch 会明显降低测试速度；
- Windows 本地 torch DLL 状态容易影响测试稳定性；
- 单元测试只需要验证 API 路由、鉴权、数据库读取和文件路径逻辑。

真实图片预测请使用 `backend/tools/manual_predict_verify.ps1` 做手工验证。
"""

from datetime import datetime

from app.entity.db_models import DetectionScene, TrainingMetric, TrainingTask, User
from app.training.training_service import TrainingService


def auth_headers(client, username="training_api_user"):
    """创建测试用户并返回 Bearer Token 请求头。"""
    client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "123456",
        },
    )
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "123456"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_completed_training_task(db_session, username="training_api_user"):
    """
    创建一条模拟的 completed 训练任务。

    真实项目中这类记录由 `tools/import_existing_model.py` 创建；
    测试中直接写入 SQLite 测试库，避免依赖本机 PostgreSQL 和真实模型文件。
    """
    user = db_session.query(User).filter(User.username == username).first()
    scene = DetectionScene(
        name=f"plant_disease_{username}",
        display_name="植物病害检测",
        category="agriculture",
        class_names=["leaf"],
        is_active=True,
        created_by=user.id,
    )
    db_session.add(scene)
    db_session.commit()
    db_session.refresh(scene)

    task = TrainingTask(
        user_id=user.id,
        scene_id=scene.id,
        task_uuid=f"{username}_001",
        status="completed",
        model_name="plant_disease_best",
        epochs=2,
        current_epoch=2,
        progress=100,
        img_size=640,
        batch_size=16,
        device="cpu",
        optimizer="SGD",
        lr0=0.01,
        dataset_path="datasets/plant_disease",
        data_yaml="datasets/plant_disease/data.yaml",
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    db_session.add_all(
        [
            TrainingMetric(
                task_id=task.id,
                epoch=1,
                box_loss=1.0,
                cls_loss=2.0,
                dfl_loss=3.0,
                precision=0.5,
                recall=0.6,
                map50=0.7,
                map50_95=0.4,
                lr=0.01,
            ),
            TrainingMetric(
                task_id=task.id,
                epoch=2,
                box_loss=0.8,
                cls_loss=1.5,
                dfl_loss=2.5,
                precision=0.7,
                recall=0.8,
                map50=0.9,
                map50_95=0.6,
                lr=0.001,
            ),
        ]
    )
    db_session.commit()
    return task


def test_training_task_list_status_metrics_and_stop(client, db_session):
    """列表、状态、曲线指标和 completed 任务停止边界。"""
    headers = auth_headers(client, "training_list_user")
    task = create_completed_training_task(db_session, "training_list_user")

    list_response = client.get("/api/training/tasks", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1

    status_response = client.get(f"/api/training/status/{task.id}", headers=headers)
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["task"]["status"] == "completed"
    assert status_data["latest_metric"]["map50"] == 0.9

    metrics_response = client.get(f"/api/training/metrics/{task.id}", headers=headers)
    assert metrics_response.status_code == 200
    metrics_data = metrics_response.json()
    assert metrics_data["total"] == 2
    assert metrics_data["metrics"][1]["map50_95"] == 0.6

    stop_response = client.post(f"/api/training/stop/{task.id}", headers=headers)
    assert stop_response.status_code == 400
    assert "无法停止" in stop_response.json()["message"]


def test_training_results_and_download(client, db_session, monkeypatch, tmp_path):
    """
    下载 results.csv 和 best.pt。

    这里用 monkeypatch 把 TrainingService 的文件路径指向临时目录，
    验证 API 下载逻辑，不读取仓库内真实模型文件。
    """
    headers = auth_headers(client, "training_file_user")
    task = create_completed_training_task(db_session, "training_file_user")

    results_file = tmp_path / "results.csv"
    results_file.write_text(
        "epoch,train/box_loss,metrics/mAP50(B),metrics/mAP50-95(B)\n"
        "0,1.0,0.7,0.4\n",
        encoding="utf-8",
    )
    weight_file = tmp_path / "best.pt"
    weight_file.write_bytes(b"fake-weights")

    monkeypatch.setattr(
        TrainingService,
        "get_task_results_path",
        staticmethod(lambda task_uuid: results_file),
    )
    monkeypatch.setattr(
        TrainingService,
        "get_task_weights_path",
        staticmethod(lambda task_uuid: weight_file),
    )

    results_response = client.get(
        f"/api/training/results/{task.task_uuid}",
        headers=headers,
    )
    assert results_response.status_code == 200
    assert "train/box_loss" in results_response.text

    download_response = client.get(
        f"/api/training/download/{task.id}",
        headers=headers,
    )
    assert download_response.status_code == 200
    assert download_response.content == b"fake-weights"


def test_training_export_uses_existing_artifacts(
    client,
    db_session,
    monkeypatch,
    tmp_path,
):
    """
    导出模型版本。

    该测试验证 `/api/training/export/{task_id}` 能从已有 best.pt 和 results.csv
    生成模型版本记录与导出文件；不调用 MinIO，也不运行 YOLO 评估。
    """
    headers = auth_headers(client, "training_export_user")
    task = create_completed_training_task(db_session, "training_export_user")

    results_file = tmp_path / "results.csv"
    results_file.write_text(
        "epoch,metrics/precision(B),metrics/recall(B),"
        "metrics/mAP50(B),metrics/mAP50-95(B)\n"
        "0,0.8,0.7,0.9,0.6\n",
        encoding="utf-8",
    )
    weight_file = tmp_path / "best.pt"
    weight_file.write_bytes(b"fake-weights")

    monkeypatch.setattr(TrainingService, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(
        TrainingService,
        "get_task_results_path",
        staticmethod(lambda task_uuid: results_file),
    )
    monkeypatch.setattr(
        TrainingService,
        "get_task_weights_path",
        staticmethod(lambda task_uuid: weight_file),
    )

    response = client.post(
        f"/api/training/export/{task.id}",
        headers=headers,
        json={
            "version": "vtest.0.0",
            "description": "测试导出",
            "set_default": True,
            "upload_minio": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "vtest.0.0"
    assert data["evaluation"]["map50"] == 0.9
    exported_model = tmp_path / "models" / data["model_path"].split("/")[-2] / "best.pt"
    assert exported_model.exists()


def test_training_start_missing_scene_and_predict_file_type(client):
    """
    校验两个轻量边界：
    - `/start` 在场景不存在时返回 404，不启动本地训练；
    - `/predict` 对非图片文件返回 400，不加载 ultralytics/torch。
    """
    headers = auth_headers(client, "training_validation_user")

    start_response = client.post(
        "/api/training/start",
        headers=headers,
        json={
            "scene_id": 999999,
            "model_name": "yolov11n",
            "epochs": 10,
            "img_size": 640,
            "batch_size": 4,
            "device": "cpu",
            "optimizer": "SGD",
            "lr0": 0.01,
        },
    )
    assert start_response.status_code == 404

    predict_response = client.post(
        "/api/training/predict",
        headers=headers,
        data={"task_id": "1", "conf": "0.25", "iou": "0.45"},
        files={"file": ("bad.txt", b"not an image", "text/plain")},
    )
    assert predict_response.status_code == 400
