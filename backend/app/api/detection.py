"""
检测 API 路由 — 快捷检测接口（跳过 LLM，直接调用 YOLO）

接口列表：
  - POST      /api/detection/single                 单图检测
  - POST      /api/detection/batch                  批量检测
  - POST      /api/detection/zip                    ZIP 文件检测
  - GET       /api/detection/status/{task_id}       查询图片/ZIP 检测任务状态
  - POST      /api/detection/video                  视频检测
  - GET       /api/detection/video/status/{task_id} 查询视频检测进度
  - WebSocket /api/detection/camera                 摄像头实时检测
"""

import asyncio
import base64  # 【新增】Base64 编解码
import os
import tempfile
import threading
import time  # 【新增】时间计算
from pathlib import Path

import cv2
from app.api.auth import get_current_user
from app.config.detection import DetectionConfig
from app.core.language import normalize_language, request_language
from app.core.security import decode_access_token
from app.core.logger import get_logger
from app.database.session import get_db
from app.entity.db_models import DetectionResult, DetectionTask, User
from app.services.detection_service import ALLOWED_IMAGE_SUFFIXES, detection_service
from app.storage.redis_client import redis_client
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse
from jose import JWTError
import numpy as np
from sqlalchemy.orm import Session
import torch

logger = get_logger(__name__)

router = APIRouter(prefix="/api/detection", tags=["快捷检测"])
MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024
VIDEO_UPLOAD_CHUNK_SIZE = 1024 * 1024


def _validate_file(file: UploadFile, suffixes: set[str]) -> None:
    """在保存临时文件前校验客户端文件扩展名。"""
    if Path(file.filename or "").suffix.lower() not in suffixes:
        raise HTTPException(status_code=400, detail="不支持的文件类型")


async def _save_video_upload(file: UploadFile, suffix: str) -> tuple[str, int]:
    """分块保存上传视频，避免将任意大小的文件一次性读入内存。"""
    tmp_path = None
    total_size = 0
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
            while chunk := await file.read(VIDEO_UPLOAD_CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > MAX_VIDEO_SIZE_BYTES:
                    raise HTTPException(status_code=400, detail="视频文件不能超过 50MB")
                tmp.write(chunk)
        return tmp_path, total_size
    except Exception:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


@router.post("/single", summary="单图检测")
async def detect_single_api(
    request: Request,
    file: UploadFile = File(..., description="检测图片"),
    conf: float = Form(DetectionConfig.conf_threshold, description="置信度阈值"),
    iou: float = Form(DetectionConfig.iou_threshold, description="NMS IoU 阈值"),
    scene_id: int = Form(None, description="场景 ID"),
    current_user=Depends(get_current_user),
):
    """
    快捷单图检测（跳过 LLM，直接调用 YOLO）
    """
    # 请求头优先，未提供时自动使用该用户保存的语言偏好。
    display_language = request_language(request, current_user)
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
            **({"display_language": display_language} if display_language != "zh" else {}),
        )
        result["filename"] = file.filename
        return result
    finally:
        os.unlink(tmp_path)


@router.post("/batch", summary="批量检测")
async def detect_batch_api(
    request: Request,
    files: list[UploadFile] = File(..., description="多张图片"),
    conf: float = Form(DetectionConfig.conf_threshold),
    iou: float = Form(DetectionConfig.iou_threshold),
    scene_id: int = Form(None),
    current_user=Depends(get_current_user),
):
    """
    快捷批量检测
    """
    # 请求头优先，未提供时自动使用该用户保存的语言偏好。
    display_language = request_language(request, current_user)
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
            **({"display_language": display_language} if display_language != "zh" else {}),
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
    request: Request,
    file: UploadFile = File(..., description="ZIP 压缩包"),
    conf: float = Form(DetectionConfig.conf_threshold),
    iou: float = Form(DetectionConfig.iou_threshold),
    scene_id: int = Form(None),
    current_user=Depends(get_current_user),
):
    """
    快捷 ZIP 检测：解压 ZIP 并批量检测其中所有图片
    """
    # 请求头优先，未提供时自动使用该用户保存的语言偏好。
    display_language = request_language(request, current_user)
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
            **({"display_language": display_language} if display_language != "zh" else {}),
        )
        return result
    finally:
        os.unlink(tmp_path)


