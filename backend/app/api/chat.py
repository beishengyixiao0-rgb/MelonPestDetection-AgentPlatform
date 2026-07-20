"""
对话相关 API 路由

接口列表：
  - POST /api/chat/upload    上传图片、视频或 ZIP 文件，返回服务端路径
  - POST /api/chat/stream    SSE 流式对话（核心接口）
  - GET  /api/chat/sessions  获取当前用户的会话列表
  - POST /api/chat/sessions  新建空会话
  - GET  /api/chat/sessions/{session_id}     获取指定会话及消息历史
  - PATCH /api/chat/sessions/{session_id}    重命名指定会话
  - DELETE /api/chat/sessions/{session_id}   删除指定会话
  - POST /api/chat/clear     清空指定会话的消息

"""

import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from app.agent.detection_agent import detection_agent
from app.agent.multi_agent import multi_agent_chat_stream
from app.agent.memory import conversation_memory
from app.api.auth import get_current_user
from app.core.language import request_language
from app.core.logger import get_logger
from app.services.chat_history_service import chat_history_service
from app.services.detection_service import ALLOWED_IMAGE_SUFFIXES
from app.storage.minio_client import MinIOClient
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["智能对话"])

ALLOWED_VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}
MAX_VIDEO_UPLOAD_BYTES = 50 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")

class ChatStreamRequest(BaseModel):
    message: str = Field(..., description="用户消息内容", examples=["检测这张图片"])
    image_path: str | None = Field(None, description="单附件路径（图片、视频或 ZIP）", examples=["/tmp/uploads/xxx.jpg"])
    image_paths: list[str] | None = Field(None, description="多个图片附件路径", examples=[["/tmp/uploads/a.jpg", "/tmp/uploads/b.jpg"]])
    session_id: str | int | None = Field(None, description="会话 ID（可选，兼容 UUID 字符串和旧数字 ID）", examples=["4e8e04c0d9494be4a8686bb48b2b144e"])
    attachment_urls: list[str] | None = Field(None, description="附件 URL 列表")
    scene_id: int | None = Field(None, description="场景 ID（可选）", examples=[1])

# 上传文件临时存储目录
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "rsod_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _validated_session_id(session_id) -> str | None:
    """兼容旧调用的数字会话标识，同时拒绝异常路径或超长输入。"""
    if session_id is None:
        return None
    if not isinstance(session_id, (str, int)):
        raise HTTPException(status_code=400, detail="会话 ID 无效")
    value = str(session_id)
    if not SESSION_ID_PATTERN.fullmatch(value):
        raise HTTPException(status_code=400, detail="会话 ID 无效")
    return value


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
                if (
                    suffix in ALLOWED_VIDEO_SUFFIXES
                    and total_size > MAX_VIDEO_UPLOAD_BYTES
                ):
                    raise HTTPException(status_code=400, detail="视频文件不能超过 50MB")
                output.write(chunk)
    except Exception:
        try:
            os.unlink(file_path)
        except OSError:
            pass
        raise

    file_type = (
        "video"
        if suffix in ALLOWED_VIDEO_SUFFIXES
        else "zip"
        if suffix == ".zip"
        else "image"
    )
    # 图片和视频上传后写入对象存储，浏览器刷新时仍可展示原始附件；
    # MinIO 不可用不阻断本轮检测，当前请求仍使用临时文件完成处理。
    attachment_url = None
    if file_type in {"image", "video"}:
        try:
            object_name = (
                f"chat_attachments/{current_user.id}/{uuid.uuid4().hex}{suffix}"
            )
            attachment_url = MinIOClient().upload_file(
                object_name,
                file_path,
                file.content_type
                or ("video/mp4" if file_type == "video" else "image/jpeg"),
            )
        except Exception as exc:
            logger.warning("对话原图上传 MinIO 失败: %s", exc)
    logger.info("对话附件上传成功: %s → %s (%s)", file.filename, file_path, file_type)
    return {
        "image_path": file_path,  # 保留旧客户端字段
        "file_path": file_path,
        "file_type": file_type,
        "filename": file.filename,
        "attachment_url": attachment_url,
    }


