"""
智能体模块（阶段二）。

阶段一：单 Agent + 8 工具（DetectionAgent 全能型）
阶段二：多 Agent + 独立工具集
  - DetectionAgent：4 个检测工具
  - QAAgent：1 个知识检索工具
  - AnalysisAgent：3 个分析工具
  - Supervisor：意图路由调度

架构：
  - base_agent: 子 Agent 基类（通用 SSE 流式逻辑）
  - detection_agent: 检测子 Agent（4 个检测工具）
  - qa_agent: 问答子 Agent（1 个知识检索工具）
  - analysis_agent: 分析子 Agent（3 个分析工具）
  - multi_agent: 多 Agent 混合调度器
  - supervisor: 意图路由调度器
"""

from app.agent.detection_agent import detection_agent
from app.agent.qa_agent import qa_agent
from app.agent.analysis_agent import analysis_agent
from app.agent.multi_agent import multi_agent_chat_stream
from app.agent.supervisor import supervisor_route

__all__ = [
    "detection_agent",
    "qa_agent",
    "analysis_agent",
    "multi_agent_chat_stream",
    "supervisor_route",
]
