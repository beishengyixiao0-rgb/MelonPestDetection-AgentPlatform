"""
问答子 Agent — 只负责知识问答，持有 search_knowledge 工具
"""

from app.agent.base_agent import BaseAgent
from app.agent.tools.knowledge_tool import KNOWLEDGE_TOOLS


class QAAgent(BaseAgent):
    """知识问答子 Agent，只持有 search_knowledge 工具。"""

    AGENT_NAME = "qa"
    TOOLS = KNOWLEDGE_TOOLS
    PROMPT_KEY = "qa_sub"


qa_agent = QAAgent()
