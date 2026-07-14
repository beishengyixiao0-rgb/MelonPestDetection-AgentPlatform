"""
检测 API 路由 — 快捷检测接口（跳过 LLM，直接调用 YOLO）

接口列表：
  - POST /api/detection/single     单图检测
  - POST /api/detection/batch      批量检测
  - POST /api/detection/zip        ZIP 文件检测
  - POST /api/detection/video      视频检测
  - GET  /api/detection/status/:id 查询任务状态
  - GET  /api/detection/video/status/:id 查询视频检测进度
"""

import os
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.logger import get_logger
from app.database.session import get_db
from app.entity.db_models import DetectionResult, DetectionTask
from app.services.detection_service import ALLOWED_IMAGE_SUFFIXES, detection_service
from app.storage.redis_client import redis_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/detection", tags=["快捷检测"])


def _validate_file(file: UploadFile, suffixes: set[str]) -> None:
    """在保存临时文件前校验客户端文件扩展名。"""
    if Path(file.filename or "").suffix.lower() not in suffixes:
        raise HTTPException(status_code=400, detail="不支持的文件类型")


@router.post("/single", summary="单图检测")
async def detect_single_api(
    file: UploadFile = File(..., description="检测图片"),
    conf: float = Form(0.25, description="置信度阈值"),
    iou: float = Form(0.45, description="NMS IoU 阈值"),
    scene_id: int = Form(None, description="场景 ID"),
    current_user=Depends(get_current_user),
):
    """
    快捷单图检测（跳过 LLM，直接调用 YOLO）
    """
    _validate_file(file, ALLOWED_IMAGE_SUFFIXES)
    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = detection_service.detect_single(
            image_path=tmp_path,
            conf=conf,
            iou=iou,
            scene_id=scene_id,
            user_id=current_user.id,
        )
        result["filename"] = file.filename
        return result
    finally:
        os.unlink(tmp_path)