@router.post("/stream")
async def chat_stream(
    body: ChatStreamRequest,
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
        "session_id": "4e8e04c0d9494be4a8686bb48b2b144e"  // 可选，会话 ID
    }

    响应：SSE 流式事件
    """
    # SSE 不经过 Axios；从请求头或用户偏好解析本轮 Agent 的回复语言。
    display_language = request_language(request, current_user)
    message = body.message
    image_path = body.image_path
    image_paths = body.image_paths
    attachment_urls = body.attachment_urls or []
    session_id = _validated_session_id(body.session_id)

    if not message:
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    if image_path and not str(image_path).startswith(UPLOAD_DIR):
        raise HTTPException(status_code=400, detail="附件路径无效")
    if image_paths is not None:
        if not isinstance(image_paths, list) or not image_paths:
            raise HTTPException(status_code=400, detail="附件路径列表无效")
        if image_path:
            raise HTTPException(
                status_code=400, detail="不能同时传入 image_path 和 image_paths"
            )
        if any(
            not isinstance(path, str) or not path.startswith(UPLOAD_DIR)
            for path in image_paths
        ):
            raise HTTPException(status_code=400, detail="附件路径无效")
    if not isinstance(attachment_urls, list) or any(
        not isinstance(url, str) for url in attachment_urls
    ):
        raise HTTPException(status_code=400, detail="附件地址无效")

    logger.info(
        "用户 %s 发起对话: message=%s, image=%s",
        current_user.username,
        message[:50],
        "多图" if image_paths else ("有" if image_path else "无"),
    )
    # StreamingResponse 开始执行时，鉴权依赖的数据库 Session 可能已关闭。
    user_id = current_user.id
    # 用户列表属于管理操作，管理员身份必须随本轮 Agent 请求传入工具执行层。
    is_admin = any(
        user_role.role and user_role.role.name == "admin"
        for user_role in current_user.user_roles
    ) or bool(getattr(current_user, "is_superuser", False))
    session = chat_history_service.ensure_session(user_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    session_id = session["session_uuid"]

    # ── SSE 流式响应 ──
    async def event_generator():
        try:
            # 新增事件，不影响既有 text_chunk/tool_call/tool_result 消费逻辑。
            session_data = json.dumps(
                {
                    "type": "session",
                    "session_id": session_id,
                    "title": session.get("title") or "新会话",
                },
                ensure_ascii=False,
            )
            yield f"data: {session_data}\n\n"
            # 使用多 Agent 流式处理（Supervisor 路由 + 子 Agent 执行）
            async for event in multi_agent_chat_stream(
                message=message,
                image_path=image_path,
                image_paths=image_paths,
                user_id=user_id,
                scene_id=body.scene_id,
                session_id=session_id,
                display_language=display_language,
                attachment_urls=attachment_urls,
                is_admin=is_admin,
            ):
                # 将事件序列化为 SSE 格式
                event_data = json.dumps(event, ensure_ascii=False)
                yield f"data: {event_data}\n\n"

            # 流结束标志
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error("SSE 流异常: %s", str(e), exc_info=True)
            error_data = json.dumps(
                {"type": "error", "content": str(e)}, ensure_ascii=False
            )
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


@router.post("/sessions/{session_id}/quick-detection", status_code=201)
async def save_quick_detection(
    session_id: str,
    request: Request,
    current_user=Depends(get_current_user),
):
    """保存快捷检测的附件和结果，使刷新后可重建对话中的结果卡片。"""
    session_id = _validated_session_id(session_id)
    body = await request.json()
    user_content = body.get("user_content")
    assistant_content = body.get("assistant_content")
    detection_result = body.get("detection_result")
    attachments = body.get("attachments", [])
    if not isinstance(user_content, str) or not isinstance(assistant_content, str):
        raise HTTPException(status_code=400, detail="快捷检测消息无效")
    if not isinstance(detection_result, dict) or not isinstance(attachments, list):
        raise HTTPException(status_code=400, detail="快捷检测结果无效")
    if chat_history_service.ensure_session(current_user.id, session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")

    saved_result = detection_result.copy()
    if "annotated_image_base64" in saved_result:
        del saved_result["annotated_image_base64"]
    if saved_result.get("annotated_images"):
        for img in saved_result["annotated_images"]:
            if "annotated_image_base64" in img:
                del img["annotated_image_base64"]

    chat_history_service.append_message(
        current_user.id,
        session_id,
        "user",
        user_content,
        tool_result=json.dumps({"attachments": attachments}, ensure_ascii=False),
    )
    chat_history_service.append_message(
        current_user.id,
        session_id,
        "assistant",
        assistant_content,
        tool_result=json.dumps(saved_result, ensure_ascii=False),
    )
    return {"session_id": session_id}


@router.get("/sessions", summary="获取当前用户的对话会话")
async def list_chat_sessions(current_user=Depends(get_current_user)):
    """返回长期保存的会话列表，Redis 过期不影响列表。"""
    return {"sessions": chat_history_service.list_sessions(current_user.id)}


@router.post("/sessions", status_code=201, summary="新建对话会话")
async def create_chat_session(current_user=Depends(get_current_user)):
    """显式创建空会话，供前端在用户输入第一条消息前切换会话。"""
    session = chat_history_service.ensure_session(current_user.id)
    return session


@router.get("/sessions/{session_id}", summary="获取对话会话历史")
async def get_chat_session(session_id: str, current_user=Depends(get_current_user)):
    session_id = _validated_session_id(session_id)
    history = chat_history_service.get_session_history(current_user.id, session_id)
    if history is None:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return history


@router.post("/clear", summary="清空当前会话消息")
async def clear_chat_session(request: Request, current_user=Depends(get_current_user)):
    body = await request.json()
    session_id = _validated_session_id(body.get("session_id"))
    if not session_id or not chat_history_service.clear_session(
        current_user.id, session_id
    ):
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    conversation_memory.clear_session(current_user.id, session_id)
    return {"message": "会话消息已清空"}


@router.patch("/sessions/{session_id}", summary="重命名对话会话")
async def rename_chat_session(
    session_id: str, request: Request, current_user=Depends(get_current_user)
):
    session_id = _validated_session_id(session_id)
    body = await request.json()
    title = body.get("title")
    if not isinstance(title, str):
        raise HTTPException(status_code=400, detail="会话标题无效")
    title = title.strip()
    if not title or len(title) > 200:
        raise HTTPException(status_code=400, detail="会话标题长度应为 1-200 个字符")
    session = chat_history_service.rename_session(current_user.id, session_id, title)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return session


@router.patch("/sessions/{session_id}/pin", summary="切换会话置顶状态")
async def toggle_pin_session(session_id: str, current_user=Depends(get_current_user)):
    session_id = _validated_session_id(session_id)
    session = chat_history_service.toggle_pin_session(current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return session


@router.delete("/sessions/{session_id}", summary="删除对话会话")
async def delete_chat_session(session_id: str, current_user=Depends(get_current_user)):
    session_id = _validated_session_id(session_id)
    if not chat_history_service.delete_session(current_user.id, session_id):
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    conversation_memory.clear_session(current_user.id, session_id)
    return {"message": "会话已删除"}
