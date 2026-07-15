"""
对话相关 API 路由

接口列表：
  - GET  /api/chat/sessions    获取用户的会话列表
  - GET  /api/chat/sessions/{session_id}/messages  获取会话的消息历史
  - POST /api/chat/upload    上传图片文件，返回服务端路径
  - POST /api/chat/stream    SSE 流式对话（核心接口）
  - DELETE /api/chat/sessions/{session_id}  删除会话

"""

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from app.agent.detection_agent import detection_agent
from app.api.auth import get_current_user
from app.core.logger import get_logger
from app.database.session import get_db
from app.entity.db_models import ChatMessage, ChatSession
from app.services.detection_service import ALLOWED_IMAGE_SUFFIXES
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["智能对话"])

# 上传文件临时存储目录
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "rsod_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/sessions", summary="获取用户的会话列表")
async def get_sessions(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    获取当前用户的所有对话会话列表
    """
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .filter(ChatSession.status == "active")
        .order_by(ChatSession.last_message_at.desc())
        .all()
    )

    return {
        "code": 200,
        "data": [
            {
                "id": session.id,
                "session_uuid": session.session_uuid,
                "title": session.title or "新对话",
                "message_count": session.message_count,
                "last_message_at": session.last_message_at.isoformat()
                if session.last_message_at
                else None,
                "created_at": session.created_at.isoformat(),
            }
            for session in sessions
        ],
    }


@router.get("/sessions/{session_id}/messages", summary="获取会话的消息历史")
async def get_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    获取指定会话的所有消息历史
    """
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id)
        .filter(ChatSession.user_id == current_user.id)
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )

    return {
        "code": 200,
        "data": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "agent_used": message.agent_used,
                "tool_calls": message.tool_calls,
                "tool_result": message.tool_result,
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ],
    }


@router.delete("/sessions/{session_id}", summary="删除会话")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    删除指定会话及其所有消息
    """
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id)
        .filter(ChatSession.user_id == current_user.id)
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    db.delete(session)
    db.commit()

    return {"code": 200, "message": "会话已删除"}


@router.post("/upload", summary="上传图片文件")
async def upload_image(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """
    上传图片文件到服务端临时目录

    Returns:
        { "image_path": "/tmp/rsod_uploads/xxx.jpg" }
    """
    suffix = os.path.splitext(file.filename)[1].lower() or ".jpg"
    if suffix not in ALLOWED_IMAGE_SUFFIXES | {".zip"}:
        raise HTTPException(status_code=400, detail="仅支持图片或 ZIP 文件")
    # 使用原始文件名保存到临时目录
    filename = f"{os.getpid()}_{uuid.uuid4().hex}_{Path(file.filename).name}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info("图片上传成功: %s → %s", file.filename, file_path)
    return {"image_path": file_path}


def _get_or_create_session(db: Session, user_id: int, session_id: int = None):
    """获取或创建会话"""
    if session_id:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            return session

    new_session = ChatSession(
        user_id=user_id,
        session_uuid=str(uuid.uuid4()),
        title=None,
        status="active",
        message_count=0,
        last_message_at=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


def _save_message(db: Session, session_id: int, role: str, content: str, **kwargs):
    """保存消息到数据库"""
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        **kwargs,
    )
    db.add(message)

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session:
        session.message_count = (session.message_count or 0) + 1
        session.last_message_at = datetime.now()
        session.updated_at = datetime.now()

    db.commit()
    db.refresh(message)
    return message


@router.post("/stream")
async def chat_stream(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    SSE 流式对话接口

    请求体：
    {
        "message": "检测这张图片",
        "image_path": "/tmp/uploads/xxx.jpg",  // 单附件（图片或 ZIP）
        "image_paths": ["/tmp/uploads/a.jpg", "/tmp/uploads/b.jpg"],  // 多图附件
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
        raise HTTPException(status_code=400, detail="图片路径无效")
    if image_paths is not None:
        if not isinstance(image_paths, list) or not image_paths:
            raise HTTPException(status_code=400, detail="图片路径列表无效")
        if image_path:
            raise HTTPException(
                status_code=400, detail="不能同时传入 image_path 和 image_paths"
            )
        if any(
            not isinstance(path, str) or not path.startswith(UPLOAD_DIR)
            for path in image_paths
        ):
            raise HTTPException(status_code=400, detail="图片路径无效")

    logger.info(
        "用户 %s 发起对话: message=%s, image=%s",
        current_user.username,
        message[:50],
        "多图" if image_paths else ("有" if image_path else "无"),
    )
    # StreamingResponse 开始执行时，鉴权依赖的数据库 Session 可能已关闭。
    user_id = current_user.id

    # 创建或获取会话
    session = None
    if session_id:
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.id == session_id, ChatSession.user_id == current_user.id
            )
            .first()
        )
    if not session:
        session = ChatSession(
            user_id=current_user.id, title=message[:50], session_uuid=str(uuid.uuid4())
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # 保存用户消息
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=message,
    )
    db.add(user_message)
    session.message_count = (session.message_count or 0) + 1
    session.last_message_at = datetime.now()
    session.updated_at = datetime.now()
    db.commit()
    db.refresh(user_message)

    # ── SSE 流式响应 ──
    async def event_generator():
        nonlocal session
        ai_content = ""
        tool_result_data = None

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

                # 收集 AI 回复内容
                if "content" in event:
                    ai_content += str(event.get("content", ""))

                # 收集工具结果
                if event.get("type") == "tool_result":
                    tool_result_data = str(event.get("result", ""))

            # 保存 AI 回复消息
            if ai_content or tool_result_data:
                db_session = next(get_db())
                try:
                    ai_message = ChatMessage(
                        session_id=session.id,
                        role="assistant",
                        content=ai_content,
                        tool_result=tool_result_data,
                    )
                    db_session.add(ai_message)
                    session_db = (
                        db_session.query(ChatSession)
                        .filter(ChatSession.id == session.id)
                        .first()
                    )
                    if session_db:
                        session_db.message_count = (session_db.message_count or 0) + 1
                        session_db.last_message_at = datetime.now()
                        session_db.updated_at = datetime.now()
                    db_session.commit()
                finally:
                    db_session.close()

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
            "X-Accel-Buffering": "no",
        },
    )
