"""
分析子 Agent — 只负责数据统计和历史查询，持有 3 个分析工具
"""

from app.agent.base_agent import BaseAgent
from app.agent.tools.analysis_tool import (
    ANALYSIS_TOOLS,
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

    async def chat_stream(self, message, image_path=None, image_paths=None, user_id=None, scene_id=None, session_id=None, display_language="zh", attachment_urls=None, is_admin=False):
        """重写 chat_stream，注入分析工具的上下文设置。"""
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
