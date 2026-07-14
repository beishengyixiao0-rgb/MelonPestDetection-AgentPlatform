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
import json
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

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

    BACKEND_DIR = Path(__file__).resolve().parents[2]
    PROJECT_ROOT = BACKEND_DIR.parent

    @staticmethod
    def _resolve_project_path(path_value: str | Path | None) -> Path | None:
        """将数据库中保存的项目相对路径解析为本机路径。"""
        if not path_value:
            return None
        path = Path(path_value)
        if path.is_absolute():
            return path
        return TrainingService.PROJECT_ROOT / path

    @staticmethod
    def _relative_to_project(path: Path) -> str:
        """保存数据库路径时优先使用项目相对路径，避免环境绑定。"""
        try:
            return path.resolve().relative_to(TrainingService.PROJECT_ROOT).as_posix()
        except ValueError:
            return path.as_posix()

    @staticmethod
    def get_dataset_dir(scene_name: str) -> Path:
        return TrainingService.PROJECT_ROOT / settings.DATASET_BASE_DIR / scene_name

    @staticmethod
    def get_train_output_dir() -> Path:
        output_dir = Path(settings.TRAIN_OUTPUT_DIR)
        if output_dir.is_absolute():
            return output_dir
        return TrainingService.BACKEND_DIR / output_dir

    @staticmethod
    def get_task_output_dir(task_uuid: str) -> Path:
        return TrainingService.get_train_output_dir() / f"task_{task_uuid}"

    @staticmethod
    def get_task_weights_path(task_uuid: str) -> Path:
        return TrainingService.get_task_output_dir(task_uuid) / "weights" / "best.pt"

    @staticmethod
    def get_task_results_path(task_uuid: str) -> Path:
        return TrainingService.get_task_output_dir(task_uuid) / "results.csv"

    @staticmethod
    def _safe_float(val: Any) -> float:
        try:
            return float(val) if val not in (None, "") else 0.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _metric_from_row(task_id: int, row: dict[str, Any]) -> TrainingMetric:
        row = {str(k).strip(): str(v).strip() for k, v in row.items()}
        return TrainingMetric(
            task_id=task_id,
            epoch=int(float(row.get("epoch", 0))) + 1,
            box_loss=TrainingService._safe_float(row.get("train/box_loss", "")),
            cls_loss=TrainingService._safe_float(row.get("train/cls_loss", "")),
            dfl_loss=TrainingService._safe_float(row.get("train/dfl_loss", "")),
            precision=TrainingService._safe_float(row.get("metrics/precision(B)", "")),
            recall=TrainingService._safe_float(row.get("metrics/recall(B)", "")),
            map50=TrainingService._safe_float(row.get("metrics/mAP50(B)", "")),
            map50_95=TrainingService._safe_float(row.get("metrics/mAP50-95(B)", "")),
            lr=TrainingService._safe_float(row.get("lr/pg0", "")),
        )

    @staticmethod
    def import_results_csv(db, task_id: int, results_csv: str | Path) -> int:
        """
        将 results.csv 指标导入 training_metrics。

        已存在的 epoch 会跳过，保证脚本或服务重复执行时不会重复插入。
        """
        csv_path = Path(results_csv)
        if not csv_path.exists():
            logger.warning("results.csv 不存在: %s", csv_path)
            return 0

        existing_epochs = {
            m.epoch
            for m in db.query(TrainingMetric)
            .filter(TrainingMetric.task_id == task_id)
            .all()
        }
        imported = 0
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                metric = TrainingService._metric_from_row(task_id, row)
                if metric.epoch in existing_epochs:
                    continue
                db.add(metric)
                existing_epochs.add(metric.epoch)
                imported += 1
        db.commit()
        return imported

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
        data_yaml_path = TrainingService._resolve_project_path(config.get("data_yaml"))
        dataset_path = TrainingService._resolve_project_path(config.get("dataset_path"))
        if not data_yaml_path and dataset_path:
            yaml_candidate = dataset_path / "data.yaml"
            if yaml_candidate.exists():
                data_yaml_path = yaml_candidate

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
            dataset_path=TrainingService._relative_to_project(dataset_path)
            if dataset_path
            else None,
            data_yaml=TrainingService._relative_to_project(data_yaml_path)
            if data_yaml_path
            else None,
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
            from ultralytics import YOLO

            # 加载预训练模型
            model_name = config.get("model_name", "yolov11n")

            # 1. 找到 backend 目录
            # 当前文件路径是 training_service.py
            # 2. 拼接成路径: backend/models/yolov11n.pt
            model_path = TrainingService.BACKEND_DIR / "models" / f"{model_name}.pt"

            # 3. 打印日志确认路径是否正确 (非常重要，方便排查)
            logger.info("准备加载本地模型: %s", model_path)

            # 4. 加载模型
            model = YOLO(str(model_path))

            # 注册到运行中任务表
            with _running_lock:
                _running_tasks[task_uuid] = model

            # 3. 准备 data.yaml
            data_yaml_path = TrainingService._resolve_project_path(config.get("data_yaml"))
            if not data_yaml_path:
                dataset_path = TrainingService._resolve_project_path(
                    config.get("dataset_path")
                )
                if dataset_path:
                    data_yaml_path = dataset_path / "data.yaml"

            if not data_yaml_path or not data_yaml_path.exists():
                raise FileNotFoundError(f"data.yaml 不存在: {data_yaml_path}")

            # 4. 准备训练参数
            train_kwargs = {
                "data": str(data_yaml_path),
                "epochs": config.get("epochs", 50),
                "imgsz": config.get("img_size", 640),
                "batch": config.get("batch_size", 8),
                "device": config.get("device", "cpu"),
                "optimizer": config.get("optimizer", "SGD"),
                "lr0": config.get("lr0", 0.01),
                "project": str(TrainingService.get_train_output_dir()),
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
                "开始训练: data=%s, epochs=%d", data_yaml_path, train_kwargs["epochs"]
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
            TrainingService._parse_final_results(db, task_id, task_uuid, config)

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
            # 从运行中任务表移除
            with _running_lock:
                _running_tasks.pop(task_uuid, None)

            db.close()

    @staticmethod
    def _parse_final_results(db, task_id: int, task_uuid: str, config: dict):
        """
        训练完成后从 results.csv 解析最终指标并补充到数据库
        """
        del config
        results_csv = TrainingService.get_task_results_path(task_uuid)

        try:
            imported = TrainingService.import_results_csv(db, task_id, results_csv)
            logger.info("results.csv 解析完成，新增指标 %d 条", imported)
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
                "lr": m.lr,
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

    @staticmethod
    def validate_model(
        db,
        task_id: int,
        split: str = "val",
        conf: float = 0.25,
        iou: float = 0.45,
    ) -> dict:
        """
        对已完成训练的模型执行验证集评估

        流程：
          1. 查找训练任务对应的 best.pt 路径
          2. 加载模型并运行 model.val()
          3. 解析评估结果
          4. 将评估指标写入 ModelVersion 表
          5. 返回结构化评估报告

        Args:
            db: 数据库会话
            task_id: 训练任务 ID
            split: 评估数据集划分（val / test）
            conf: 置信度阈值
            iou: NMS IoU 阈值

        Returns:
            评估报告字典
        """
        from ultralytics import YOLO

        # ── 查找训练任务 ──
        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            return {"error": "训练任务不存在"}

        if task.status != "completed":
            return {"error": f"训练任务状态为 {task.status}，只有已完成的任务才能评估"}

        # ── 定位 best.pt ──
        weights_path = TrainingService.get_task_weights_path(task.task_uuid)

        if not weights_path.exists():
            return {"error": f"模型权重不存在: {weights_path}"}

        # ── 定位 data.yaml ──
        data_yaml = TrainingService._resolve_project_path(task.data_yaml)
        if not data_yaml or not data_yaml.exists():
            # 尝试在数据集目录下查找
            dataset_path = TrainingService._resolve_project_path(task.dataset_path)
            if dataset_path:
                data_yaml = dataset_path / "data.yaml"
        if not data_yaml or not data_yaml.exists():
            return {"error": "data.yaml 不存在"}

        logger.info(
            "开始模型评估: task_id=%d, weights=%s, split=%s",
            task_id,
            weights_path,
            split,
        )

        try:
            # ── 加载模型并评估 ──
            model = YOLO(str(weights_path))
            results = model.val(
                data=str(data_yaml),
                split=split,
                conf=conf,
                iou=iou,
                imgsz=task.img_size,
                device="cpu",
                save_json=True,
                plots=True,
                project=str(TrainingService.get_train_output_dir()),
                name=f"task_{task.task_uuid}",
                exist_ok=True,
                verbose=False,
            )

            # ── 解析评估结果 ──
            overall = {
                "precision": float(results.box.mp),
                "recall": float(results.box.mr),
                "map50": float(results.box.map50),
                "map50_95": float(results.box.map),
            }

            per_class = {}
            if results.box.ap is not None:
                for i, ap50 in enumerate(results.box.ap50):
                    class_name = model.names.get(i, f"class_{i}")
                    ap50_95 = results.box.ap[i] if i < len(results.box.ap) else 0.0
                    per_class[class_name] = {
                        "ap50": round(float(ap50), 4),
                        "ap50_95": round(float(ap50_95), 4),
                    }

            report = {
                "task_id": task_id,
                "task_uuid": task.task_uuid,
                "split": split,
                "overall": overall,
                "per_class": per_class,
            }

            # ── 更新或创建 ModelVersion 记录 ──
            from app.entity.db_models import DetectionScene, ModelVersion

            scene = (
                db.query(DetectionScene)
                .filter(DetectionScene.id == task.scene_id)
                .first()
            )
            if not scene:
                return {"error": "关联场景不存在"}

            # 查找已有版本或创建新版本
            model_version = (
                db.query(ModelVersion)
                .filter(ModelVersion.training_task_id == task_id)
                .first()
            )

            if not model_version:
                # 生成版本号
                existing_count = (
                    db.query(ModelVersion)
                    .filter(ModelVersion.scene_id == task.scene_id)
                    .count()
                )
                version = f"v{existing_count + 1}.0.0"

                model_version = ModelVersion(
                    scene_id=task.scene_id,
                    training_task_id=task_id,
                    version=version,
                    model_name=f"{task.model_name}_{scene.name}_{version}",
                    model_type=task.model_name,
                    model_path=TrainingService._relative_to_project(weights_path),
                    map50=overall["map50"],
                    map50_95=overall["map50_95"],
                    precision=overall["precision"],
                    recall=overall["recall"],
                    per_class_ap=per_class,
                    file_size=weights_path.stat().st_size,
                    description=f"训练任务 {task.task_uuid} 自动产出",
                )
                db.add(model_version)
            else:
                # 更新已有版本的评估指标
                model_version.map50 = overall["map50"]
                model_version.map50_95 = overall["map50_95"]
                model_version.precision = overall["precision"]
                model_version.recall = overall["recall"]
                model_version.per_class_ap = per_class

            db.commit()
            report["model_version_id"] = model_version.id
            report["model_version"] = model_version.version

            logger.info(
                "模型评估完成: task_id=%d, mAP50=%.4f, mAP50-95=%.4f",
                task_id,
                overall["map50"],
                overall["map50_95"],
            )

            return report

        except Exception as e:
            logger.error(
                "模型评估异常: task_id=%d, error=%s", task_id, str(e), exc_info=True
            )
            return {"error": f"评估失败: {str(e)}"}

    @staticmethod
    def export_model(
        db,
        task_id: int,
        version: str = None,
        description: str = None,
        set_default: bool = False,
        upload_minio: bool = True,
    ) -> dict:
        """
        导出训练好的模型为正式版本

        流程：
          1. 复制 best.pt 到 models/ 目录
          2. 运行评估获取最终指标
          3. 保存评估报告 JSON
          4. 创建 ModelVersion 记录
          5. 可选上传到 MinIO

        Args:
            db: 数据库会话
            task_id: 训练任务 ID
            version: 版本号（如 v1.0.0，不传则自动生成）
            description: 版本描述/变更说明
            set_default: 是否设为该场景的默认模型
            upload_minio: 是否上传到 MinIO

        Returns:
            导出结果字典
        """
        from app.entity.db_models import DetectionScene, ModelVersion

        # ── 查找训练任务 ──
        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            return {"error": "训练任务不存在"}

        if task.status != "completed":
            return {"error": f"训练任务状态为 {task.status}，只有已完成的任务才能导出"}

        # ── 定位 best.pt ──
        weights_path = TrainingService.get_task_weights_path(task.task_uuid)

        if not weights_path.exists():
            return {"error": f"模型权重不存在: {weights_path}"}

        # ── 获取场景信息 ──
        scene = db.query(DetectionScene).filter(DetectionScene.id == task.scene_id).first()
        if not scene:
            return {"error": "关联场景不存在"}

        # ── 生成版本号 ──
        if not version:
            existing_count = (
                db.query(ModelVersion)
                .filter(ModelVersion.scene_id == task.scene_id)
                .count()
            )
            version = f"v{existing_count + 1}.0.0"

        # ── 创建导出目录 ──
        export_dir = TrainingService.BACKEND_DIR / "models" / f"{scene.name}_{version}"
        export_dir.mkdir(parents=True, exist_ok=True)

        # ── 复制模型文件 ──
        exported_weight = export_dir / "best.pt"
        shutil.copy2(weights_path, exported_weight)
        logger.info("模型文件已复制: %s -> %s", weights_path, exported_weight)

        # ── 复制评估图表（如果存在）──
        task_output_dir = TrainingService.get_task_output_dir(task.task_uuid)
        eval_plots = [
            "confusion_matrix.png",
            "PR_curve.png",
            "F1_curve.png",
            "results.png",
        ]
        extra_eval_plots = {
            "BoxPR_curve.png": "PR_curve.png",
            "BoxF1_curve.png": "F1_curve.png",
        }
        for plot_name in eval_plots:
            src = task_output_dir / plot_name
            if src.exists():
                shutil.copy2(src, export_dir / plot_name)
        for src_name, dst_name in extra_eval_plots.items():
            src = task_output_dir / src_name
            dst = export_dir / dst_name
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)

        # ── 获取评估指标（从训练过程已有的 results.csv 读取，避免重复评估）──
        # 训练过程中每轮验证都会写入 results.csv，最后一轮的指标就是最终评估结果
        csv_path = TrainingService.get_task_results_path(task.task_uuid)

        overall = {}
        per_class = {}

        if csv_path.exists():
            try:
                with csv_path.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                if rows:
                    last_row = {k.strip(): v.strip() for k, v in rows[-1].items()}
                    overall = {
                        "precision": TrainingService._safe_float(
                            last_row.get("metrics/precision(B)", "")
                        ),
                        "recall": TrainingService._safe_float(
                            last_row.get("metrics/recall(B)", "")
                        ),
                        "map50": TrainingService._safe_float(
                            last_row.get("metrics/mAP50(B)", "")
                        ),
                        "map50_95": TrainingService._safe_float(
                            last_row.get("metrics/mAP50-95(B)", "")
                        ),
                    }
                    # 从已有 ModelVersion 记录获取每类指标（如果存在）
                    existing_version = (
                        db.query(ModelVersion)
                        .filter(ModelVersion.training_task_id == task_id)
                        .first()
                    )
                    if existing_version and existing_version.per_class_ap:
                        per_class = existing_version.per_class_ap
                    logger.info(
                        "从 results.csv 读取评估指标: task_id=%d, mAP50=%.4f",
                        task_id,
                        overall.get("map50", 0),
                    )
            except Exception as e:
                logger.warning("从 results.csv 读取指标失败: %s", e)

        # 如果 results.csv 读取失败，再尝试从 ModelVersion 记录获取
        if not overall or overall.get("map50") is None:
            existing_version = (
                db.query(ModelVersion)
                .filter(ModelVersion.training_task_id == task_id)
                .first()
            )
            if existing_version and existing_version.map50 is not None:
                overall = {
                    "precision": existing_version.precision,
                    "recall": existing_version.recall,
                    "map50": existing_version.map50,
                    "map50_95": existing_version.map50_95,
                }
                per_class = existing_version.per_class_ap or {}
                logger.info(
                    "使用已有 ModelVersion 指标: task_id=%d, mAP50=%.4f",
                    task_id,
                    existing_version.map50,
                )

        # ── 保存评估报告 JSON ──
        report = {
            "version": version,
            "model_name": task.model_name,
            "scene": scene.name,
            "training_task": task.task_uuid,
            "evaluation": {
                "split": "val",
                "overall": overall,
                "per_class": per_class,
            },
            "training_config": {
                "epochs": task.epochs,
                "batch_size": task.batch_size,
                "img_size": task.img_size,
                "optimizer": task.optimizer,
                "lr0": task.lr0,
                "device": task.device,
            },
            "exported_at": datetime.now().isoformat(),
        }
        report_path = export_dir / "eval_report.json"
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # ── 上传到 MinIO ──
        minio_url = None
        if upload_minio:
            try:
                from app.storage.minio_client import MinIOClient

                minio_client = MinIOClient()
                object_name = f"models/{scene.name}/{version}/best.pt"
                minio_url = minio_client.upload_file(object_name, str(exported_weight))
                logger.info("模型已上传 MinIO: %s", minio_url)
            except Exception as e:
                logger.warning("MinIO 上传失败（不影响导出）: %s", str(e))

        # ── 创建/更新 ModelVersion 记录 ──
        model_version = (
            db.query(ModelVersion).filter(ModelVersion.training_task_id == task_id).first()
        )

        if model_version:
            # 更新已有记录
            model_version.version = version
            model_version.model_path = TrainingService._relative_to_project(
                exported_weight
            )
            model_version.minio_url = minio_url
            model_version.map50 = overall.get("map50")
            model_version.map50_95 = overall.get("map50_95")
            model_version.precision = overall.get("precision")
            model_version.recall = overall.get("recall")
            model_version.per_class_ap = per_class
            model_version.file_size = exported_weight.stat().st_size
            model_version.description = description or f"训练任务 {task.task_uuid} 导出"
        else:
            model_version = ModelVersion(
                scene_id=task.scene_id,
                training_task_id=task_id,
                version=version,
                model_name=f"{task.model_name}_{scene.name}_{version}",
                model_type=task.model_name,
                model_path=TrainingService._relative_to_project(exported_weight),
                minio_url=minio_url,
                map50=overall.get("map50"),
                map50_95=overall.get("map50_95"),
                precision=overall.get("precision"),
                recall=overall.get("recall"),
                per_class_ap=per_class,
                file_size=exported_weight.stat().st_size,
                description=description or f"训练任务 {task.task_uuid} 导出",
            )
            db.add(model_version)

        # ── 设置默认模型 ──
        if set_default:
            # 取消该场景其他版本的默认标记
            db.query(ModelVersion).filter(
                ModelVersion.scene_id == task.scene_id,
                ModelVersion.id != model_version.id,
            ).update({"is_default": False})
            model_version.is_default = True

        db.commit()
        db.refresh(model_version)

        logger.info(
            "模型导出完成: scene=%s, version=%s, mAP50=%.4f",
            scene.name,
            version,
            overall.get("map50", 0),
        )

        return {
            "model_version_id": model_version.id,
            "version": version,
            "model_name": model_version.model_name,
            "model_path": TrainingService._relative_to_project(exported_weight),
            "export_dir": TrainingService._relative_to_project(export_dir),
            "minio_url": minio_url,
            "file_size": model_version.file_size,
            "evaluation": {
                "map50": overall.get("map50"),
                "map50_95": overall.get("map50_95"),
                "precision": overall.get("precision"),
                "recall": overall.get("recall"),
                "per_class": per_class,
            },
            "is_default": model_version.is_default,
            "message": f"模型已导出为版本 {version}",
        }

    @staticmethod
    def get_model_download_path(db, task_id: int) -> dict:
        """获取训练好的模型权重文件路径（best.pt）"""
        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            return {"error": "训练任务不存在"}
        if task.status != "completed":
            return {"error": f"训练任务状态为 {task.status}，无法下载模型"}

        weights_path = TrainingService.get_task_weights_path(task.task_uuid)
        if not weights_path.exists():
            return {"error": f"模型权重不存在: {weights_path}"}

        return {
            "file_path": str(weights_path),
            "filename": f"best_{task.task_uuid}.pt",
        }


training_service = TrainingService()
