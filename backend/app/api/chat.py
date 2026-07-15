"""
对话相关 API 路由

接口列表：
  - POST /api/chat/upload    上传图片、视频或 ZIP 文件，返回服务端路径
  - POST /api/chat/stream    SSE 流式对话（核心接口）

"""

import json
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.agent.detection_agent import detection_agent
from app.api.auth import get_current_user
from app.core.logger import get_logger
from app.services.detection_service import ALLOWED_IMAGE_SUFFIXES

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["智能对话"])

ALLOWED_VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}
MAX_VIDEO_UPLOAD_BYTES = 50 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024

# 上传文件临时存储目录
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "rsod_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", summary="上传对话附件")
async def upload_image(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """
    上传图片、视频或 ZIP 文件到服务端临时目录。

    Returns:
        {
            "image_path": "/tmp/rsod_uploads/xxx.jpg",
            "file_path": "/tmp/rsod_uploads/xxx.jpg",
            "file_type": "image"
        }
    """
    suffix = os.path.splitext(file.filename)[1].lower() or ".jpg"
    allowed_suffixes = ALLOWED_IMAGE_SUFFIXES | {".zip"} | ALLOWED_VIDEO_SUFFIXES
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="仅支持图片、视频或 ZIP 文件")
    # 使用原始文件名保存到临时目录
    filename = f"{os.getpid()}_{uuid.uuid4().hex}_{Path(file.filename).name}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    total_size = 0
    try:
        with open(file_path, "wb") as output:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                total_size += len(chunk)
                if suffix in ALLOWED_VIDEO_SUFFIXES and total_size > MAX_VIDEO_UPLOAD_BYTES:
                    raise HTTPException(status_code=400, detail="视频文件不能超过 50MB")
                output.write(chunk)
    except Exception:
        try:
            os.unlink(file_path)
        except OSError:
            pass
        raise

    file_type = "video" if suffix in ALLOWED_VIDEO_SUFFIXES else "zip" if suffix == ".zip" else "image"
    logger.info("对话附件上传成功: %s → %s (%s)", file.filename, file_path, file_type)
    return {
        "image_path": file_path,  # 保留旧客户端字段
        "file_path": file_path,
        "file_type": file_type,
        "filename": file.filename,
    }


@router.post("/stream")
async def chat_stream(
    request: Request,
    current_user=Depends(get_current_user),
):
    """
    SSE 流式对话接口

    请求体：
    {
        "message": "检测这张图片",
        "image_path": "/tmp/uploads/xxx.jpg",  // 单附件（图片、视频或 ZIP）
        "image_paths": ["/tmp/uploads/a.jpg", "/tmp/uploads/b.jpg"],  // 多个图片附件
        "session_id": 123                        // 可选，会话 ID
    }

    响应：SSE 流式事件
    """
    # ── 解析请求体 ──
    body = await request.json()
    message = body.get("message", "")
    image_path = body.get("image_path")
    image_paths = body.get("image_paths")
    session_id = body.get("session_id")

    if not message:
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    if image_path and not str(image_path).startswith(UPLOAD_DIR):
        raise HTTPException(status_code=400, detail="附件路径无效")
    if image_paths is not None:
        if not isinstance(image_paths, list) or not image_paths:
            raise HTTPException(status_code=400, detail="附件路径列表无效")
        if image_path:
            raise HTTPException(status_code=400, detail="不能同时传入 image_path 和 image_paths")
        if any(not isinstance(path, str) or not path.startswith(UPLOAD_DIR) for path in image_paths):
            raise HTTPException(status_code=400, detail="附件路径无效")

    logger.info(
        "用户 %s 发起对话: message=%s, image=%s",
        current_user.username,
        message[:50],
        "多图" if image_paths else ("有" if image_path else "无"),
    )
    # StreamingResponse 开始执行时，鉴权依赖的数据库 Session 可能已关闭。
    user_id = current_user.id

    # ── SSE 流式响应 ──
    async def event_generator():
        try:
            # 使用 Agent 流式处理
            async for event in detection_agent.chat_stream(
                message=message,
                image_path=image_path,
                image_paths=image_paths,
                user_id=user_id,
                scene_id=body.get("scene_id"),
            ):
                # 将事件序列化为 SSE 格式
                event_data = json.dumps(event, ensure_ascii=False)
                yield f"data: {event_data}\n\n"

            # 流结束标志
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error("SSE 流异常: %s", str(e), exc_info=True)
            error_data = json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁止 Nginx 缓冲 SSE
        },
    )
