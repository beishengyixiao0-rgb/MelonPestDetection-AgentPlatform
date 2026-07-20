"""
目标检测服务 — 封装 YOLOv11 推理逻辑

职责：
  - 单图检测（detect_single）
  - 批量检测（detect_batch）
  - ZIP 解压 + 批量检测（detect_zip）
  - 结果持久化（MinIO 存储标注图 + PostgreSQL 存储检测结果）

架构：
  DetectionService 是无状态的纯服务，被 Agent Tool 和快捷按钮 API 共同调用。
  每次检测都会：
    1. 创建 DetectionTask 记录
    2. 运行 YOLO 推理
    3. 上传 标注图到 MinIO
    4. 保存 DetectionResult 记录

使用方式：
  from app.services.detection_service import detection_service

  result = detection_service.detect_single(image_path, scene_id, user_id)
"""

import base64
import os
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session
from ultralytics import YOLO

from app.config.detection import DetectionConfig
from app.config.settings import settings
from app.core.logger import get_logger
from app.database.session import SessionLocal
from app.entity.db_models import DetectionResult, DetectionScene, DetectionTask, ModelVersion
from app.storage.minio_client import MinIOClient
from app.storage.redis_client import redis_client
from app.training.training_service import TrainingService

logger = get_logger(__name__)

# ── 支持的图片格式 ──
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/bmp",
    "image/webp",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp",
}
ALLOWED_IMAGE_SUFFIXES = {item for item in ALLOWED_IMAGE_TYPES if item.startswith(".")}


