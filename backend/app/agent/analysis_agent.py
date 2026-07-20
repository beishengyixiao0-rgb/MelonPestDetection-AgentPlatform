"""
分析子 Agent — 只负责数据统计和历史查询，持有 3 个分析工具
"""

import json

from app.agent.base_agent import BaseAgent
from app.agent.tools.analysis_tool import (
    ANALYSIS_TOOLS,
    query_detection_history,
    reset_tool_context,
    set_tool_context,
)


def _analysis_context_setup(user_id, scene_id, display_language, is_admin):
    """设置分析工具的上下文（用户 ID 和管理员身份）。"""
    return set_tool_context(user_id, is_admin)


def _analysis_context_teardown(tokens):
    """清理分析工具的上下文。"""
    reset_tool_context(tokens)


class AnalysisAgent(BaseAgent):
    """数据分析子 Agent，持有 query_detection_stats、query_detection_history、query_user_list 工具。"""

    AGENT_NAME = "analysis"
    TOOLS = ANALYSIS_TOOLS
    PROMPT_KEY = "analysis_sub"

    @staticmethod
    def _is_recent_history_query(message: str) -> bool:
        text = (message or "").lower()
        keywords = [
            "最近的检测结果",
            "最近检测结果",
            "最近检测",
            "检测历史",
            "历史记录",
            "上次检测",
            "上次检测了什么",
            "recent detection",
            "detection history",
        ]
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _format_history_result(serialized_result: str, display_language: str) -> str:
        try:
            data = json.loads(serialized_result)
        except json.JSONDecodeError:
            return serialized_result

        if data.get("error"):
            return (
                f"查询失败：{data['error']}"
                if display_language == "zh"
                else f"Query failed: {data['error']}"
            )

        history = data.get("history") or []
        if not history:
            return (
                "最近没有检测记录。"
                if display_language == "zh"
                else "No recent detection records found."
            )

        if display_language == "en":
            lines = [f"Found {len(history)} recent detection record(s):"]
            for item in history:
                lines.append(
                    "- "
                    f"Task #{item.get('id')}: {item.get('task_type')} / {item.get('status')}, "
                    f"{item.get('total_images', 0)} image(s), "
                    f"{item.get('total_objects', 0)} object(s), "
                    f"time: {item.get('created_at') or '-'}"
                )
            return "\n".join(lines)

        lines = [f"最近 {len(history)} 条检测记录："]
        type_labels = {
            "single": "单图检测",
            "batch": "批量检测",
            "zip": "ZIP 检测",
            "video": "视频检测",
            "camera": "摄像头检测",
        }
        status_labels = {
            "pending": "等待中",
            "processing": "处理中",
            "completed": "已完成",
            "failed": "失败",
        }
        for item in history:
            task_type = type_labels.get(item.get("task_type"), item.get("task_type") or "-")
            status = status_labels.get(item.get("status"), item.get("status") or "-")
            lines.append(
                "- "
                f"任务 #{item.get('id')}：{task_type} / {status}，"
                f"{item.get('total_images', 0)} 张图，"
                f"{item.get('total_objects', 0)} 个目标，"
                f"时间：{item.get('created_at') or '-'}"
            )
        return "\n".join(lines)

    async def chat_stream(self, message, image_path=None, image_paths=None, user_id=None, scene_id=None, session_id=None, display_language="zh", attachment_urls=None, is_admin=False):
        """重写 chat_stream，注入分析工具的上下文设置。"""
        if self._is_recent_history_query(message):
            if user_id is not None and session_id:
                self._save_history_message(user_id, session_id, "user", message)

            thinking_msg = (
                "Querying recent detection history..."
                if display_language == "en"
                else "正在查询最近的检测历史..."
            )
            yield {"type": "thinking", "content": thinking_msg}
            yield {
                "type": "tool_call",
                "tool": "query_detection_history",
                "input": {"limit": 5},
            }

            tokens = set_tool_context(user_id, is_admin)
            try:
                serialized_result = query_detection_history.invoke({"limit": 5})
            finally:
                reset_tool_context(tokens)

            yield {
                "type": "tool_result",
                "tool": "query_detection_history",
                "result": serialized_result,
            }
            assistant_text = self._format_history_result(
                serialized_result, display_language
            )
            yield {"type": "text_chunk", "content": assistant_text}

            if user_id is not None and session_id:
                self._save_history_message(
                    user_id,
                    session_id,
                    "assistant",
                    assistant_text,
                    tool_calls=[
                        {
                            "tool": "query_detection_history",
                            "input": {"limit": 5},
                        }
                    ],
                    tool_result=serialized_result,
                )
            yield {"type": "done", "full_text": assistant_text}
            return

        async for event in super().chat_stream(
            message=message,
            image_path=image_path,
            image_paths=image_paths,
            user_id=user_id,
            scene_id=scene_id,
            session_id=session_id,
            display_language=display_language,
            attachment_urls=attachment_urls,
            is_admin=is_admin,
            extra_context_setup=_analysis_context_setup,
            extra_context_teardown=_analysis_context_teardown,
        ):
            yield event


analysis_agent = AnalysisAgent()
