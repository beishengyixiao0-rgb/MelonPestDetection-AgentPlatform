"""
LangGraph 多 Agent 状态图

架构：
  START → supervisor_node → 条件路由 → detection_node / qa_node / analysis_node / general_node → END

使用方式：
  from app.agent.graph import multi_agent_graph

  result = await multi_agent_graph.ainvoke({
      "messages": [],
      "user_input": "检测这张图",
      "next_agent": "",
      "final_answer": "",
      "events": [],
      "attachment_paths": [],
      "user_id": 1,
      "session_id": "xxx",
      "display_language": "zh",
      "is_admin": False,
      "scene_id": None,
      "max_iterations": 5,
      "current_iteration": 0,
  })
"""

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    analysis_node,
    detection_node,
    general_node,
    qa_node,
    should_continue,
    supervisor_node,
)
from app.agent.state import AgentState
from app.core.logger import get_logger

logger = get_logger(__name__)


def _build_graph() -> StateGraph:
    """构建多 Agent 状态图。"""
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("detection", detection_node)
    graph.add_node("qa", qa_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("general", general_node)

    # 添加边：START → supervisor
    graph.add_edge(START, "supervisor")

    # 添加条件边：supervisor → 根据 next_agent 路由
    graph.add_conditional_edges(
        "supervisor",
        should_continue,
        {
            "detection": "detection",
            "qa": "qa",
            "analysis": "analysis",
            "general": "general",
            "end": END,
        },
    )

    # 添加边：各子 Agent → END
    graph.add_edge("detection", END)
    graph.add_edge("qa", END)
    graph.add_edge("analysis", END)
    graph.add_edge("general", END)

    return graph


# 编译图（全局单例）
try:
    multi_agent_graph = _build_graph().compile()
    logger.info("多 Agent 状态图编译成功")
except Exception as e:
    logger.error("多 Agent 状态图编译失败: %s", str(e))
    multi_agent_graph = None
