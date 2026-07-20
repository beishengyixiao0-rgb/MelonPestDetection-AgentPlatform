"""
Supervisor — 多 Agent 路由调度器

职责：
  - 分析用户意图，判断应该派给哪个子 Agent
  - 只返回一个词：detection / qa / analysis / general
  - 不做具体工作，只做路由决策

使用方式：
  from app.agent.supervisor import supervisor_route

  route = await supervisor_route("检测这张图", "zh")
  # 返回: "detection"
"""

import httpx
from app.agent.prompts import get_multi_agent_prompt
from app.config.settings import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


def _create_supervisor_llm():
    """创建轻量级 LLM 用于 Supervisor 路由（不需要工具调用能力）。"""
    qwen_api_key = getattr(settings, "QWEN_API_KEY", "")
    if qwen_api_key and qwen_api_key != "sk-your-qwen-api-key":
        api_key = qwen_api_key
        base_url = getattr(
            settings,
            "QWEN_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        model_name = getattr(settings, "QWEN_MODEL", "qwen3.7-max-2026-06-08")
    else:
        api_key = getattr(settings, "OPENAI_API_KEY", "")
        base_url = getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        model_name = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    from langchain_openai import ChatOpenAI

    proxy = getattr(settings, "QWEN_PROXY", "").strip() or None
    http_client = httpx.Client(
        proxy=proxy,
        timeout=httpx.Timeout(30.0, connect=10.0),
        trust_env=False,
    )
    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=0.0,
        http_client=http_client,
    )


async def supervisor_route(user_input: str, display_language: str = "zh") -> str:
    """
    分析用户输入，返回应该路由到的 Agent 名称。

    Args:
        user_input: 用户的原始消息
        display_language: 显示语言（zh / en）

    Returns:
        "detection" | "qa" | "analysis" | "general"
    """
    llm = _create_supervisor_llm()
    prompt_text = get_multi_agent_prompt("supervisor", display_language)

    try:
        response = await llm.ainvoke(
            [
                ("system", prompt_text),
                ("human", user_input),
            ]
        )
        result = response.content.strip().lower() if hasattr(response, 'content') else str(response).strip().lower()

        for keyword in ["detection", "qa", "analysis", "general"]:
            if keyword in result:
                logger.info("Supervisor 路由: %s → %s", user_input[:50], keyword)
                return keyword

        logger.warning("Supervisor 返回未知路由: %s，默认走 general", result[:100])
        return "general"

    except Exception as e:
        logger.error("Supervisor 路由失败: %s，默认走 general", str(e))
        return "general"
