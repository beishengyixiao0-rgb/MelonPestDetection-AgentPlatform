"""
检测 API 路由 — 快捷检测接口（跳过 LLM，直接调用 YOLO）

接口列表：
  - POST /api/detection/single     单图检测
  - POST /api/detection/batch      批量检测
  - POST /api/detection/zip        ZIP 文件检测
  - GET  /api/detection/status/:id 查询任务状态
"""

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.logger import get_logger
from app.database.session import get_db
from app.entity.db_models import DetectionTask
from app.services.detection_service import ALLOWED_IMAGE_SUFFIXES, detection_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/detection", tags=["快捷检测"])


def _validate_file(file: UploadFile, suffixes: set[str]) -> None:
    """在指导书保存临时文件前校验客户端文件扩展名。"""
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
    try:
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
    finally:
        # get_db 会负责关闭连接；保留 finally 结构以对应指导书的资源释放语义。
        pass
