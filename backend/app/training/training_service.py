"""
模型训练服务

职责：
- 封装 YOLOv11 训练启动、监控、停止逻辑
- 支持本地 CPU 训练和 GPU 训练
- 训练在后台线程中执行，不阻塞 API 请求
- 实时解析训练指标并写入数据库
- 解析 Ultralytics 生成的 results.csv 获取训练日志
"""

import csv
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict  # 移除了未使用的 List 和 Optional

from app.config.settings import settings
from app.core.logger import get_logger
from app.database.session import SessionLocal
from app.entity.db_models import TrainingMetric, TrainingTask

logger = get_logger(__name__)

# 全局变量：存储正在运行的任务模型实例，用于中途停止
_running_tasks: Dict[str, Any] = {}
_running_lock = threading.Lock()


class TrainingService:
    """YOLOv11 模型训练服务"""

    @staticmethod
    def start_training(
        db, user_id: int, scene_id: int, config: Dict[str, Any]
    ) -> TrainingTask:
        """
        创建并启动模型训练任务

        Args:
            db: 数据库会话
            user_id: 用户 ID
            scene_id: 场景 ID
            config: 训练配置字典

        Returns:
            训练任务数据库记录
        """
        task_uuid = str(uuid.uuid4()).replace("-", "")[:16]

        # 获取 data.yaml 路径
        data_yaml = config.get("data_yaml", "")
        dataset_path = config.get("dataset_path", "")
        if not data_yaml and dataset_path:
            yaml_candidate = os.path.join(dataset_path, "data.yaml")
            if os.path.exists(yaml_candidate):
                data_yaml = yaml_candidate

        # 创建数据库记录
        task = TrainingTask(
            user_id=user_id,
            scene_id=scene_id,
            task_uuid=task_uuid,
            status="pending",
            model_name=config.get("model_name", "yolov11n"),
            epochs=config.get("epochs", 50),
            img_size=config.get("img_size", 640),
            batch_size=config.get("batch_size", 8),
            device=config.get("device", "cpu"),
            optimizer=config.get("optimizer", "SGD"),
            lr0=config.get("lr0", 0.01),
            augment_config=config.get("augment_config"),
            dataset_path=dataset_path,
            data_yaml=data_yaml,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # 启动后台训练线程
        thread = threading.Thread(
            target=TrainingService._run_training,
            args=(task.id, task.task_uuid, config),
            daemon=True,
            name=f"train-{task_uuid}",
        )
        thread.start()

        logger.info(
            "训练任务已启动: task_id=%d, uuid=%s, model=%s, epochs=%d",
            task.id,
            task_uuid,
            task.model_name,
            task.epochs,
        )
        return task

    @staticmethod
    def _run_training(task_id: int, task_uuid: str, config: Dict[str, Any]):
        """
        在后台线程中执行 YOLOv11 训练（内部方法）
        """
        db = SessionLocal()
        original_content = ""
        data_yaml = ""

        try:
            # 1. 更新状态
            task_obj = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
            if not task_obj:
                logger.error("训练任务不存在: task_id=%d", task_id)
                return

            # 注意：此处加 # type: ignore 是为了绕过 Pylance 对 SQLAlchemy Column 赋值的静态检查
            task_obj.status = "running"  # type: ignore
            task_obj.started_at = datetime.now()  # type: ignore
            db.commit()

            # 2. 导入并加载模型
            import os

            from ultralytics import YOLO

            # 加载预训练模型
            model_name = config.get("model_name", "yolov11n")

            # 1. 找到 backend 目录的绝对路径
            # 当前文件路径是 training_service.py
            current_file_path = os.path.abspath(__file__)
            # 上一级目录 app/training
            training_dir = os.path.dirname(current_file_path)
            # 再上一级目录 app
            app_dir = os.path.dirname(training_dir)
            # 再上一级目录 backend (这就是我们要找的根)
            backend_dir = os.path.dirname(app_dir)

            # 2. 拼接成绝对路径: backend/models/yolov11n.pt
            model_path = os.path.join(backend_dir, "models", f"{model_name}.pt")

            # 3. 打印日志确认路径是否正确 (非常重要，方便排查)
            logger.info(f"准备加载本地模型: {model_path}")

            # 4. 加载模型
            model = YOLO(model_path)

            # 注册到运行中任务表
            with _running_lock:
                _running_tasks[task_uuid] = model

            # 3. 准备 data.yaml
            data_yaml = config.get("data_yaml", "")
            if not data_yaml:
                dataset_path = config.get("dataset_path", "")
                data_yaml = os.path.join(dataset_path, "data.yaml")

            if not os.path.exists(data_yaml):
                raise FileNotFoundError(f"data.yaml 不存在: {data_yaml}")

            # 修改 data.yaml 的 path 为绝对路径（训练后恢复）
            data_yaml_dir = os.path.dirname(data_yaml)
            with open(data_yaml, "r", encoding="utf-8") as f:
                original_content = f.read()

            modified_content = original_content.replace(
                "path: .", f"path: {data_yaml_dir}"
            )
            with open(data_yaml, "w", encoding="utf-8") as f:
                f.write(modified_content)

            logger.info(f"临时修改 data.yaml path 为绝对路径: {data_yaml_dir}")

            # 4. 准备训练参数
            original_cwd = os.getcwd()
            train_kwargs = {
                "data": data_yaml,
                "epochs": config.get("epochs", 50),
                "imgsz": config.get("img_size", 640),
                "batch": config.get("batch_size", 8),
                "device": config.get("device", "cpu"),
                "optimizer": config.get("optimizer", "SGD"),
                "lr0": config.get("lr0", 0.01),
                "project": os.path.join(original_cwd, settings.TRAIN_OUTPUT_DIR),
                "name": f"task_{task_uuid}",
                "exist_ok": True,
                "verbose": True,
                "save": True,
                "plots": False,
            }

            # 5. 注册训练回调
            def on_train_epoch_end(trainer):
                try:
                    epoch = trainer.epoch + 1
                    metrics = trainer.metrics or {}
                    # 修复 Pylance 类型报错
                    box_loss_val = float(metrics.get("metrics/box_loss", 0))
                    cls_loss_val = float(metrics.get("metrics/cls_loss", 0))
                    dfl_loss_val = float(metrics.get("metrics/dfl_loss", 0))
                    precision_val = float(metrics.get("metrics/precision(B)", 0))
                    recall_val = float(metrics.get("metrics/recall(B)", 0))
                    map50_val = float(metrics.get("metrics/mAP50(B)", 0))
                    map50_95_val = float(metrics.get("metrics/mAP50-95(B)", 0))

                    metric_record = TrainingMetric(
                        task_id=task_id,
                        epoch=epoch,
                        box_loss=box_loss_val,
                        cls_loss=cls_loss_val,
                        dfl_loss=dfl_loss_val,
                        precision=precision_val,
                        recall=recall_val,
                        map50=map50_val,
                        map50_95=map50_95_val,
                    )
                    db.add(metric_record)

                    total_epochs = config.get("epochs", 50)
                    # 修复 Pylance 赋值报错
                    task_obj.current_epoch = epoch  # type: ignore
                    task_obj.progress = int((epoch / total_epochs) * 100)  # type: ignore
                    db.commit()

                    logger.debug(
                        "训练进度: task=%s epoch=%d/%d box_loss=%f",
                        task_uuid,
                        epoch,
                        total_epochs,
                        metric_record.box_loss or 0,
                    )
                except Exception as e:
                    logger.warning("训练回调异常（不影响训练）: %s", str(e))
                    db.rollback()

            model.add_callback("on_train_epoch_end", on_train_epoch_end)

            # 6. 开始训练（阻塞式）
            logger.info(
                "开始训练: data=%s, epochs=%d", data_yaml, train_kwargs["epochs"]
            )
            model.train(**train_kwargs)  # type: ignore

            # 7. 训练完成
            # 修复 Pylance 赋值报错
            task_obj.status = "completed"  # type: ignore
            task_obj.progress = 100  # type: ignore
            task_obj.current_epoch = config.get("epochs", 50)  # type: ignore
            task_obj.completed_at = datetime.now()  # type: ignore
            db.commit()

            # 从 results.csv 补充最终指标
            project_path = os.path.join(original_cwd, settings.TRAIN_OUTPUT_DIR)
            TrainingService._parse_final_results(
                db, task_id, task_uuid, config, project_path
            )

            logger.info("训练完成: task_id=%d, uuid=%s", task_id, task_uuid)

        except FileNotFoundError as e:
            logger.error("训练文件缺失: task_id=%d, error=%s", task_id, str(e))
            task_obj.status = "failed"  # type: ignore
            task_obj.error_message = str(e)  # type: ignore
            db.commit()
        except Exception as e:
            logger.error(
                "训练异常: task_id=%d, error=%s", task_id, str(e), exc_info=True
            )
            task_obj.status = "failed"  # type: ignore
            task_obj.error_message = str(e)[:2000]  # type: ignore
            db.commit()
        finally:
            # 恢复 data.yaml
            try:
                if data_yaml and original_content:
                    with open(data_yaml, "w", encoding="utf-8") as f:
                        f.write(original_content)
                    logger.info("恢复 data.yaml 原始内容")
            except Exception:
                pass

            # 从运行中任务表移除
            with _running_lock:
                _running_tasks.pop(task_uuid, None)

            db.close()

    @staticmethod
    def _parse_final_results(
        db, task_id: int, task_uuid: str, config: dict, project_path: str
    ):
        """
        训练完成后从 results.csv 解析最终指标并补充到数据库
        """
        results_csv = os.path.join(project_path, f"task_{task_uuid}", "results.csv")

        if not os.path.exists(results_csv):
            logger.warning("results.csv 不存在: %s", results_csv)
            return

        try:
            existing_epochs = set()
            existing = (
                db.query(TrainingMetric).filter(TrainingMetric.task_id == task_id).all()
            )
            for m in existing:
                existing_epochs.add(m.epoch)

            def safe_float(val: str) -> float:
                try:
                    return float(val) if val else 0.0
                except ValueError:
                    return 0.0

            with open(results_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row = {k.strip(): v.strip() for k, v in row.items()}
                    epoch = int(row.get("epoch", 0)) + 1

                    if epoch in existing_epochs:
                        continue

                    metric = TrainingMetric(
                        task_id=task_id,
                        epoch=epoch,
                        box_loss=safe_float(row.get("train/box_loss", "")),
                        cls_loss=safe_float(row.get("train/cls_loss", "")),
                        dfl_loss=safe_float(row.get("train/dfl_loss", "")),
                        precision=safe_float(row.get("metrics/precision(B)", "")),
                        recall=safe_float(row.get("metrics/recall(B)", "")),
                        map50=safe_float(row.get("metrics/mAP50(B)", "")),
                        map50_95=safe_float(row.get("metrics/mAP50-95(B)", "")),
                    )
                    db.add(metric)
                    db.commit()

            logger.info("results.csv 解析完成，指标已补充到数据库")
        except Exception as e:
            logger.warning("results.csv 解析异常: %s", str(e))
            db.rollback()

    @staticmethod
    def get_training_status(db, task_id: int) -> dict:
        """获取训练任务状态"""
        task_obj = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task_obj:
            return {"error": "训练任务不存在"}

        latest_metric = (
            db.query(TrainingMetric)
            .filter(TrainingMetric.task_id == task_id)
            .order_by(TrainingMetric.epoch.desc())
            .first()
        )

        with _running_lock:
            is_running = task_obj.task_uuid in _running_tasks

        return {
            "task": {
                "id": task_obj.id,
                "task_uuid": task_obj.task_uuid,
                "status": task_obj.status,
                "model_name": task_obj.model_name,
                "epochs": task_obj.epochs,
                "current_epoch": task_obj.current_epoch,
                "progress": task_obj.progress,
                "device": task_obj.device,
                "batch_size": task_obj.batch_size,
                "img_size": task_obj.img_size,
                "started_at": str(task_obj.started_at) if task_obj.started_at else None,
                "completed_at": str(task_obj.completed_at)
                if task_obj.completed_at
                else None,
                "error_message": task_obj.error_message,
            },
            "latest_metric": {
                "epoch": latest_metric.epoch,
                "box_loss": latest_metric.box_loss,
                "cls_loss": latest_metric.cls_loss,
                "dfl_loss": latest_metric.dfl_loss,
                "precision": latest_metric.precision,
                "recall": latest_metric.recall,
                "map50": latest_metric.map50,
                "map50_95": latest_metric.map50_95,
            }
            if latest_metric
            else None,
            "is_running": is_running,
        }

    @staticmethod
    def get_training_metrics(db, task_id: int) -> list:
        """获取训练任务的所有 epoch 指标"""
        metrics = (
            db.query(TrainingMetric)
            .filter(TrainingMetric.task_id == task_id)
            .order_by(TrainingMetric.epoch.asc())
            .all()
        )
        return [
            {
                "epoch": m.epoch,
                "box_loss": m.box_loss,
                "cls_loss": m.cls_loss,
                "dfl_loss": m.dfl_loss,
                "precision": m.precision,
                "recall": m.recall,
                "map50": m.map50,
                "map50_95": m.map50_95,
            }
            for m in metrics
        ]

    @staticmethod
    def stop_training(db, task_id: int) -> dict:
        """停止正在运行的训练任务"""
        task_obj = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task_obj:
            return {"error": "训练任务不存在"}

        if task_obj.status != "running":
            return {"error": f"任务当前状态为 {task_obj.status}，无法停止"}

        with _running_lock:
            model = _running_tasks.get(task_obj.task_uuid)
            if model:
                try:
                    model.trainer.stop()
                except Exception as e:
                    logger.warning("停止训练异常: %s", str(e))

        # 修复 Pylance 赋值报错
        task_obj.status = "cancelled"  # type: ignore
        task_obj.completed_at = datetime.now()  # type: ignore
        db.commit()

        logger.info("训练任务已停止: task_id=%d", task_id)
        return {"message": "训练任务已停止", "task_id": task_id}

    @staticmethod
    def get_task_list(db, user_id: int | None = None, limit: int = 20) -> list:
        """获取训练任务列表"""
        query = db.query(TrainingTask)
        if user_id:
            query = query.filter(TrainingTask.user_id == user_id)
        tasks = query.order_by(TrainingTask.created_at.desc()).limit(limit).all()

        return [
            {
                "id": t.id,
                "task_uuid": t.task_uuid,
                "status": t.status,
                "model_name": t.model_name,
                "epochs": t.epochs,
                "current_epoch": t.current_epoch,
                "progress": t.progress,
                "device": t.device,
                "created_at": str(t.created_at),
                "started_at": str(t.started_at) if t.started_at else None,
                "completed_at": str(t.completed_at) if t.completed_at else None,
            }
            for t in tasks
        ]


training_service = TrainingService()
