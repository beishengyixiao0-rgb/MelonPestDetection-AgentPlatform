"""
统计分析工具 — Agent 可调用的数据查询工具

工具列表：
  - query_detection_stats: 查询检测统计数据
  - query_detection_history: 查询检测历史记录
  - query_user_list: 查询系统中的用户列表
"""

import contextvars
import json

from app.core.logger import get_logger
from app.database.session import SessionLocal
from app.entity.db_models import DetectionTask
from langchain_core.tools import tool

logger = get_logger(__name__)

# 工具没有 HTTP 请求对象，使用 ContextVar 在并发 Agent 调用中隔离用户与角色。
_tool_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "analysis_tool_user_id", default=None
)
_tool_is_admin: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "analysis_tool_is_admin", default=False
)


def set_tool_context(user_id: int | None, is_admin: bool):
    """在 Agent 调用分析工具前写入当前用户和管理员身份。"""
    return _tool_user_id.set(user_id), _tool_is_admin.set(is_admin)


def reset_tool_context(tokens) -> None:
    """在请求结束时恢复上下文，避免权限状态泄漏到下一轮调用。"""
    user_token, admin_token = tokens
    _tool_user_id.reset(user_token)
    _tool_is_admin.reset(admin_token)


@tool
def query_detection_stats(days: int = 30) -> str:
    """查询用户的检测统计数据。

    当用户询问"今天检测了多少次"、"最近检测了多少目标"、"检测统计"等统计类问题时使用此工具。

    Args:
        days: 统计最近 N 天的数据，默认 30 天

    Returns:
        JSON 字符串，包含总任务数、总目标数、各类型任务数等统计信息
    """
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import func

        db = SessionLocal()
        try:
            start_date = datetime.now() - timedelta(days=days)
            user_id = _tool_user_id.get()
            if user_id is None:
                return json.dumps(
                    {"error": "未获取到当前用户上下文"}, ensure_ascii=False
                )

            stats = (
                db.query(
                    func.count(DetectionTask.id).label("total_tasks"),
                    func.coalesce(func.sum(DetectionTask.total_objects), 0).label(
                        "total_objects"
                    ),
                    func.coalesce(func.sum(DetectionTask.total_images), 0).label(
                        "total_images"
                    ),
                    func.coalesce(
                        func.avg(DetectionTask.total_inference_time), 0
                    ).label("avg_time"),
                )
                .filter(
                    DetectionTask.user_id == user_id,
                    DetectionTask.created_at >= start_date,
                )
                .first()
            )

            result = {
                "period": f"最近 {days} 天",
                "total_tasks": stats.total_tasks,
                "total_objects": int(stats.total_objects),
                "total_images": int(stats.total_images),
                "avg_inference_time": round(float(stats.avg_time), 2),
            }
            return json.dumps(result, ensure_ascii=False)
        finally:
            db.close()
    except Exception as e:
        logger.error("查询统计失败: %s", str(e))
        return json.dumps({"error": f"查询失败: {str(e)}"}, ensure_ascii=False)


@tool
def query_detection_history(limit: int = 10) -> str:
    """查询最近的检测历史记录。

    当用户询问"最近的检测结果"、"上次检测了什么"、"检测历史"等问题时使用此工具。

    Args:
        limit: 返回最近 N 条记录，默认 10 条

    Returns:
        JSON 字符串，包含最近的检测任务列表（类型、状态、目标数、时间）
    """
    try:
        db = SessionLocal()
        try:
            user_id = _tool_user_id.get()
            if user_id is None:
                return json.dumps(
                    {"error": "未获取到当前用户上下文"}, ensure_ascii=False
                )
            tasks = (
                db.query(DetectionTask)
                .filter(DetectionTask.user_id == user_id)
                .order_by(DetectionTask.created_at.desc())
                .limit(limit)
                .all()
            )

            items = []
            for t in tasks:
                items.append(
                    {
                        "id": t.id,
                        "task_type": t.task_type,
                        "status": t.status,
                        "total_objects": t.total_objects or 0,
                        "total_images": t.total_images or 0,
                        "created_at": t.created_at.isoformat()
                        if t.created_at
                        else None,
                    }
                )

            return json.dumps(
                {"history": items, "count": len(items)}, ensure_ascii=False
            )
        finally:
            db.close()
    except Exception as e:
        logger.error("查询历史失败: %s", str(e))
        return json.dumps({"error": f"查询失败: {str(e)}"}, ensure_ascii=False)


# 分析工具列表
ANALYSIS_TOOLS = [
    query_detection_stats,
    query_detection_history,
]

# ── 追加到 analysis_tool.py 末尾 ──


@tool
def query_user_list(limit: int = 20) -> str:
    """查询系统中的用户列表。

    当用户询问"系统有哪些用户"、"有哪些管理员"、"用户列表"等问题时使用此工具。

    Args:
        limit: 返回最多 N 个用户，默认 20 个

    Returns:
        JSON 字符串，包含用户列表（用户名、邮箱、角色、注册时间）
    """
    try:
        from app.entity.db_models import User, UserRole
        from sqlalchemy.orm import joinedload

        # 用户列表属于系统管理数据，提示词约束不能代替工具执行层权限校验。
        if not _tool_is_admin.get():
            return json.dumps(
                {"error": "仅管理员可查询系统用户列表"}, ensure_ascii=False
            )

        db = SessionLocal()
        try:
            users = (
                db.query(User)
                .options(joinedload(User.user_roles).joinedload(UserRole.role))
                .order_by(User.created_at.desc())
                .limit(max(1, min(limit, 100)))
                .all()
            )

            items = []
            for u in users:
                roles = [ur.role.name for ur in u.user_roles] if u.user_roles else []
                items.append(
                    {
                        "id": u.id,
                        "username": u.username,
                        "email": u.email,
                        "roles": roles,
                        "is_active": u.is_active,
                    }
                )

            return json.dumps({"users": items, "count": len(items)}, ensure_ascii=False)
        finally:
            db.close()
    except Exception as e:
        logger.error("查询用户列表失败: %s", str(e))
        return json.dumps({"error": f"查询失败: {str(e)}"}, ensure_ascii=False)


# 更新分析工具列表
ANALYSIS_TOOLS.append(query_user_list)