@router.post("/batch", summary="批量检测")
async def detect_batch_api(
    files: list[UploadFile] = File(..., description="多张图片"),
    conf: float = Form(0.25),
    iou: float = Form(0.45),
    scene_id: int = Form(None),
    current_user=Depends(get_current_user),
):
    """
    快捷批量检测
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一张图片")
    for file in files:
        _validate_file(file, ALLOWED_IMAGE_SUFFIXES)
    temp_paths = []
    try:
        for file in files:
            suffix = os.path.splitext(file.filename)[1] or ".jpg"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                content = await file.read()
                tmp.write(content)
                temp_paths.append(tmp.name)

        result = detection_service.detect_batch(
            image_paths=temp_paths,
            conf=conf,
            iou=iou,
            scene_id=scene_id,
            user_id=current_user.id,
        )
        return result
    finally:
        for path in temp_paths:
            try:
                os.unlink(path)
            except Exception:
                pass


@router.post("/zip", summary="ZIP 文件检测")
async def detect_zip_api(
    file: UploadFile = File(..., description="ZIP 压缩包"),
    conf: float = Form(0.25),
    iou: float = Form(0.45),
    scene_id: int = Form(None),
    current_user=Depends(get_current_user),
):
    """
    快捷 ZIP 检测：解压 ZIP 并批量检测其中所有图片
    """
    _validate_file(file, {".zip"})
    suffix = os.path.splitext(file.filename)[1] or ".zip"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = detection_service.detect_zip(
            zip_path=tmp_path,
            conf=conf,
            iou=iou,
            scene_id=scene_id,
            user_id=current_user.id,
        )
        return result
    finally:
        os.unlink(tmp_path)


@router.get("/status/{task_id}", summary="查询检测任务状态")
async def get_detection_status(
    task_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """查询检测任务状态"""
    task = db.query(DetectionTask).filter(DetectionTask.id == task_id, DetectionTask.user_id == current_user.id).first()
    if not task:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "任务不存在"})
    return {
        "task_id": task.id,
        "status": task.status,
        "task_type": task.task_type,
        "total_images": task.total_images,
        "total_objects": task.total_objects,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@router.post("/video", summary="视频检测")
async def detect_video_api(
    file: UploadFile = File(..., description="视频文件（mp4/avi/mov）"),
    conf: float = Form(0.25, description="置信度阈值"),
    frame_sample_rate: int = Form(5, description="帧采样间隔（每 N 帧取 1 帧）"),
    max_frames: int = Form(50, description="最多处理的关键帧数量"),
    scene_id: int = Form(None, description="场景 ID"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    视频检测：上传视频文件，后台异步处理，通过 status 接口轮询进度

    支持格式：mp4, avi, mov, mkv, wmv, flv
    文件大小限制：50MB
    """
    allowed_video_types = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in allowed_video_types:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": f"不支持的视频格式: {suffix}，"
                f"支持的格式: {', '.join(allowed_video_types)}"
            },
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    logger.info(
        "视频文件已保存: %s (%.2f MB), 用户: %s",
        tmp_path,
        len(content) / (1024 * 1024),
        current_user.username,
    )

    task = DetectionTask(
        user_id=current_user.id,
        scene_id=scene_id or 1,
        task_type="video",
        status="processing",
        conf_threshold=conf,
    )
    db.add(task)
    db.flush()
    task_id = task.id
    db.commit()

    redis_client.set_json(f"video_task:{task_id}", {
        "status": "processing",
        "progress": 0,
        "message": "视频处理中...",
    }, expire=3600)

    def run_video_detection():
        try:
            result = detection_service.detect_video(
                video_path=tmp_path,
                conf=conf,
                frame_sample_rate=frame_sample_rate,
                max_frames=max_frames,
                scene_id=scene_id,
                user_id=current_user.id,
                task_id=task_id,
            )

            if "error" in result:
                redis_client.set_json(f"video_task:{task_id}", {
                    "status": "failed",
                    "progress": 0,
                    "message": result["error"],
                }, expire=3600)
            else:
                redis_client.set_json(f"video_task:{task_id}", {
                    "status": "completed",
                    "progress": 100,
                    "message": f"检测完成，共处理 {result['processed_frames']} 帧，"
                    f"发现 {result['total_objects']} 个目标",
                    "result": result,
                }, expire=3600)
        except Exception as e:
            logger.error("视频后台检测异常: %s", str(e), exc_info=True)
            redis_client.set_json(f"video_task:{task_id}", {
                "status": "failed",
                "progress": 0,
                "message": f"视频检测异常: {str(e)}",
            }, expire=3600)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    thread = threading.Thread(target=run_video_detection, daemon=True)
    thread.start()

    return {
        "task_id": task_id,
        "status": "processing",
        "message": "视频已上传，正在后台处理中，请通过 status 接口轮询进度",
        "filename": file.filename,
    }


@router.get("/video/status/{task_id}", summary="查询视频检测进度")
async def get_video_detection_status(
    task_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    查询视频检测任务的实时进度和结果

    轮询间隔建议：1-2 秒
    """
    progress_info = redis_client.get_json(f"video_task:{task_id}")

    if progress_info:
        return {
            "task_id": task_id,
            **progress_info,
        }

    task = db.query(DetectionTask).filter(DetectionTask.id == task_id).first()
    if not task:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "任务不存在"},
        )

    result = {
        "task_id": task.id,
        "status": task.status,
        "task_type": task.task_type,
        "total_images": task.total_images,
        "total_objects": task.total_objects or 0,
    }

    if task.status == "completed":
        results = (
            db.query(DetectionResult)
            .filter(DetectionResult.task_id == task_id)
            .all()
        )

        class_counts = {}
        for r in results:
            class_counts[r.class_name] = class_counts.get(r.class_name, 0) + 1

        result["class_counts"] = class_counts
        result["total_inference_time"] = task.total_inference_time

    return result
