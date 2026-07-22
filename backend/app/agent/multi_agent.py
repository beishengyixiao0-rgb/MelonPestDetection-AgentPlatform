"""
多 Agent 混合调度器（阶段二）— 每个子 Agent 拥有独立工具集

设计思路：
  - Supervisor 分析用户意图，路由到对应的子 Agent
  - 每个子 Agent 只持有自己职责范围内的工具
  - 完全保留现有 SSE 事件协议（thinking/tool_call/tool_result/text_chunk/done）
  - 前端无需任何修改

流程：
  用户消息 → Supervisor 路由 → 选择子 Agent → 子 Agent 用自己的工具处理 → SSE 流式返回

阶段二（当前）：
  - detection → DetectionAgent（4 个检测工具）
  - qa → QAAgent（1 个知识检索工具）
  - analysis → AnalysisAgent（3 个分析工具）
  - general → 直接 LLM 回复（不调用工具）
"""

from typing import AsyncGenerator

from app.agent.analysis_agent import analysis_agent
from app.agent.base_agent import BaseAgent, create_llm
from app.agent.detection_agent import detection_agent
from app.agent.prompts import get_multi_agent_prompt
from app.agent.qa_agent import qa_agent
from app.agent.supervisor import supervisor_route
from app.core.logger import get_logger

logger = get_logger(__name__)

# 子 Agent 注册表
_SUB_AGENTS = {
    "detection": detection_agent,
    "qa": qa_agent,
    "analysis": analysis_agent,
}


def _route_by_keywords(message: str) -> str | None:
    """对高频、低歧义意图做确定性路由，减少 Supervisor LLM 抖动影响。"""
    text = (message or "").lower()
    analysis_keywords = [
        "检测了多少",
        "检测多少",
        "检测次数",
        "检测统计",
        "统计",
        "历史记录",
        "检测历史",
        "最近的检测结果",
        "最近检测",
        "上次检测",
        "上次检测了什么",
        "用户列表",
        "用户清单",
        "有哪些用户",
        "系统用户",
        "所有用户",
        "管理员列表",
        "user list",
        "users",
        "detection stats",
        "detection history",
    ]
    if any(keyword in text for keyword in analysis_keywords):
        return "analysis"

    qa_keywords = [
        "iou",
        "mAP",
        "map50",
        "map50-95",
        "nms",
        "yolo",
        "置信度",
        "召回率",
        "精确率",
        "非极大值抑制",
        "交并比",
        "平均精度",
        "模型训练",
        "训练模型",
        "数据增强",
        "病害防治",
        "怎么防治",
        "如何防治",
        "防治方法",
        "生长周期",
        "生命周期",
        "种植",
        "栽培",
        "采收",
        "成熟",
        "保存",
        "食用",
        "变质",
        "作物",
        "农业",
        "水肥",
        "温度",
        "湿度",
        "检测流程",
        "知识库",
        "growth cycle",
        "life cycle",
        "cultivation",
        "planting",
        "harvest",
        "storage",
        "agriculture",
        "crop",
    ]
    if any(keyword.lower() in text for keyword in qa_keywords):
        return "qa"
    return None


async def multi_agent_chat_stream(
    message: str,
    image_path: str = None,
    image_paths: list[str] | None = None,
    user_id: int | None = None,
    scene_id: int | None = None,
    session_id: str | None = None,
    display_language: str = "zh",
    attachment_urls: list[str] | None = None,
    is_admin: bool = False,
) -> AsyncGenerator:
    """
    多 Agent 流式对话入口（阶段二）。

    1. Supervisor 分析用户意图，决定路由
    2. 根据路由选择子 Agent：
       - detection → DetectionAgent（4 个检测工具）
       - qa → QAAgent（1 个知识检索工具）
       - analysis → AnalysisAgent（3 个分析工具）
       - general → 直接 LLM 回复（不调用工具）
    3. 完全保留现有 SSE 事件协议，前端无需修改
    """
    # ── 第 1 步：Supervisor 路由 ─
    # 附件路径来自 /api/chat/upload，已经是明确的检测意图，不再交给 LLM 猜路由。
    route = (
        "detection"
        if image_path or image_paths
        else _route_by_keywords(message) or await supervisor_route(message, display_language)
    )
    logger.info("多 Agent 路由: %s -> %s", message[:50], route)

    # ── 第 2 步：根据路由分发 ──
    if route == "general":
        # 通用对话：直接 LLM 回复，不走工具
        async for event in _general_stream(
            message, display_language, user_id, session_id
        ):
            yield event
    else:
        # 检测/问答/分析：路由到对应的子 Agent
        agent = _SUB_AGENTS.get(route)
        if agent is None:
            logger.error("未知的路由目标: %s，降级到 general", route)
            async for event in _general_stream(
                message, display_language, user_id, session_id
            ):
                yield event
            return

        async for event in agent.chat_stream(
            message=message,
            image_path=image_path,
            image_paths=image_paths,
            user_id=user_id,
            scene_id=scene_id,
            session_id=session_id,
            display_language=display_language,
            attachment_urls=attachment_urls,
            is_admin=is_admin,
        ):
            yield event


async def _general_stream(
    message: str,
    display_language: str,
    user_id: int | None,
    session_id: str | None,
) -> AsyncGenerator:
    """通用对话流式输出（不调用工具，直接 LLM 回复）。"""
    system_prompt = get_multi_agent_prompt("general", display_language)

    chat_history = []
    if user_id is not None and session_id:
        try:
            from app.agent.memory import conversation_memory
            from app.services.chat_history_service import chat_history_service

            history = conversation_memory.load_history(user_id, session_id)
            if not history:
                history = chat_history_service.get_recent_messages(
                    user_id, session_id, conversation_memory.max_messages
                )
                if history:
                    conversation_memory.replace_history(user_id, session_id, history)
            chat_history = BaseAgent._to_langchain_messages(history)
            BaseAgent._save_history_message(user_id, session_id, "user", message)
        except Exception as e:
            logger.error("加载或保存 General 历史消息失败: %s", e)

    assistant_parts: list[str] = []

    try:
        llm = create_llm()
        async for chunk in llm.astream(
            [
                ("system", system_prompt),
                *chat_history,
                ("human", message),
            ]
        ):
            if hasattr(chunk, "content") and chunk.content:
                assistant_parts.append(chunk.content)
        sanitized_text = BaseAgent._sanitize_model_text(
            "".join(assistant_parts), display_language
        )
        assistant_parts = [sanitized_text] if sanitized_text else []
        if sanitized_text:
            yield {"type": "text_chunk", "content": sanitized_text}
    except Exception as e:
        logger.error("General 流式回复失败: %s", str(e))
        error_msg = (
            f"回复失败：{str(e)}"
            if display_language == "zh"
            else f"Reply failed: {str(e)}"
        )
        yield {"type": "error", "content": error_msg}
        return

    # 保存历史消息（与各子 Agent 保持一致）
    if user_id is not None and session_id and assistant_parts:
        try:
            BaseAgent._save_history_message(
                user_id, session_id, "assistant", "".join(assistant_parts)
            )
        except Exception as e:
            logger.error("保存历史消息失败: %s", e)

    yield {"type": "done", "full_text": "".join(assistant_parts)}
