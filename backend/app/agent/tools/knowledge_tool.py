"""
知识库工具 — Agent 可调用的 RAG 检索工具

工具列表：
  - search_knowledge: 语义检索知识库
"""

import json
import re

from app.config.settings import settings
from app.core.logger import get_logger
from app.rag.retriever import knowledge_retriever
from langchain_core.tools import tool

logger = get_logger(__name__)

DISEASE_CORE_TERMS = (
    "细菌性斑点病",
    "花叶病毒病",
    "septoria leaf spot",
    "late blight",
    "early blight",
    "gray mold",
    "grey mold",
    "bacterial spot",
    "mosaic virus",
    "leaf mold",
    "target spot",
    "炭疽病",
    "灰霉病",
    "白星病",
    "晚疫病",
    "早疫病",
    "叶霉病",
    "白粉病",
    "黑斑病",
    "褐斑病",
    "叶斑病",
    "斑点病",
    "锈病",
    "枯萎病",
    "软腐病",
    "疫病",
    "病毒病",
    "灰霉",
)


def _dedupe_terms(terms: list[str]) -> list[str]:
    deduped: list[str] = []
    for term in sorted(set(terms), key=len, reverse=True):
        if not any(term in existing for existing in deduped):
            deduped.append(term)
    return deduped


def _extract_required_terms(query: str) -> list[str]:
    """病害类问题需要核心病名直接出现，避免相近症状片段被误判为命中。"""
    normalized = (query or "").lower()
    matched = [term for term in DISEASE_CORE_TERMS if term.lower() in normalized]

    # 兜底处理知识库未预置的新病名，如“苹果腐烂病”“番茄灰叶斑病”。
    if not matched:
        generic_matches = re.findall(
            r"[\u4e00-\u9fff]{0,8}(?:病毒病|虫害|病)",
            query or "",
        )
        for item in generic_matches:
            if len(item) >= 3 and item not in {"病害", "疾病", "虫害"}:
                matched.append(item)

    return _dedupe_terms(matched)


def _contains_required_term(text: str, required_terms: list[str]) -> bool:
    if not required_terms:
        return True
    normalized = (text or "").lower()
    return any(term.lower() in normalized for term in required_terms)


@tool
def search_knowledge(query: str, top_k: int = 3) -> str:
    """搜索果蔬病害检测知识库，获取专业领域的知识内容。

    当用户询问专业知识问题时使用此工具，例如：
    - "什么是 IoU？"
    - "YOLOv11 有哪些改进？"
    - "mAP 是怎么计算的？"
    - "遥感图像有什么特点？"
    - "什么是 NMS 非极大值抑制？"

    Args:
        query: 用户的问题或关键词
        top_k: 返回最相关的前 K 条知识片段，默认 3 条

    Returns:
        JSON 字符串，包含检索到的知识片段（内容、来源、相似度）
    """
    try:
        results = knowledge_retriever.search(query, top_k=top_k)

        if not results:
            return json.dumps(
                {
                    "knowledge": [],
                    "sources": [],
                    "count": 0,
                    "hit": False,
                    "max_similarity": 0,
                    "threshold": settings.RAG_SIMILARITY_THRESHOLD,
                    "fallback_to_llm": True,
                    "answer_instruction": "未命中知识库，可以基于通用知识回答，并说明未找到知识库来源。",
                },
                ensure_ascii=False,
            )

        formatted = []
        for r in results:
            formatted.append(
                {
                    "content": r["content"][:300],  # 截取前 300 字符，避免过长
                    "source": r.get("metadata", {}).get("source", "未知"),
                    "similarity": r.get("similarity", 0),
                }
            )

        required_terms = _extract_required_terms(query)
        if required_terms:
            matched = [
                item
                for item in formatted
                if _contains_required_term(
                    f"{item.get('content', '')}\n{item.get('source', '')}",
                    required_terms,
                )
            ]
            if not matched:
                return json.dumps(
                    {
                        "knowledge": [],
                        "near_matches": formatted,
                        "sources": [],
                        "count": 0,
                        "candidate_count": len(formatted),
                        "hit": False,
                        "max_similarity": max((item["similarity"] for item in formatted), default=0),
                        "threshold": settings.RAG_SIMILARITY_THRESHOLD,
                        "fallback_to_llm": True,
                        "required_terms": required_terms,
                        "strict_reason": f"检索到相近片段，但未直接包含核心病名：{', '.join(required_terms)}",
                        "answer_instruction": "未命中知识库；可基于通用知识回答，但必须说明未找到知识库来源。",
                    },
                    ensure_ascii=False,
                )
            formatted = matched

        return json.dumps(
            {
                "knowledge": formatted,
                "count": len(formatted),
                "hit": True,
                "max_similarity": max((item["similarity"] for item in formatted), default=0),
                "threshold": settings.RAG_SIMILARITY_THRESHOLD,
                "fallback_to_llm": False,
                "required_terms": required_terms,
                "answer_instruction": "已命中知识库，请基于 knowledge 字段回答；不要再说知识库中暂无相关内容。",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error("知识检索失败: %s", str(e))
        return json.dumps({"error": f"检索失败: {str(e)}"}, ensure_ascii=False)


# 知识工具列表
KNOWLEDGE_TOOLS = [
    search_knowledge,
]
