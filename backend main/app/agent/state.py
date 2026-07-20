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

    # 对话历史消息列表（LangGraph 自动追加）
    messages: Annotated[list, add_messages]

    # 用户原始输入（不含历史记录）
    user_input: str

    # 下一步该哪个 Agent 处理（Supervisor 写入）
    # 可选值: "detection" | "qa" | "analysis" | "general" | "end"
    next_agent: str

    # 最终回答文本（最后一个 Agent 写入）
    final_answer: str

    # SSE 事件列表（用于流式输出累积）
    events: list[dict]

    # 附件路径列表（用户上传的图片/视频）
    attachment_paths: list[str]

    # 用户 ID（用于工具上下文隔离）
    user_id: int | None

    # 会话 ID（用于保存历史）
    session_id: str | None

    # 显示语言（zh / en）
    display_language: str

    # 是否为管理员（用于权限控制）
    is_admin: bool

    # 场景 ID（用于检测工具）
    scene_id: int | None

    # 最大迭代次数（防止无限循环）
    max_iterations: int

    # 当前迭代次数
    current_iteration: int
