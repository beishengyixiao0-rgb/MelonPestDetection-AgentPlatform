"""
训练模块接口测试 - 完整版

包含 Day06/Day07 所有训练接口的正向和负向测试

正向测试：
- 有效任务状态查询
- 有效任务指标查询
- results.csv 有效下载
- 模型下载有效
- 模型评估有效
- 模型导出有效

负向测试：
- 任务不存在（状态/指标/评估/导出/下载）
- 场景不存在
- 文件类型错误
- 新用户空列表
- 预测任务不存在
"""

import io
from datetime import datetime

import pytest
from PIL import Image

from app.entity.db_models import DetectionScene, TrainingMetric, TrainingTask, User
from app.training.training_service import TrainingService


def create_test_user(client, username, password="123456"):
    """创建测试用户并返回 Token"""
    client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
        },
    )
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_completed_training_task(db_session, username="training_api_user"):
    """
    创建一条模拟的 completed 训练任务。
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


class TestTrainingAPI:
    """训练管理模块测试 - 完整版（正向 + 负向）"""

    # ==================== Fixtures ====================

    @pytest.fixture
    def auth_headers(self, admin_headers):
        """训练和模型接口均为管理员专用。"""
        return admin_headers

    def _get_error_message(self, response):
        """从响应中安全提取错误消息"""
        try:
            data = response.json()
            if "detail" in data:
                return data["detail"]
            elif "message" in data:
                return data["message"]
            elif "msg" in data:
                return data["msg"]
            return str(data)
        except Exception:
            return ""

    # ==================== 1. 训练任务列表 ====================

    def test_list_training_tasks_success(self, client, auth_headers):
        """正向：获取训练任务列表"""
        response = client.get("/api/training/tasks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_admin_lists_tasks_created_by_other_users(self, client, db_session, admin_headers):
        """平台模型归管理员统一管理，管理员可查看其他账户归属的历史任务。"""
        create_test_user(client, "imported_task_owner")
        task = create_completed_training_task(db_session, "imported_task_owner")

        response = client.get("/api/training/tasks", headers=admin_headers)
        assert response.status_code == 200
        assert task.id in [item["id"] for item in response.json()["items"]]

    def test_training_requires_admin(self, client, user_headers):
        """普通用户不具备模型和训练管理权限。"""
        response = client.get("/api/training/tasks", headers=user_headers)
        assert response.status_code == 403

    # ==================== 2. 训练状态 ====================

    def test_get_training_status_success(self, client, db_session, admin_headers):
        """正向：有效 task_id 查询训练状态"""
        create_test_user(client, "status_success_user")
        headers = admin_headers
        task = create_completed_training_task(db_session, "status_success_user")

        response = client.get(f"/api/training/status/{task.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "task" in data
        assert data["task"]["id"] == task.id
        assert data["task"]["status"] == "completed"
        assert data["latest_metric"]["map50"] == 0.9

    def test_get_training_status_not_found(self, client, auth_headers):
        """负向：查询不存在的任务 → 404"""
        response = client.get("/api/training/status/99999", headers=auth_headers)
        assert response.status_code == 404

    # ==================== 3. 训练指标 ====================

    def test_get_training_metrics_success(self, client, db_session, admin_headers):
        """正向：有效 task_id 获取所有 epoch 指标"""
        create_test_user(client, "metrics_success_user")
        headers = admin_headers
        task = create_completed_training_task(db_session, "metrics_success_user")

        response = client.get(f"/api/training/metrics/{task.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task.id
        assert data["total"] == 2
        assert data["metrics"][1]["map50_95"] == 0.6

    def test_get_training_metrics_not_found(self, client, auth_headers):
        """负向：查询不存在的任务指标 → 空列表"""
        response = client.get("/api/training/metrics/99999", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["metrics"] == []

    # ==================== 4. 停止训练 ====================

    def test_stop_completed_task(self, client, db_session, admin_headers):
        """负向：停止已完成的训练任务 → 400"""
        create_test_user(client, "stop_completed_user")
        headers = admin_headers
        task = create_completed_training_task(db_session, "stop_completed_user")

        response = client.post(f"/api/training/stop/{task.id}", headers=headers)
        assert response.status_code == 400
        error_msg = self._get_error_message(response)
        assert "无法停止" in error_msg or "completed" in error_msg

    def test_stop_training_not_found(self, client, auth_headers):
        """负向：停止不存在的训练任务 → 400"""
        response = client.post("/api/training/stop/99999", headers=auth_headers)
        assert response.status_code == 400
        error_msg = self._get_error_message(response)
        assert "不存在" in error_msg or "任务" in error_msg

    # ==================== 5. 获取 results.csv ====================

    def test_get_results_csv_success(self, client, db_session, monkeypatch, tmp_path, admin_headers):
        """正向：有效 task_uuid 下载 results.csv"""
        create_test_user(client, "results_success_user")
        headers = admin_headers
        task = create_completed_training_task(db_session, "results_success_user")

        results_file = tmp_path / "results.csv"
        results_file.write_text(
            "epoch,train/box_loss,metrics/mAP50(B),metrics/mAP50-95(B)\n"
            "0,1.0,0.7,0.4\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            TrainingService,
            "get_task_results_path",
            staticmethod(lambda task_uuid: results_file),
        )

        response = client.get(
            f"/api/training/results/{task.task_uuid}",
            headers=headers,
        )
        assert response.status_code == 200
        assert "train/box_loss" in response.text

    def test_get_results_csv_not_found(self, client, auth_headers):
        """负向：无效 task_uuid 下载 results.csv → 404"""
        response = client.get(
            "/api/training/results/nonexistent_uuid_12345",
            headers=auth_headers,
        )
        assert response.status_code == 404

    # ==================== 6. 模型评估 ====================

    def test_validate_model_success(self, client, db_session, monkeypatch, tmp_path, admin_headers):
        """正向：对已完成训练的模型执行评估"""
        create_test_user(client, "validate_success_user")
        headers = admin_headers
        task = create_completed_training_task(db_session, "validate_success_user")

        def mock_validate_model(db, task_id, split="val", conf=0.001, iou=0.6):
            return {
                "task_id": task_id,
                "task_uuid": "mock_uuid",
                "split": split,
                "overall": {
                    "precision": 0.95,
                    "recall": 0.93,
                    "map50": 0.92,
                    "map50_95": 0.68,
                },
                "per_class": {"leaf": {"ap50": 0.92, "ap50_95": 0.68}},
            }

        monkeypatch.setattr(
            TrainingService,
            "validate_model",
            staticmethod(mock_validate_model),
        )

        response = client.post(
            f"/api/training/validate/{task.id}",
            json={"split": "val", "conf": 0.001, "iou": 0.6},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "overall" in data
        assert data["overall"]["map50"] == 0.92
        assert data["overall"]["precision"] == 0.95

    def test_validate_task_not_found(self, client, auth_headers):
        """负向：评估不存在的训练任务 → 400"""
        response = client.post(
            "/api/training/validate/99999",
            json={"split": "val"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        error_msg = self._get_error_message(response)
        assert error_msg and ("不存在" in error_msg or "任务" in error_msg)

    # ==================== 7. 模型导出 ====================

    def test_export_model_success(self, client, db_session, monkeypatch, tmp_path, admin_headers):
        """正向：导出训练好的模型为正式版本"""
        create_test_user(client, "export_success_user")
        headers = admin_headers
        task = create_completed_training_task(db_session, "export_success_user")

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

    def test_export_not_completed_task(self, client, db_session, admin_headers):
        """负向：导出未完成的训练任务 → 400"""
        create_test_user(client, "export_not_completed_user")
        headers = admin_headers
        
        user = db_session.query(User).filter(User.username == "export_not_completed_user").first()
        scene = DetectionScene(
            name="export_not_completed_scene",
            display_name="未完成场景",
            category="test",
            class_names=["test"],
            is_active=True,
            created_by=user.id,
        )
        db_session.add(scene)
        db_session.commit()
        db_session.refresh(scene)

        task = TrainingTask(
            user_id=user.id,
            scene_id=scene.id,
            task_uuid="not_completed_001",
            status="pending",
            model_name="test_model",
            epochs=10,
            current_epoch=5,
            progress=50,
            img_size=640,
            batch_size=16,
            device="cpu",
            optimizer="SGD",
            lr0=0.01,
            dataset_path="datasets/test",
            data_yaml="datasets/test/data.yaml",
            started_at=datetime.now(),
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        response = client.post(
            f"/api/training/export/{task.id}",
            headers=headers,
            json={"description": "测试"},
        )
        assert response.status_code == 400
        error_msg = self._get_error_message(response)
        assert "已完成" in error_msg or "pending" in error_msg

    def test_export_task_not_found(self, client, auth_headers):
        """负向：导出不存在的训练任务 → 400"""
        response = client.post(
            "/api/training/export/99999",
            json={"description": "测试导出", "set_default": True},
            headers=auth_headers,
        )
        assert response.status_code == 400
        error_msg = self._get_error_message(response)
        assert error_msg and ("不存在" in error_msg or "任务" in error_msg)

    # ==================== 8. 下载模型 ====================

    def test_download_model_success(self, client, db_session, monkeypatch, tmp_path, admin_headers):
        """正向：下载模型权重文件（.pt）"""
        create_test_user(client, "download_success_user")
        headers = admin_headers
        task = create_completed_training_task(db_session, "download_success_user")

        weight_file = tmp_path / "best.pt"
        weight_file.write_bytes(b"fake-weights")

        monkeypatch.setattr(
            TrainingService,
            "get_task_weights_path",
            staticmethod(lambda task_uuid: weight_file),
        )

        response = client.get(
            f"/api/training/download/{task.id}",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.content == b"fake-weights"

    def test_download_model_not_found(self, client, auth_headers):
        """负向：下载不存在的训练任务 → 404"""
        response = client.get("/api/training/download/99999", headers=auth_headers)
        assert response.status_code == 404

    # ==================== 9. 启动训练 ====================

    def test_start_training_scene_not_found(self, client, auth_headers):
        """负向：场景不存在时启动训练 → 404"""
        response = client.post(
            "/api/training/start",
            json={
                "scene_id": 99999,
                "model_name": "yolov11n",
                "epochs": 10,
                "batch_size": 8,
                "img_size": 640,
                "device": "cpu",
                "optimizer": "SGD",
                "lr0": 0.01,
            },
            headers=auth_headers,
        )
        assert response.status_code == 404
        error_msg = self._get_error_message(response)
        assert error_msg and "检测场景不存在" in error_msg

    # ==================== 10. 测试图验证 ====================

    def test_predict_invalid_file_format(self, client, auth_headers):
        """负向：上传非图片格式文件 → 400"""
        txt_bytes = io.BytesIO(b"this is not an image")

        response = client.post(
            "/api/training/predict",
            files={"file": ("test.txt", txt_bytes, "text/plain")},
            data={"task_id": 1, "conf": 0.25, "iou": 0.45},
            headers=auth_headers,
        )
        assert response.status_code == 400
        error_msg = self._get_error_message(response)
        assert error_msg and ("不支持" in error_msg or "格式" in error_msg)

    def test_predict_task_not_found(self, client, auth_headers):
        """负向：使用不存在的 task_id 预测 → 404"""
        img = Image.new("RGB", (640, 640), color=0xFF0000)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        response = client.post(
            "/api/training/predict",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"task_id": 99999, "conf": 0.25, "iou": 0.45},
            headers=auth_headers,
        )
        assert response.status_code == 404
        error_msg = self._get_error_message(response)
        assert error_msg and ("不存在" in error_msg or "任务" in error_msg)
