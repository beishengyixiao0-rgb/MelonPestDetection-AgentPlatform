"""持久化对话会话与消息服务。"""

from datetime import datetime
from uuid import uuid4

from app.database.session import SessionLocal
from app.entity.db_models import ChatMessage, ChatSession


class ChatHistoryService:
    """数据库是长期会话来源，Redis 只保存一小时的活跃上下文。"""

    @staticmethod
    def _session_payload(session: ChatSession) -> dict:
        return {
            "id": session.id,
            "session_uuid": session.session_uuid,
            "title": session.title,
            "status": session.status,
            "message_count": session.message_count or 0,
            "last_message_at": session.last_message_at.isoformat()
            if session.last_message_at
            else None,
            "created_at": session.created_at.isoformat() if session.created_at else None,
        }

    @staticmethod
    def _message_payload(message: ChatMessage) -> dict:
        return {
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "agent_used": message.agent_used,
            "tool_calls": message.tool_calls,
            "tool_result": message.tool_result,
            "latency_ms": message.latency_ms,
            "created_at": message.created_at.isoformat()
            if message.created_at
            else None,
        }

    def ensure_session(self, user_id: int, session_uuid: str | None = None) -> dict | None:
        db = SessionLocal()
        try:
            session_uuid = session_uuid or uuid4().hex
            session = (
                db.query(ChatSession)
                .filter(ChatSession.session_uuid == session_uuid)
                .first()
            )
            if session:
                if session.user_id != user_id:
                    return None
                return self._session_payload(session)

            session = ChatSession(
                user_id=user_id,
                session_uuid=session_uuid,
                status="active",
                message_count=0,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return self._session_payload(session)
        finally:
            db.close()

    def append_message(
        self,
        user_id: int,
        session_uuid: str,
        role: str,
        content: str,
        tool_calls: list[dict] | None = None,
        tool_result: str | None = None,
    ) -> dict | None:
        db = SessionLocal()
        try:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.session_uuid == session_uuid,
                )
                .first()
            )
            if not session:
                return None

            message = ChatMessage(
                session_id=session.id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_result=tool_result,
            )
            db.add(message)
            session.message_count = (session.message_count or 0) + 1
            session.last_message_at = datetime.now()
            if role == "user" and not session.title:
                session.title = content.replace("\n", " ").strip()[:60] or "新会话"
            db.commit()
            db.refresh(message)
            return self._message_payload(message)
        finally:
            db.close()

    def get_recent_messages(
        self, user_id: int, session_uuid: str, limit: int
    ) -> list[dict]:
        db = SessionLocal()
        try:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.session_uuid == session_uuid,
                )
                .first()
            )
            if not session:
                return []
            messages = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .limit(limit)
                .all()
            )
            return [
                {"role": message.role, "content": message.content}
                for message in reversed(messages)
            ]
        finally:
            db.close()

    def list_sessions(self, user_id: int) -> list[dict]:
        db = SessionLocal()
        try:
            sessions = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user_id, ChatSession.status == "active")
                .order_by(ChatSession.last_message_at.desc(), ChatSession.created_at.desc())
                .all()
            )
            return [self._session_payload(session) for session in sessions]
        finally:
            db.close()

    def get_session_history(self, user_id: int, session_uuid: str) -> dict | None:
        db = SessionLocal()
        try:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.session_uuid == session_uuid,
                )
                .first()
            )
            if not session:
                return None
            messages = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
                .all()
            )
            return {
                "session": self._session_payload(session),
                "messages": [self._message_payload(message) for message in messages],
            }
        finally:
            db.close()

    def clear_session(self, user_id: int, session_uuid: str) -> bool:
        db = SessionLocal()
        try:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.session_uuid == session_uuid,
                )
                .first()
            )
            if not session:
                return False
            db.query(ChatMessage).filter(ChatMessage.session_id == session.id).delete()
            session.message_count = 0
            session.last_message_at = None
            db.commit()
            return True
        finally:
            db.close()

    def rename_session(
        self, user_id: int, session_uuid: str, title: str
    ) -> dict | None:
        """更新用户自己的会话标题。"""
        db = SessionLocal()
        try:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.session_uuid == session_uuid,
                )
                .first()
            )
            if not session:
                return None
            session.title = title
            db.commit()
            db.refresh(session)
            return self._session_payload(session)
        finally:
            db.close()

    def delete_session(self, user_id: int, session_uuid: str) -> bool:
        db = SessionLocal()
        try:
            session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.user_id == user_id,
                    ChatSession.session_uuid == session_uuid,
                )
                .first()
            )
            if not session:
                return False
            db.delete(session)
            db.commit()
            return True
        finally:
            db.close()


chat_history_service = ChatHistoryService()
