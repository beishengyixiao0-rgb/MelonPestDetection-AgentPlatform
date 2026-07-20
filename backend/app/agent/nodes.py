"""
多 Agent 节点函数 — 每个节点对应一个子 Agent

节点列表：
  - supervisor_node: Supervisor 路由决策
  - detection_node: 检测子 Agent（调用检测工具）
  - qa_node: 问答子 Agent（调用知识工具）
  - analysis_node: 分析子 Agent（调用统计工具）
  - general_node: 通用对话（直接回复，不调用工具）

设计原则：
  - 每个节点接收 AgentState，返回更新后的 State
  - 节点之间通过 State 传递信息，不直接调用
  - 保留现有的 SSE 流式输出能力
"""

import json

from app.agent.detection_agent import detection_agent, create_llm
from app.agent.prompts import get_multi_agent_prompt
from app.agent.state import AgentState
from app.agent.supervisor import supervisor_route
from app.agent.tools.analysis_tool import (
    ANALYSIS_TOOLS,
    reset_tool_context,
    set_tool_context,
)
from app.agent.tools.detection_tool import (
    DETECTION_TOOLS,
    reset_detection_tool_context,
    set_detection_tool_context,
)
from app.agent.tools.knowledge_tool import KNOWLEDGE_TOOLS
from app.core.logger import get_logger

logger = get_logger(__name__)


async def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor 节点：分析用户意图，决定路由到哪个子 Agent。

    更新字段：
      - next_agent: 路由目标（detection / qa / analysis / general）
      - current_iteration: 迭代计数 +1
    """
    user_input = state.get("user_input", "")
    display_language = state.get("display_language", "zh")

    next_agent = await supervisor_route(user_input, display_language)
    current_iteration = state.get("current_iteration", 0) + 1

    logger.info("Supervisor 决策: %s → %s (迭代 %d)", user_input[:50], next_agent, current_iteration)

    return {"next_agent": next_agent, "current_iteration": current_iteration}


async def detection_node(state: AgentState) -> dict:
    """
    检测子 Agent 节点：处理图片/视频检测任务。

    复用现有 detection_agent.chat()，传入检测相关消息。
    """
    user_input = state.get("user_input", "")
    display_language = state.get("display_language", "zh")
    attachment_paths = state.get("attachment_paths", [])
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    scene_id = state.get("scene_id")

    # 构造带附件路径的消息
    message = user_input
    if attachment_paths:
        if len(attachment_paths) == 1:
            from app.agent.detection_agent import _is_video_path
            is_video = _is_video_path(attachment_paths[0])
            if display_language == "en":
                label = "video" if is_video else "image"
                message += f"\n[attachment {label} path: {attachment_paths[0]}]"
            else:
                label = "视频" if is_video else "图片"
                message += f"\n[附件{label}路径: {attachment_paths[0]}]"
        else:
            paths_json = json.dumps(attachment_paths, ensure_ascii=False)
            if display_language == "en":
                message += f"\n[attachment image path list: {paths_json}]"
            else:
                message += f"\n[附件图片路径列表: {paths_json}]"

    detection_context_tokens = set_detection_tool_context(user_id, scene_id, display_language)

    try:
        result = await detection_agent.chat(
            message=message,
            user_id=user_id,
            display_language=display_language,
        )
        final_text = result.get("output", "")
        logger.info("Detection Agent 完成: %d 字符", len(final_text))
        return {"final_answer": final_text}

    except Exception as e:
        logger.error("Detection Agent 执行失败: %s", str(e))
        error_msg = f"检测失败：{str(e)}" if display_language == "zh" else f"Detection failed: {str(e)}"
        return {"final_answer": error_msg}
    finally:
        reset_detection_tool_context(detection_context_tokens)


async def qa_node(state: AgentState) -> dict:
    """
    问答子 Agent 节点：处理知识问答任务。
    """
    user_input = state.get("user_input", "")
    display_language = state.get("display_language", "zh")
    user_id = state.get("user_id")

    try:
        result = await detection_agent.chat(
            message=user_input,
            user_id=user_id,
            display_language=display_language,
        )
        final_text = result.get("output", "")
        logger.info("QA Agent 完成: %d 字符", len(final_text))
        return {"final_answer": final_text}

    except Exception as e:
        logger.error("QA Agent 执行失败: %s", str(e))
        error_msg = f"问答失败：{str(e)}" if display_language == "zh" else f"Q&A failed: {str(e)}"
        return {"final_answer": error_msg}


async def analysis_node(state: AgentState) -> dict:
    """
    分析子 Agent 节点：处理统计查询任务。
    """
    user_input = state.get("user_input", "")
    display_language = state.get("display_language", "zh")
    user_id = state.get("user_id")
    is_admin = state.get("is_admin", False)

    analysis_context_tokens = set_tool_context(user_id, is_admin)

    try:
        result = await detection_agent.chat(
            message=user_input,
            user_id=user_id,
            is_admin=is_admin,
            display_language=display_language,
        )
        final_text = result.get("output", "")
        logger.info("Analysis Agent 完成: %d 字符", len(final_text))
        return {"final_answer": final_text}

    except Exception as e:
        logger.error("Analysis Agent 执行失败: %s", str(e))
        error_msg = f"分析失败：{str(e)}" if display_language == "zh" else f"Analysis failed: {str(e)}"
        return {"final_answer": error_msg}
    finally:
        reset_tool_context(analysis_context_tokens)


async def general_node(state: AgentState) -> dict:
    """
    通用对话节点：直接回复，不调用任何工具。
    """
    user_input = state.get("user_input", "")
    display_language = state.get("display_language", "zh")

    system_prompt = get_multi_agent_prompt("general", display_language) if display_language == "zh" else get_multi_agent_prompt("general", "en")

    try:
        llm = create_llm()
        response = await llm.ainvoke([
            ("system", system_prompt),
            ("human", user_input),
        ])
        final_text = response.content if hasattr(response, 'content') else str(response)
        logger.info("General Agent 完成: %d 字符", len(final_text))
        return {"final_answer": final_text}

    except Exception as e:
        logger.error("General Agent 执行失败: %s", str(e))
        error_msg = f"回复失败：{str(e)}" if display_language == "zh" else f"Reply failed: {str(e)}"
        return {"final_answer": error_msg}


def should_continue(state: AgentState) -> str:
    """
    条件边函数：决定下一步去哪里。
    """
    next_agent = state.get("next_agent", "end")
    max_iterations = state.get("max_iterations", 5)
    current_iteration = state.get("current_iteration", 0)

    if current_iteration >= max_iterations:
        logger.warning("达到最大迭代次数 %d，强制结束", max_iterations)
        return "end"

    if next_agent in ("end", ""):
        return "end"

    return next_agent