@router.get("/status/{task_id}", summary="查询检测任务状态")
async def get_detection_status(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """查询检测任务状态"""
    # 状态查询也按当前界面语言重新生成类别显示名。
    display_language = request_language(request, current_user)
    task = (
        db.query(DetectionTask)
        .filter(DetectionTask.id == task_id, DetectionTask.user_id == current_user.id)
        .first()
    )
    if not task:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"error": "任务不存在"}
        )
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
    request: Request,
    file: UploadFile = File(..., description="视频文件（mp4/avi/mov）"),
    conf: float = Form(DetectionConfig.conf_threshold, description="置信度阈值"),
    iou: float = Form(DetectionConfig.iou_threshold, description="NMS IoU 阈值"),
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
    # 视频后台任务在启动时取得语言快照，用于标注帧和统计结果。
    display_language = request_language(request, current_user)
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

    if not 0 <= conf <= 1 or not 0 <= iou <= 1:
        raise HTTPException(status_code=400, detail="conf 和 iou 必须在 0 到 1 之间")
    if frame_sample_rate < 1:
        raise HTTPException(status_code=400, detail="frame_sample_rate 必须大于 0")
    if not 1 <= max_frames <= 300:
        raise HTTPException(status_code=400, detail="max_frames 必须在 1 到 300 之间")

    resolved_scene_id = detection_service._resolve_scene_id(db, scene_id)
    if not resolved_scene_id:
        raise HTTPException(status_code=400, detail="指定场景不存在或未启用")

    tmp_path, file_size = await _save_video_upload(file, suffix)
    user_id = current_user.id

    logger.info(
        "视频文件已保存: %s (%.2f MB), 用户: %s",
        tmp_path,
        file_size / (1024 * 1024),
        current_user.username,
    )

    try:
        task = DetectionTask(
            user_id=user_id,
            scene_id=resolved_scene_id,
            task_type="video",
            status="processing",
            conf_threshold=conf,
            iou_threshold=iou,
        )
        db.add(task)
        db.flush()
        task_id = task.id
        db.commit()
    except Exception:
        db.rollback()
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    redis_client.set_json(
        f"video_task:{task_id}",
        {
            "status": "processing",
            "progress": 0,
            "message": "视频处理中...",
        },
        expire=3600,
    )

    def run_video_detection():
        try:
            result = detection_service.detect_video(
                video_path=tmp_path,
                conf=conf,
                iou=iou,
                frame_sample_rate=frame_sample_rate,
                max_frames=max_frames,
                scene_id=resolved_scene_id,
                user_id=user_id,
                task_id=task_id,
                **({"display_language": display_language} if display_language != "zh" else {}),
            )

            if "error" in result:
                redis_client.set_json(
                    f"video_task:{task_id}",
                    {
                        "status": "failed",
                        "progress": 0,
                        "message": result["error"],
                    },
                    expire=3600,
                )
            else:
                redis_client.set_json(
                    f"video_task:{task_id}",
                    {
                        "status": "completed",
                        "progress": 100,
                        "message": f"检测完成，共处理 {result['processed_frames']} 帧，"
                        f"发现 {result['total_objects']} 个目标",
                        "result": result,
                    },
                    expire=3600,
                )
        except Exception as e:
            logger.error("视频后台检测异常: %s", str(e), exc_info=True)
            redis_client.set_json(
                f"video_task:{task_id}",
                {
                    "status": "failed",
                    "progress": 0,
                    "message": f"视频检测异常: {str(e)}",
                },
                expire=3600,
            )
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
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    查询视频检测任务的实时进度和结果

    轮询间隔建议：1-2 秒
    """
    # 轮询时按当前界面语言格式化数据库中的原始类别名。
    display_language = request_language(request, current_user)
    task = (
        db.query(DetectionTask)
        .filter(DetectionTask.id == task_id, DetectionTask.user_id == current_user.id)
        .first()
    )
    if not task:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "任务不存在"},
        )

    progress_info = redis_client.get_json(f"video_task:{task_id}")
    if progress_info:
        return {"task_id": task_id, **progress_info}

    result = {
        "task_id": task.id,
        "status": task.status,
        "task_type": task.task_type,
        "total_images": task.total_images,
        "total_objects": task.total_objects or 0,
    }

    if task.status == "completed":
        results = (
            db.query(DetectionResult).filter(DetectionResult.task_id == task_id).all()
        )

        class_counts = {}
        class_counts_display = {}
        for r in results:
            class_counts[r.class_name] = class_counts.get(r.class_name, 0) + 1
            display_name = DetectionConfig.display_class_name(
                r.class_name, display_language=display_language
            )
            class_counts_display[display_name] = class_counts_display.get(display_name, 0) + 1

        result["class_counts"] = class_counts
        result["class_counts_display"] = class_counts_display
        result["total_inference_time"] = task.total_inference_time

    return result

# ── 单帧缓冲区（CPU 模式优化）──
# 键为 WebSocket 连接 ID，值为最新帧数据
_camera_frame_buffer = {}
MAX_CAMERA_FRAME_BYTES = 2 * 1024 * 1024


async def _authenticate_camera_websocket(
    websocket: WebSocket, db: Session
) -> int | None:
    """验证 WebSocket query 参数中的 JWT，并拒绝已禁用账户。"""
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=1008, reason="缺少认证 Token")
        return None

    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        await websocket.close(code=1008, reason="认证失败")
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        await websocket.close(code=1008, reason="账户不存在或已被禁用")
        return None
    return user.id


@router.websocket("/camera")
async def camera_detection_ws(
    websocket: WebSocket, db: Session = Depends(get_db)
):
    """
    摄像头实时检测 WebSocket 接口

    通信协议：
      前端发送：
        - {"type": "config", "mode": "cpu/gpu", "conf": 0.5}   初始化配置
        - {"type": "frame", "data": "<base64>"}                 发送帧
        - {"type": "close"}                                     关闭连接

      后端返回：
        - {"type": "result", "annotated_frame": "<base64>", ...}  标注帧 + 统计
        - {"type": "error", "message": "..."}                     错误信息
    """
    user_id = await _authenticate_camera_websocket(websocket, db)
    if user_id is None:
        return

    await websocket.accept()
    # WebSocket 不能携带普通自定义请求头，从查询参数读取语言。
    display_language = normalize_language(websocket.query_params.get("display_language"))
    connection_id = id(websocket)
    logger.info(
        "摄像头 WebSocket 连接建立: connection_id=%d, user_id=%d",
        connection_id,
        user_id,
    )

    # ── 默认配置 ──
    mode = "cpu"  # cpu 或 gpu
    conf = DetectionConfig.conf_threshold
    iou = DetectionConfig.iou_threshold
    scene_id = None
    model = None

    # ── 帧处理状态 ──
    last_frame_time = 0
    frame_count = 0
    fps_start_time = time.time()
    fps_frame_count = 0

    try:
        while True:
            # 接收前端消息
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # ── 处理配置消息 ──
            if msg_type == "config":
                mode = data.get("mode", "cpu")
                conf = data.get("conf", DetectionConfig.conf_threshold)
                iou = data.get("iou", DetectionConfig.iou_threshold)
                scene_id = data.get("scene_id")
                display_language = normalize_language(
                    data.get("display_language", display_language)
                )

                if mode not in {"cpu", "gpu"}:
                    await websocket.send_json(
                        {"type": "error", "message": "mode 只能是 cpu 或 gpu"}
                    )
                    continue
                if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
                    await websocket.send_json(
                        {"type": "error", "message": "conf 必须在 0 到 1 之间"}
                    )
                    continue
                if not isinstance(iou, (int, float)) or not 0 <= iou <= 1:
                    await websocket.send_json(
                        {"type": "error", "message": "iou 必须在 0 到 1 之间"}
                    )
                    continue
                if mode == "gpu" and not torch.cuda.is_available():
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "当前服务器没有可用 CUDA GPU，请切换 CPU 模式",
                        }
                    )
                    continue

                # 复用 WebSocket 依赖注入的会话，避免重复创建会话并保持鉴权上下文一致。
                scene_id = detection_service._resolve_scene_id(db, scene_id)
                if not scene_id:
                    await websocket.send_json(
                        {"type": "error", "message": "指定场景不存在或未启用"}
                    )
                    continue
                scene_class_names_cn = detection_service._get_scene_class_names_cn(db, scene_id)

                # 加载模型（指定设备）
                device = "cpu" if mode == "cpu" else "0"
                try:
                    model = detection_service._get_model(scene_id)

                    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    await asyncio.to_thread(
                        model.predict,
                        source=dummy_frame,
                        conf=conf,
                        iou=iou,
                        imgsz=640,
                        device=device,
                        save=False,
                        verbose=False,
                    )
                    logger.info("摄像头模型预热完成, 模式: %s", mode)
                except Exception as e:
                    logger.error("模型加载失败: %s", str(e))
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"模型加载失败: {str(e)}",
                        }
                    )
                    continue

                await websocket.send_json(
                    {
                        "type": "config_ok",
                        "mode": mode,
                        "scene_id": scene_id,
                        "message": f"配置成功，模式: {mode}",
                    }
                )

            # ── 处理帧数据 ──
            elif msg_type == "frame":
                if model is None:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "请先发送 config 消息初始化模型",
                        }
                    )
                    continue

                frame_b64 = data.get("data", "")
                if not frame_b64:
                    continue
                if not isinstance(frame_b64, str) or len(frame_b64) > (
                    MAX_CAMERA_FRAME_BYTES * 4 // 3
                ):
                    await websocket.send_json(
                        {"type": "error", "message": "摄像头帧数据过大"}
                    )
                    continue

                # CPU 模式下始终以最新帧覆盖缓冲区，避免慢推理时内存堆积。
                _camera_frame_buffer[connection_id] = frame_b64
                frame_b64 = _camera_frame_buffer.pop(connection_id)

                try:
                    img_bytes = base64.b64decode(frame_b64, validate=True)
                    if len(img_bytes) > MAX_CAMERA_FRAME_BYTES:
                        await websocket.send_json(
                            {"type": "error", "message": "摄像头帧解码后过大"}
                        )
                        continue
                    nparr = np.frombuffer(img_bytes, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if frame is None:
                        continue

                    device = "cpu" if mode == "cpu" else "0"
                    imgsz = 416 if mode == "cpu" else 640

                    results = await asyncio.to_thread(
                        model.predict,
                        source=frame,
                        conf=conf,
                        iou=iou,
                        imgsz=imgsz,
                        device=device,
                        save=False,
                        verbose=False,
                        half=False,
                    )
                    result = results[0]
                    inference_time = float(result.speed.get("inference", 0))

                    detections = []
                    if result.boxes is not None and len(result.boxes) > 0:
                        for box in result.boxes:
                            detections.append(
                                detection_service._detection_from_box(
                                    box, model, scene_class_names_cn, display_language
                                )
                            )

                    annotated_img = detection_service._draw_detections_on_frame(
                        frame, detections
                    )
                    _, buffer = cv2.imencode(
                        ".jpg", annotated_img, [cv2.IMWRITE_JPEG_QUALITY, 70]
                    )
                    annotated_b64 = base64.b64encode(buffer).decode("utf-8")

                    fps_frame_count += 1
                    elapsed = time.time() - fps_start_time
                    if elapsed >= 1.0:
                        current_fps = fps_frame_count / elapsed
                        fps_frame_count = 0
                        fps_start_time = time.time()
                    else:
                        current_fps = 0

                    frame_count += 1

                    await websocket.send_json(
                        {
                            "type": "result",
                            "annotated_frame": annotated_b64,
                            "detections": detections,
                            "object_count": len(detections),
                            "inference_time": round(inference_time, 2),
                            "fps": round(current_fps, 1),
                            "frame_count": frame_count,
                        }
                    )

                except Exception as e:
                    logger.error("摄像头帧处理异常: %s", str(e))
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"帧处理失败: {str(e)}",
                        }
                    )

            # ── 处理关闭消息 ──
            elif msg_type == "close":
                logger.info(
                    "摄像头 WebSocket 主动关闭: connection_id=%d", connection_id
                )
                break

    except WebSocketDisconnect:
        logger.info("摄像头 WebSocket 断开: connection_id=%d", connection_id)
    except Exception as e:
        logger.error("摄像头 WebSocket 异常: %s", str(e), exc_info=True)
    finally:
        # 清理资源
        _camera_frame_buffer.pop(connection_id, None)
        logger.info(
            "摄像头 WebSocket 关闭, 共处理 %d 帧: connection_id=%d",
            frame_count,
            connection_id,
        )