class DetectionService:
    """目标检测服务 — 封装 YOLOv11 推理全流程"""

    @staticmethod
    def _resolve_model_path(path_value: str | None) -> str | None:
        """兼容 Day07 写入数据库的项目相对模型路径。"""
        path = TrainingService._resolve_project_path(path_value)
        return str(path) if path and path.exists() else None

    @staticmethod
    def _get_default_model_path() -> str:
        """
        获取默认模型权重路径

        查找顺序：
          1. models/ 目录下 is_default=True 的模型
          2. runs/train/ 目录下最新训练产出的 best.pt
          3. 回退到预训练模型 yolov11n.pt
        """
        db = SessionLocal()
        try:
            # 查找默认模型版本
            default_model = db.query(ModelVersion).filter(ModelVersion.is_default.is_(True)).first()
            model_path = DetectionService._resolve_model_path(default_model.model_path) if default_model else None
            if model_path:
                return model_path

            # 回退：查找最新训练的 best.pt
            from app.entity.db_models import TrainingTask

            latest_task = (
                db.query(TrainingTask)
                .filter(TrainingTask.status == "completed")
                .order_by(TrainingTask.completed_at.desc())
                .first()
            )
            if latest_task:
                weights_path = TrainingService.get_task_weights_path(latest_task.task_uuid)
                if weights_path.exists():
                    return str(weights_path)
        finally:
            db.close()

        # 最终回退：预训练模型
        configured_path = Path(DetectionConfig.model_path)
        if not configured_path.is_absolute():
            configured_path = TrainingService.BACKEND_DIR / configured_path
        return str(configured_path) if configured_path.exists() else "yolo11n.pt"

    @staticmethod
    def _get_model(scene_id: int = None) -> YOLO:
        """
        加载 YOLO 模型

        优先使用场景关联的默认模型，否则使用全局默认模型
        """
        model_path = None

        if scene_id:
            db = SessionLocal()
            try:
                default_model = (
                    db.query(ModelVersion)
                    .filter(ModelVersion.scene_id == scene_id, ModelVersion.is_default.is_(True))
                    .first()
                )
                model_path = DetectionService._resolve_model_path(default_model.model_path) if default_model else None
            finally:
                db.close()

        if not model_path:
            model_path = DetectionService._get_default_model_path()

        logger.info("加载检测模型: %s", model_path)
        return YOLO(model_path)

    @staticmethod
    def _resolve_scene_id(db: Session, scene_id: int | None) -> int | None:
        """快捷接口未传场景时使用第一个启用场景，保证检测记录可以持久化。"""
        if scene_id is not None:
            scene = (
                db.query(DetectionScene)
                .filter(
                    DetectionScene.id == scene_id,
                    DetectionScene.is_active.is_(True),
                )
                .first()
            )
            return scene.id if scene else None
        scene = db.query(DetectionScene).filter(DetectionScene.is_active.is_(True)).first()
        return scene.id if scene else None

    @staticmethod
    def _get_scene_class_names_cn(db: Session, scene_id: int | None) -> dict:
        if not scene_id:
            return {}
        scene = db.query(DetectionScene).filter(DetectionScene.id == scene_id).first()
        return scene.class_names_cn if scene and isinstance(scene.class_names_cn, dict) else {}

    @staticmethod
    def _detection_from_box(
        box,
        model: YOLO,
        class_names_cn: dict | None = None,
        display_language: str = "zh",
    ) -> dict:
        cls_id = int(box.cls[0])
        class_name = model.names.get(cls_id, f"class_{cls_id}")
        # 原始类别名始终保留，仅根据本次请求语言计算面向用户的显示字段。
        class_name_display = DetectionConfig.display_class_name(
            class_name, class_names_cn, display_language
        )
        confidence = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        return {
            "class_name": class_name,
            "class_name_cn": class_name_display if class_name_display != class_name else None,
            "class_name_display": class_name_display,
            "class_id": cls_id,
            "confidence": round(confidence, 4),
            "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
        }

    @staticmethod
    def _load_label_font(size: int):
        candidates = [
            DetectionConfig.font_path,
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                try:
                    return ImageFont.truetype(candidate, size)
                except OSError:
                    continue
        return None

    @classmethod
    def _draw_detections_on_frame(cls, frame, detections: list) :
        """绘制支持中文的检测框；OpenCV Hershey 字体不支持中文，因此使用 Pillow。"""
        annotated = frame.copy()
        color_bgr = (0, 200, 0)
        for det in detections:
            x1, y1, x2, y2 = [int(value) for value in det["bbox"]]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color_bgr, 2)

        font = cls._load_label_font(max(16, round(min(frame.shape[:2]) / 40)))
        if font is None:
            for det in detections:
                x1, y1, _, _ = [int(value) for value in det["bbox"]]
                label = f"{det.get('class_name_display', det['class_name'])} {det['confidence']:.2f}"
                cv2.putText(annotated, label, (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 2)
            return annotated

        image = Image.fromarray(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(image)
        for det in detections:
            x1, y1, _, _ = [int(value) for value in det["bbox"]]
            label = f"{det.get('class_name_display', det['class_name'])} {det['confidence']:.2f}"
            left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
            text_width = right - left
            text_height = bottom - top
            text_y = max(0, y1 - text_height - 6)
            draw.rectangle((x1, text_y, x1 + text_width + 8, text_y + text_height + 6), fill=(0, 120, 0))
            draw.text((x1 + 4, text_y + 2), label, font=font, fill=(255, 255, 255))
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    @staticmethod
    def _bbox_iou(box_a: list[float], box_b: list[float]) -> float:
        """计算两个边界框的 IoU，供跟踪器无 ID 时做轻量降级匹配。"""
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(
            0.0, min(ay2, by2) - max(ay1, by1)
        )
        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = area_a + area_b - intersection
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _set_video_progress(
        task_id: int,
        progress: int,
        message: str,
        source_video_url: str | None = None,
    ) -> None:
        """写入短生命周期的轮询进度；Redis 不可用时由客户端自动降级。"""
        try:
            payload = {"status": "processing", "progress": progress, "message": message}
            if source_video_url:
                payload["source_video_url"] = source_video_url
            redis_client.set_json(
                f"video_task:{task_id}",
                payload,
                expire=3600,
            )
        except Exception as exc:
            logger.warning("更新视频任务进度失败: %s", exc)

    @staticmethod
    def _save_task_and_results(
        db: Session,
        user_id: int,
        scene_id: int,
        task_type: str,
        detections: list,
        annotated_image: bytes,
        original_image: bytes | None,
        original_filename: str,
        inference_time: float,
        conf: float,
        iou: float,
    ) -> dict:
        """
        保存检测任务和结果到数据库 + MinIO

        Returns:
            包含 task_id 和 annotated_image_url 的字典
        """
        # ── 创建检测任务记录 ──
        task = DetectionTask(
            user_id=user_id,
            scene_id=scene_id,
            task_type=task_type,
            status="completed",
            total_images=1,
            total_objects=len(detections),
            total_inference_time=inference_time,
            conf_threshold=conf,
            iou_threshold=iou,
            completed_at=datetime.now(),
        )
        db.add(task)
        db.flush()  # 获取 task.id

        # ── 上传原图和标注图到 MinIO，报告导出时可直接嵌入图片。 ──
        source_image_url = None
        annotated_image_url = None
        try:
            minio_client = MinIOClient()
            if original_image:
                source_object_name = f"detections/{task.id}/source_{original_filename}"
                source_image_url = minio_client.upload_bytes(
                    source_object_name, original_image, "image/jpeg"
                )
            annotated_object_name = f"detections/{task.id}/annotated_{original_filename}"
            annotated_image_url = minio_client.upload_bytes(
                annotated_object_name, annotated_image, "image/jpeg"
            )
        except Exception as e:
            logger.warning("MinIO 上传失败（不影响检测结果）: %s", str(e))

        # ── 保存每条检测结果 ──
        for det in detections:
            result = DetectionResult(
                task_id=task.id,
                image_path=source_image_url or original_filename,
                annotated_image_url=annotated_image_url,
                class_name=det["class_name"],
                class_name_cn=det.get("class_name_cn"),
                class_id=det["class_id"],
                confidence=det["confidence"],
                bbox=det["bbox"],
                inference_time=inference_time,
            )
            db.add(result)

        db.commit()
        return {
            "task_id": task.id,
            "source_image_url": source_image_url,
            "annotated_image_url": annotated_image_url,
        }

    def detect_single(
        self,
        image_path: str,
        conf: float = DetectionConfig.conf_threshold,
        iou: float = DetectionConfig.iou_threshold,
        scene_id: int = None,
        user_id: int = None,
        display_language: str = "zh",
    ) -> dict:
        """
        单图检测

        Args:
            image_path: 图片文件路径
            conf: 置信度阈值
            iou: NMS IoU 阈值
            scene_id: 检测场景 ID
            user_id: 操作用户 ID

        Returns:
            检测结果字典：
            {
                "total_objects": int,
                "class_counts": {"class_name": count, ...},
                "detections": [...],
                "annotated_image_base64": str,
                "inference_time": float,
                "task_id": int,
            }
        """
        db = SessionLocal()
        try:
            if Path(image_path).suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
                return {"error": "不支持的图片格式"}
            if not Path(image_path).is_file():
                return {"error": "图片文件不存在"}
            if not 0 <= conf <= 1 or not 0 <= iou <= 1:
                return {"error": "conf 和 iou 必须在 0 到 1 之间"}

            # ── 加载模型 ──
            scene_id = self._resolve_scene_id(db, scene_id)
            scene_class_names_cn = self._get_scene_class_names_cn(db, scene_id)
            model = self._get_model(scene_id)

            # ── YOLO 推理 ──
            results = model.predict(
                source=image_path,
                conf=conf,
                iou=iou,
                imgsz=DetectionConfig.image_size,
                device=DetectionConfig.device,
                save=False,
                verbose=False,
            )

            result = results[0]
            detections = []
            total_objects = 0

            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    detections.append(
                        self._detection_from_box(
                            box, model, scene_class_names_cn, display_language
                        )
                    )
                    total_objects += 1

            # ── 生成标注图 ──
            source_frame = cv2.imread(image_path)
            annotated_img = (
                self._draw_detections_on_frame(source_frame, detections)
                if source_frame is not None
                else result.plot()
            )
            _, buffer = cv2.imencode(".jpg", annotated_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            annotated_base64 = base64.b64encode(buffer).decode("utf-8")

            # ── 统计各类别数量 ──
            class_counts = {}
            class_counts_display = {}
            for det in detections:
                name = det["class_name"]
                class_counts[name] = class_counts.get(name, 0) + 1
                display_name = det["class_name_display"]
                class_counts_display[display_name] = class_counts_display.get(display_name, 0) + 1

            # ── 持久化到数据库 ──
            task_id = None
            annotated_image_url = None
            if user_id and scene_id:
                save_result = self._save_task_and_results(
                    db=db,
                    user_id=user_id,
                    scene_id=scene_id,
                    task_type="single",
                    detections=detections,
                    annotated_image=buffer.tobytes(),
                    original_image=Path(image_path).read_bytes(),
                    original_filename=os.path.basename(image_path),
                    inference_time=float(result.speed.get("inference", 0)),
                    conf=conf,
                    iou=iou,
                )
                task_id = save_result["task_id"]
                annotated_image_url = save_result.get("annotated_image_url")

            logger.info("单图检测完成: %s, 检测到 %d 个目标, 耗时 %.2fms", image_path, total_objects, float(result.speed.get("inference", 0)))

            return {
                "total_objects": total_objects,
                "class_counts": class_counts,
                "class_counts_display": class_counts_display,
                "detections": detections,
                "annotated_image_base64": annotated_base64,
                "annotated_image_url": annotated_image_url,
                "inference_time": round(float(result.speed.get("inference", 0)), 2),
                "task_id": task_id,
            }

        except Exception as e:
            db.rollback()
            logger.error("单图检测异常: %s", str(e), exc_info=True)
            return {"error": f"检测失败: {str(e)}"}
        finally:
            db.close()

    def detect_batch(
        self,
        image_paths: list[str],
        conf: float = DetectionConfig.conf_threshold,
        iou: float = DetectionConfig.iou_threshold,
        scene_id: int = None,
        user_id: int = None,
        display_language: str = "zh",
    ) -> dict:
        """
        批量检测多张图片

        Args:
            image_paths: 图片文件路径列表
            conf: 置信度阈值
            scene_id: 检测场景 ID
            user_id: 操作用户 ID

        Returns:
            批量检测结果字典
        """
        db = SessionLocal()
        try:
            if not image_paths:
                return {"error": "请至少上传一张图片"}
            if len(image_paths) > DetectionConfig.max_batch_size:
                return {"error": f"单次最多检测 {DetectionConfig.max_batch_size} 张图片"}
            if not 0 <= conf <= 1 or not 0 <= iou <= 1:
                return {"error": "conf 和 iou 必须在 0 到 1 之间"}

            # 当 scene_id 为 None 时，自动查询第一个可用场景
            scene_id = self._resolve_scene_id(db, scene_id)
            if not scene_id:
                return {"error": "数据库中没有可用的检测场景，请先创建检测场景"}
            if not user_id:
                return {"error": "检测操作需要登录用户"}
            scene_class_names_cn = self._get_scene_class_names_cn(db, scene_id)
            model = self._get_model(scene_id)

            # ── 创建批量检测任务 ──
            task = DetectionTask(
                user_id=user_id,
                scene_id=scene_id,
                task_type="batch",
                status="processing",
                total_images=len(image_paths),
                conf_threshold=conf,
                iou_threshold=iou,
            )
            db.add(task)
            db.flush()

            all_detections = []
            annotated_images = []  # 每张图片的标注图 base64
            total_objects = 0
            total_inference_time = 0
            class_counts = {}
            class_counts_display = {}
            minio_client = None

            for i, image_path in enumerate(image_paths):
                if Path(image_path).suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
                    continue
                results = model.predict(source=image_path, conf=conf, iou=iou, imgsz=DetectionConfig.image_size, device=DetectionConfig.device, save=False, verbose=False)
                result = results[0]
                inference_time = float(result.speed.get("inference", 0))
                total_inference_time += inference_time

                image_detections = []
                if result.boxes is not None and len(result.boxes) > 0:
                    for box in result.boxes:
                        det = self._detection_from_box(
                            box, model, scene_class_names_cn, display_language
                        )
                        det.update({"image_path": image_path, "inference_time": inference_time})
                        image_detections.append(det)
                        all_detections.append(det)
                        total_objects += 1

                        # 统计类别计数
                        class_name = det["class_name"]
                        class_counts[class_name] = class_counts.get(class_name, 0) + 1
                        display_name = det["class_name_display"]
                        class_counts_display[display_name] = class_counts_display.get(display_name, 0) + 1

                # 生成使用中文显示名的标注图
                source_frame = cv2.imread(image_path)
                annotated_img = (
                    self._draw_detections_on_frame(source_frame, image_detections)
                    if source_frame is not None
                    else result.plot()
                )
                _, buffer = cv2.imencode(".jpg", annotated_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                annotated_images.append({"image_path": os.path.basename(image_path), "annotated_image_base64": base64.b64encode(buffer).decode("utf-8")})

                source_image_url = None
                annotated_image_url = None
                try:
                    if minio_client is None:
                        minio_client = MinIOClient()
                    safe_name = os.path.basename(image_path)
                    source_image_url = minio_client.upload_file(
                        f"detections/{task.id}/source_{i}_{safe_name}",
                        image_path,
                        content_type="image/jpeg",
                    )
                    annotated_image_url = minio_client.upload_bytes(
                        f"detections/{task.id}/annotated_{i}_{safe_name}",
                        buffer.tobytes(),
                        "image/jpeg",
                    )
                except Exception as exc:
                    logger.warning("批量检测图片上传 MinIO 失败（不影响检测结果）: %s", exc)

                # 保存检测结果到数据库
                for det in image_detections:
                    db.add(
                        DetectionResult(
                            task_id=task.id,
                            image_path=source_image_url or image_path,
                            annotated_image_url=annotated_image_url,
                            class_name=det["class_name"],
                            class_name_cn=det.get("class_name_cn"),
                            class_id=det["class_id"],
                            confidence=det["confidence"],
                            bbox=det["bbox"],
                            inference_time=inference_time,
                        )
                    )

            task.status = "completed"
            task.total_objects = total_objects
            task.total_inference_time = total_inference_time
            task.completed_at = datetime.now()
            db.commit()

            logger.info("批量检测完成: %d 张图, 共 %d 个目标, 总耗时 %.2fms", len(image_paths), total_objects, total_inference_time)

            return {"task_id": task.id, "total_images": len(image_paths), "total_objects": total_objects, "class_counts": class_counts, "class_counts_display": class_counts_display, "total_inference_time": round(total_inference_time, 2), "detections": all_detections, "annotated_images": annotated_images}

        except Exception as e:
            db.rollback()
            logger.error("批量检测异常: %s", str(e), exc_info=True)
            return {"error": f"批量检测失败: {str(e)}"}
        finally:
            db.close()

    def detect_zip(
        self,
        zip_path: str,
        conf: float = DetectionConfig.conf_threshold,
        iou: float = DetectionConfig.iou_threshold,
        scene_id: int = None,
        user_id: int = None,
        display_language: str = "zh",
    ) -> dict:
        """
        解压 ZIP 文件并批量检测其中所有图片

        Args:
            zip_path: ZIP 文件路径
            conf: 置信度阈值
            scene_id: 检测场景 ID
            user_id: 操作用户 ID

        Returns:
            ZIP 检测结果字典
        """
        temp_dir = None
        try:
            # ── 解压 ZIP 到临时目录 ──
            temp_dir = tempfile.mkdtemp(prefix="rsod_zip_")
            logger.info("解压 ZIP 文件: %s → %s", zip_path, temp_dir)

            with zipfile.ZipFile(zip_path, "r") as zf:
                # 指导书使用 extractall；这里逐文件校验目标路径，防止 ZIP 路径穿越。
                for member in zf.infolist():
                    if member.is_dir() or Path(member.filename).suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
                        continue
                    target = (Path(temp_dir) / member.filename).resolve()
                    if Path(temp_dir).resolve() not in target.parents:
                        return {"error": "ZIP 文件包含非法路径"}
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as source, target.open("wb") as destination:
                        shutil.copyfileobj(source, destination)

            # ── 筛选图片文件 ──
            image_files = []
            for root, dirs, files in os.walk(temp_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in ALLOWED_IMAGE_SUFFIXES:
                        image_files.append(os.path.join(root, fname))

            if not image_files:
                return {"error": "ZIP 文件中没有找到图片"}

            logger.info("ZIP 中包含 %d 张图片，开始批量检测", len(image_files))

            # ── 调用批量检测 ──
            batch_result = self.detect_batch(
                image_paths=image_files,
                conf=conf,
                iou=iou,
                scene_id=scene_id,
                user_id=user_id,
                display_language=display_language,
            )
            batch_result["source"] = "zip"
            batch_result["zip_filename"] = os.path.basename(zip_path)
            batch_result["total_images_in_zip"] = len(image_files)
            return batch_result

        except zipfile.BadZipFile:
            return {"error": f"无效的 ZIP 文件: {zip_path}"}
        except Exception as e:
            logger.error("ZIP 检测异常: %s", str(e), exc_info=True)
            return {"error": f"ZIP 检测失败: {str(e)}"}
        finally:
            # ── 清理临时目录 ──
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def detect_video(
        self,
        video_path: str,
        conf: float = DetectionConfig.conf_threshold,
        iou: float = DetectionConfig.iou_threshold,
        frame_sample_rate: int = 5,
        max_frames: int = 50,
        scene_id: int = None,
        user_id: int = None,
        task_id: int = None,
        display_language: str = "zh",
    ) -> dict:
        """
        视频检测 — 逐帧采样 + YOLO 推理

        处理流程：
        1. OpenCV 打开视频，获取总帧数和 fps
        2. 按 frame_sample_rate 采样关键帧
        3. 对每帧执行 YOLO 推理
        4. 生成标注帧图像（Base64）
        5. 汇总统计结果

        Args:
            video_path: 视频文件路径
            conf: 置信度阈值
            iou: NMS IoU 阈值
            frame_sample_rate: 帧采样间隔（每 N 帧取 1 帧）
            max_frames: 最多处理的关键帧数量（防止视频过长）
            scene_id: 检测场景 ID
            user_id: 操作用户 ID
            task_id: 已创建的检测任务 ID（用于更新进度）

        Returns:
            视频检测结果字典：
            {
                "task_id": int,
                "total_frames": int,          # 视频总帧数
                "processed_frames": int,       # 处理的关键帧数
                "fps": float,                  # 视频原始 fps
                "duration_seconds": float,     # 视频时长（秒）
                "total_objects": int,          # 检测到目标总数
                "class_counts": {...},         # 各类别统计
                "key_frames": [...],           # 关键帧结果列表
                "total_inference_time": float, # 总推理耗时（ms）
            }
        """
        db = SessionLocal()
        cap = None
        video_writer = None
        output_video_path = None
        converted_video_path = None
        source_video_path = None
        source_video_url = None
        try:
            if not 0 <= conf <= 1 or not 0 <= iou <= 1:
                raise ValueError("conf 和 iou 必须在 0 到 1 之间")
            if frame_sample_rate < 1:
                raise ValueError("frame_sample_rate 必须大于 0")
            if not 1 <= max_frames <= 300:
                raise ValueError("max_frames 必须在 1 到 300 之间")

            if task_id:
                task = (
                    db.query(DetectionTask).filter(DetectionTask.id == task_id).first()
                )
                if not task:
                    raise ValueError("视频检测任务不存在")
                scene_id = task.scene_id
            else:
                scene_id = self._resolve_scene_id(db, scene_id)
                if not scene_id:
                    raise ValueError("指定场景不存在或未启用")
                if not user_id:
                    raise ValueError("视频检测需要登录用户")
                task = DetectionTask(
                    user_id=user_id,
                    scene_id=scene_id,
                    task_type="video",
                    status="processing",
                    total_images=0,
                    conf_threshold=conf,
                    iou_threshold=iou,
                )
                db.add(task)
                db.flush()
                task_id = task.id

            # 将原视频统一转为浏览器可播放的 H.264/AAC，再提供给右侧播放器。
            ffmpeg_path = shutil.which("ffmpeg")
            source_upload_path = video_path
            if ffmpeg_path:
                source_video_path = f"{video_path}.source.h264.mp4"
                try:
                    subprocess.run(
                        [
                            ffmpeg_path,
                            "-y",
                            "-i",
                            video_path,
                            "-map",
                            "0:v:0",
                            "-map",
                            "0:a?",
                            "-c:v",
                            "libx264",
                            "-pix_fmt",
                            "yuv420p",
                            "-c:a",
                            "aac",
                            "-movflags",
                            "+faststart",
                            source_video_path,
                        ],
                        check=True,
                        capture_output=True,
                        timeout=120,
                    )
                    source_upload_path = source_video_path
                except (OSError, subprocess.SubprocessError) as exc:
                    logger.warning("原视频转码失败，使用上传原文件: %s", exc)

            try:
                minio_client = MinIOClient()
                source_object_name = f"detections/{task_id}/source_video.mp4"
                source_video_url = minio_client.upload_file(
                    source_object_name, source_upload_path, content_type="video/mp4"
                )
                self._set_video_progress(
                    task_id,
                    1,
                    "原视频已准备完成，正在检测...",
                    source_video_url,
                )
            except Exception as exc:
                logger.warning("原视频上传 MinIO 失败: %s", exc)

            model = self._get_model(scene_id)
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError("无法打开视频文件")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration_seconds = total_frames / fps if fps > 0 else 0
            if total_frames <= 0 or width <= 0 or height <= 0:
                raise ValueError("视频文件中没有可处理的画面")

            logger.info(
                "视频信息: %d×%d, %.1ffps, %d 帧, %.1f 秒",
                width,
                height,
                fps,
                total_frames,
                duration_seconds,
            )

            effective_interval = max(frame_sample_rate, total_frames // max_frames)
            sample_indices = list(range(0, total_frames, effective_interval))
            if len(sample_indices) > max_frames:
                sample_indices = sample_indices[:max_frames]

            if task:
                task.total_images = len(sample_indices)
                db.commit()

            sample_set = set(sample_indices)
            scene_class_names_cn = self._get_scene_class_names_cn(db, scene_id)
            key_frames = []
            total_objects = 0
            total_inference_time = 0
            class_counts = {}
            class_counts_display = {}
            sampled_count = 0
            sampled_frames_seen = 0
            last_detections = []
            seen_track_ids = set()
            fallback_tracks = {}
            next_fallback_track_id = 1
            tracking_enabled = True

            def draw_detections_on_frame(frame, detections):
                return self._draw_detections_on_frame(frame, detections)

            output_tmp = tempfile.NamedTemporaryFile(
                suffix=".mp4", delete=False
            )
            output_video_path = output_tmp.name
            output_tmp.close()

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            video_writer = cv2.VideoWriter(
                output_video_path, fourcc, fps, (width, height)
            )

            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx not in sample_set:
                    if last_detections:
                        annotated_frame = draw_detections_on_frame(frame, last_detections)
                        video_writer.write(annotated_frame)
                    else:
                        video_writer.write(frame)
                    frame_idx += 1
                    continue

                # 采样只减少推理次数，不能直接把每个采样帧的检测数量相加。
                # ByteTrack 会为连续出现的目标保持同一个 track ID，首次出现时立即计数。
                if tracking_enabled:
                    try:
                        results = model.track(
                            source=frame,
                            conf=conf,
                            iou=iou,
                            imgsz=DetectionConfig.image_size,
                            device=DetectionConfig.device,
                            tracker="bytetrack.yaml",
                            persist=True,
                            save=False,
                            verbose=False,
                        )
                    except Exception as exc:
                        tracking_enabled = False
                        logger.warning("视频跟踪器不可用，降级为检测框匹配: %s", exc)
                        results = model.predict(
                            source=frame,
                            conf=conf,
                            iou=iou,
                            imgsz=DetectionConfig.image_size,
                            device=DetectionConfig.device,
                            save=False,
                            verbose=False,
                        )
                else:
                    results = model.predict(
                        source=frame,
                        conf=conf,
                        iou=iou,
                        imgsz=DetectionConfig.image_size,
                        device=DetectionConfig.device,
                        save=False,
                        verbose=False,
                    )

                result = results[0]
                frame_detections = []
                current_fallback_tracks = set()
                if result.boxes is not None and len(result.boxes) > 0:
                    for box in result.boxes:
                        det = self._detection_from_box(
                            box, model, scene_class_names_cn, display_language
                        )
                        native_track_id = None
                        if getattr(box, "id", None) is not None:
                            native_track_id = int(box.id[0])
                        det["track_id"] = native_track_id

                        if native_track_id is not None:
                            identity = f"track:{native_track_id}"
                        else:
                            # 极少数情况下跟踪器没有返回 ID，使用相邻采样帧的
                            # 同类别框做降级匹配，避免同一目标反复计数。
                            identity = None
                            best_iou = 0.3
                            for fallback_id, previous in fallback_tracks.items():
                                if fallback_id in current_fallback_tracks:
                                    continue
                                if previous["class_id"] != det["class_id"]:
                                    continue
                                if sampled_count - previous["sample_index"] > 2:
                                    continue
                                overlap = self._bbox_iou(previous["bbox"], det["bbox"])
                                if overlap >= best_iou:
                                    identity = fallback_id
                                    best_iou = overlap
                            if identity is None:
                                identity = f"fallback:{next_fallback_track_id}"
                                next_fallback_track_id += 1
                            current_fallback_tracks.add(identity)
                            fallback_tracks[identity] = {
                                "class_id": det["class_id"],
                                "bbox": det["bbox"],
                                "sample_index": sampled_count,
                            }

                        is_new_object = identity not in seen_track_ids
                        det["is_new_object"] = is_new_object
                        if is_new_object:
                            seen_track_ids.add(identity)
                            total_objects += 1
                            class_name = det["class_name"]
                            class_counts[class_name] = class_counts.get(class_name, 0) + 1
                            display_name = det["class_name_display"]
                            class_counts_display[display_name] = class_counts_display.get(display_name, 0) + 1
                        frame_detections.append(det)

                last_detections = frame_detections
                sampled_count += 1
                inference_time = float(result.speed.get("inference", 0))
                total_inference_time += inference_time

                annotated_img = draw_detections_on_frame(frame, frame_detections)
                video_writer.write(annotated_img)

                annotated_base64 = None
                frame_annotated_url = None
                if len(key_frames) < 6:
                    _, buffer = cv2.imencode(
                        ".jpg", annotated_img, [cv2.IMWRITE_JPEG_QUALITY, 70]
                    )
                    frame_bytes = buffer.tobytes()
                    annotated_base64 = base64.b64encode(frame_bytes).decode("utf-8")
                    try:
                        minio_client = MinIOClient()
                        frame_annotated_url = minio_client.upload_bytes(
                            f"detections/{task_id}/key_frame_{frame_idx}.jpg",
                            frame_bytes,
                            "image/jpeg",
                        )
                    except Exception as exc:
                        logger.warning("视频关键帧上传 MinIO 失败（不影响检测结果）: %s", exc)

                key_frames.append(
                    {
                        "frame_index": frame_idx,
                        "timestamp": round(frame_idx / fps, 2),
                        "annotated_image_base64": annotated_base64,
                        "annotated_image_url": frame_annotated_url,
                        "object_count": len(frame_detections),
                        "new_object_count": sum(
                            1 for det in frame_detections if det["is_new_object"]
                        ),
                        "detections": frame_detections,
                        "inference_time": round(inference_time, 2),
                    }
                )

                # 数据库只保存每个唯一目标首次出现的记录，避免历史查询再次按帧重复统计。
                for det in frame_detections:
                    if not det["is_new_object"]:
                        continue
                    db_result = DetectionResult(
                        task_id=task_id,
                        image_path=f"frame_{frame_idx}.jpg",
                        annotated_image_url=frame_annotated_url,
                        class_name=det["class_name"],
                        class_name_cn=det.get("class_name_cn"),
                        class_id=det["class_id"],
                        confidence=det["confidence"],
                        bbox=det["bbox"],
                        inference_time=inference_time,
                    )
                    db.add(db_result)

                if task:
                    task.total_objects = total_objects
                    db.commit()

                logger.debug(
                    "视频检测进度: %d 采样帧, 帧号 %d, 当前目标 %d, 新增唯一目标 %d",
                    sampled_count,
                    frame_idx,
                    len(frame_detections),
                    sum(1 for det in frame_detections if det["is_new_object"]),
                )

                sampled_frames_seen += 1
                progress = min(
                    99,
                    max(1, int(sampled_frames_seen * 100 / len(sample_indices))),
                )
                self._set_video_progress(
                    task_id,
                    progress,
                    f"视频处理中，已采样 {sampled_frames_seen}/{len(sample_indices)} 帧",
                    source_video_url,
                )
                frame_idx += 1

            cap.release()
            cap = None
            video_writer.release()
            video_writer = None

            annotated_video_url = None
            upload_video_path = output_video_path
            if ffmpeg_path:
                converted_video_path = f"{output_video_path}.h264.mp4"
                try:
                    subprocess.run(
                        [
                            ffmpeg_path,
                            "-y",
                            "-i",
                            output_video_path,
                            "-c:v",
                            "libx264",
                            "-pix_fmt",
                            "yuv420p",
                            "-movflags",
                            "+faststart",
                            converted_video_path,
                        ],
                        check=True,
                        capture_output=True,
                        timeout=120,
                    )
                    upload_video_path = converted_video_path
                except (OSError, subprocess.SubprocessError) as exc:
                    logger.warning("ffmpeg 转码失败，使用原始 mp4v 视频: %s", exc)
            try:
                minio_client = MinIOClient()
                object_name = f"detections/{task_id}/annotated_video.mp4"
                annotated_video_url = minio_client.upload_file(
                    object_name, upload_video_path, content_type="video/mp4"
                )
                logger.info("标注视频已上传: %s", object_name)
            except Exception as e:
                logger.warning("标注视频上传 MinIO 失败: %s", str(e))

            for path in (output_video_path, converted_video_path):
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except OSError:
                        pass

            if task:
                task.status = "completed"
                task.total_objects = total_objects
                task.total_inference_time = total_inference_time
                task.completed_at = datetime.now()
                db.commit()

            logger.info(
                "视频检测完成: %d 帧处理, %d 关键帧采样, 共 %d 个目标, 总耗时 %.2fms",
                frame_idx,
                len(key_frames),
                total_objects,
                total_inference_time,
            )

            return {
                "task_id": task_id,
                "total_frames": total_frames,
                "processed_frames": sampled_count,
                "sampled_frames": len(sample_indices),
                "frame_sample_rate": frame_sample_rate,
                "fps": round(fps, 2),
                "duration_seconds": round(duration_seconds, 2),
                "video_resolution": {"width": width, "height": height},
                "total_objects": total_objects,
                "class_counts": class_counts,
                "class_counts_display": class_counts_display,
                "key_frames": key_frames,
                "source_video_url": source_video_url,
                "annotated_video_url": annotated_video_url,
                "total_inference_time": round(total_inference_time, 2),
            }

        except Exception as e:
            logger.error("视频检测异常: %s", str(e), exc_info=True)
            db.rollback()
            if task_id:
                task = (
                    db.query(DetectionTask).filter(DetectionTask.id == task_id).first()
                )
                if task:
                    task.status = "failed"
                    task.error_message = str(e)
                    db.commit()
            return {"error": f"视频检测失败: {str(e)}"}
        finally:
            if cap is not None:
                cap.release()
            if video_writer is not None:
                video_writer.release()
            for path in (output_video_path, converted_video_path, source_video_path):
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
            db.close()


# 创建全局单例
detection_service = DetectionService()
