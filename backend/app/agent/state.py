"""
AgentState — LangGraph 多 Agent 共享状态定义

设计原则：
  - 所有节点通过 State 传递信息，不直接互相调用
  - 只包含必要的字段，避免状态膨胀
  - 支持 SSE 流式输出（events 列表累积）

使用方式：
  from app.agent.state import AgentState
  
  state: AgentState = {
      "messages": [...],
      "next_agent": "detection",
      "final_answer": "",
      "events": [],
  }
"""

from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """多 Agent 共享状态"""

    messages: Annotated[list, add_messages]

    user_input: str

    next_agent: str

    final_answer: str

    events: list[dict]

    attachment_paths: list[str]

    user_id: int | None

    session_id: str | None

    display_language: str

    is_admin: bool

    scene_id: int | None

    max_iterations: int

    current_iteration: int
