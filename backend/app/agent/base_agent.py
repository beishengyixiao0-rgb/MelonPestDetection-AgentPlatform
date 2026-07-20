"""
子 Agent 基类 — 提取通用的 chat_stream 逻辑

所有子 Agent（DetectionAgent / QAAgent / AnalysisAgent）共享：
  - LLM 创建
  - AgentExecutor 构建
  - SSE 流式输出（thinking/tool_call/tool_result/text_chunk/done）
  - ContextVar 上下文隔离
  - 对话历史管理

子类只需指定：tools、prompt 名称、agent 日志名。
"""

import contextvars
import json
import re
from pathlib import Path
from typing import AsyncGenerator

import httpx
from app.agent.memory import conversation_memory
from app.agent.prompts import get_multi_agent_prompt
from app.config.settings import settings
from app.core.logger import get_logger
from app.services.chat_history_service import chat_history_service
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

logger = get_logger(__name__)

VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}
FAKE_TOOL_CALL_PATTERN = re.compile(
    r"^\s*(?:call|tool_call|function_call)?\s*`{0,3}\s*\{[^{}]*(?:\"name\"|'name')[^{}]*(?:\"arguments\"|'arguments')",
    re.IGNORECASE | re.DOTALL,
)


def _is_video_path(path: str) -> bool:
    return Path(path).suffix.lower() in VIDEO_SUFFIXES


def create_llm():
    """创建 LLM 实例（通义千问优先，OpenAI 降级）。"""
    qwen_api_key = getattr(settings, "QWEN_API_KEY", "")
    if qwen_api_key and qwen_api_key != "sk-your-qwen-api-key":
        api_key = qwen_api_key
        base_url = getattr(
            settings,
            "QWEN_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        model_name = getattr(settings, "QWEN_MODEL", "qwen3.7-plus")
    else:
        api_key = getattr(settings, "OPENAI_API_KEY", "")
        base_url = getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        model_name = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")

    from langchain_openai import ChatOpenAI

    proxy = getattr(settings, "QWEN_PROXY", "").strip() or None
    http_client = httpx.Client(
        proxy=proxy,
        timeout=httpx.Timeout(60.0, connect=15.0),
        trust_env=False,
    )
    http_async_client = httpx.AsyncClient(
        proxy=proxy,
        timeout=httpx.Timeout(60.0, connect=15.0),
        trust_env=False,
    )
    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=0.1,
        http_client=http_client,
        http_async_client=http_async_client,
    )


class BaseAgent:
    """子 Agent 基类，提供通用的 SSE 流式对话能力。"""

    # 子类必须覆盖
    AGENT_NAME: str = "base"
    TOOLS: list = []
    PROMPT_KEY: str = ""  # 对应 MULTI_AGENT_PROMPT_REGISTRY 中的 key

    def __init__(self):
        self.llm = create_llm()
        self.agent_logger = get_logger(f"agent.{self.AGENT_NAME}")

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        try:
            agent = create_openai_tools_agent(
                llm=self.llm,
                tools=self.TOOLS,
                prompt=prompt,
            )
            self.executor = AgentExecutor(
                agent=agent,
                tools=self.TOOLS,
                verbose=True,
                max_iterations=8,
                return_intermediate_steps=True,
            )
        except Exception as e:
            logger.error("[%s] Agent 创建失败，降级为无 LLM 模式: %s", self.AGENT_NAME, e)
            self.executor = None

        self.agent_logger.info(
            "[%s] 初始化完成，绑定 %d 个工具", self.AGENT_NAME, len(self.TOOLS)
        )

    def _get_system_prompt(self, display_language: str) -> str:
        """获取当前语言的系统提示词。"""
        lang = "en" if display_language == "en" else "zh"
        return get_multi_agent_prompt(self.PROMPT_KEY, lang)

    def _attachment_message(
        self,
        message: str,
        image_path: str | None = None,
        image_paths: list[str] | None = None,
    ) -> tuple[str, list[str]]:
        attachment_paths = image_paths or ([image_path] if image_path else [])
        if len(attachment_paths) == 1:
            label = "视频" if _is_video_path(attachment_paths[0]) else "图片"
            return (
                f"{message}\n[附件{label}路径: {attachment_paths[0]}]",
                attachment_paths,
            )
        if attachment_paths:
            paths_json = json.dumps(attachment_paths, ensure_ascii=False)
            label = (
                "视频"
                if all(_is_video_path(path) for path in attachment_paths)
                else "图片"
            )
            return f"{message}\n[附件{label}路径列表: {paths_json}]", attachment_paths
        return message, attachment_paths

    @staticmethod
    def _message_for_history(message: str, attachment_paths: list[str]) -> str:
        if not attachment_paths:
            return message
        if len(attachment_paths) == 1:
            attachment_label = "视频" if _is_video_path(attachment_paths[0]) else "图片"
            return f"{message}\n[本轮已上传{attachment_label}附件]"
        return f"{message}\n[本轮已上传 {len(attachment_paths)} 个图片附件]"

    @staticmethod
    def _to_langchain_messages(history: list[dict]) -> list:
        messages = []
        for item in history:
            content = item.get("content", "")
            if not content:
                continue
            if item.get("role") in ("assistant", "ai"):
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))
        return messages

    @staticmethod
    def _tool_output_text(tool_output) -> str:
        if isinstance(tool_output, str):
            return tool_output
        content = getattr(tool_output, "content", None)
        if isinstance(content, str):
            return content
        return str(tool_output) if tool_output is not None else ""

    @staticmethod
    def _sanitize_model_text(content: str, display_language: str) -> str:
        """禁止模型把伪工具调用 JSON 当普通正文输出。"""
        if not content:
            return content
        if not FAKE_TOOL_CALL_PATTERN.search(content):
            return content
        return (
            "The model attempted to emit an unregistered tool call, so the response was blocked. "
            "Please try again, or ask for a supported action such as detection history, statistics, or knowledge-base Q&A."
            if display_language == "en"
            else "模型尝试输出未注册的工具调用，已被系统拦截。请重试，或改问系统支持的检测历史、统计、知识库问答等功能。"
        )

    @staticmethod
    def _compact_tool_results(tool_results: list[str]) -> str | None:
        if not tool_results:
            return None
        latest_detection_result = None
        fallback_results = []
        for result in tool_results:
            try:
                data = json.loads(result)
                if not isinstance(data, dict):
                    continue
                for frame in data.get("key_frames", []):
                    if data.get("annotated_video_url"):
                        frame.pop("annotated_image_base64", None)
                        frame.pop("source_image_base64", None)
                if (
                    data.get("type") == "video"
                    or "detections" in data
                    or "annotated_image_base64" in data
                    or "annotated_images" in data
                ):
                    latest_detection_result = data
                else:
                    fallback_results.append(data)
            except (json.JSONDecodeError, AttributeError):
                fallback_results.append(str(result))
        if latest_detection_result is not None:
            return json.dumps(latest_detection_result, ensure_ascii=False)
        return (
            json.dumps(fallback_results[-1], ensure_ascii=False)
            if fallback_results
            else None
        )

    @staticmethod
    def _knowledge_status_text(
        tool_name: str, serialized_output: str, display_language: str
    ) -> str | None:
        """把知识库检索结果转成用户可见的命中状态提示。"""
        if tool_name != "search_knowledge":
            return None
        try:
            data = json.loads(serialized_output)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None

        if data.get("error"):
            return (
                f"Knowledge retrieval failed: {data['error']}\n\n"
                if display_language == "en"
                else f"知识库检索失败：{data['error']}\n\n"
            )

        fallback = bool(data.get("fallback_to_llm"))
        count = int(data.get("count") or len(data.get("knowledge") or []))
        if fallback or count <= 0:
            return (
                "Knowledge base not hit; answering with general model knowledge.\n\n"
                if display_language == "en"
                else "未命中知识库，以下回答将基于通用模型知识。\n\n"
            )
        return (
            f"Knowledge base hit: {count} relevant fragment(s).\n\n"
            if display_language == "en"
            else f"已命中知识库：{count} 条相关片段。\n\n"
        )

    @staticmethod
    def _save_history_message(
        user_id: int,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[dict] | None = None,
        tool_result: str | None = None,
    ):
        try:
            chat_history_service.append_message(
                user_id,
                session_id,
                role,
                content,
                tool_calls=tool_calls,
                tool_result=tool_result,
            )
            conversation_memory.save_message(user_id, session_id, role, content)
        except Exception as e:
            logger.error("保存历史消息失败: %s", e)

    async def chat_stream(
        self,
        message: str,
        image_path: str = None,
        image_paths: list[str] | None = None,
        user_id: int | None = None,
        scene_id: int | None = None,
        session_id: str | None = None,
        display_language: str = "zh",
        attachment_urls: list[str] | None = None,
        is_admin: bool = False,
        extra_context_setup=None,
        extra_context_teardown=None,
    ) -> AsyncGenerator:
        """
        SSE 流式对话入口（通用实现）。

        extra_context_setup: 可选的同步上下文设置函数 (user_id, scene_id, display_language, is_admin) -> tokens
        extra_context_teardown: 可选的上下文清理函数 (tokens) -> None
        """
        original_message = message
        message, attachment_paths = self._attachment_message(
            original_message, image_path, image_paths
        )
        if display_language == "en":
            message += "\n[System instruction: Respond in English.]"

        persisted_user_message = self._message_for_history(
            original_message, attachment_paths
        )
        chat_history = []
        if user_id is not None and session_id:
            history = conversation_memory.load_history(user_id, session_id)
            if not history:
                history = chat_history_service.get_recent_messages(
                    user_id, session_id, conversation_memory.max_messages
                )
                if history:
                    conversation_memory.replace_history(user_id, session_id, history)
            chat_history = self._to_langchain_messages(history)
            self._save_history_message(
                user_id,
                session_id,
                "user",
                persisted_user_message,
                tool_result=json.dumps(
                    {"attachments": attachment_urls or []}, ensure_ascii=False
                ),
            )

        # ContextVar 隔离
        _tool_user_id: contextvars.ContextVar = contextvars.ContextVar("base_user_id", default=None)
        _tool_scene_id: contextvars.ContextVar = contextvars.ContextVar("base_scene_id", default=None)
        _tool_lang: contextvars.ContextVar = contextvars.ContextVar("base_lang", default="zh")

        user_token = _tool_user_id.set(user_id)
        scene_token = _tool_scene_id.set(scene_id)
        language_token = _tool_lang.set(display_language)

        # 子类自定义上下文设置
        extra_tokens = None
        if extra_context_setup:
            extra_tokens = extra_context_setup(user_id, scene_id, display_language, is_admin)

        assistant_parts: list[str] = []
        tool_calls: list[dict] = []
        tool_results: list[str] = []

        thinking_msg = (
            "Analyzing your request..."
            if display_language == "en"
            else "正在分析您的请求..."
        )
        yield {"type": "thinking", "content": thinking_msg}

        try:
            if self.executor is None:
                yield {"type": "error", "content": "AI 服务暂时不可用，请稍后重试。" if display_language == "zh" else "AI service temporarily unavailable."}
                return

            async for event in self.executor.astream_events(
                {
                    "input": message,
                    "chat_history": chat_history,
                    "response_language": display_language,
                    "system_prompt": self._get_system_prompt(display_language),
                },
                version="v2",
            ):
                event_kind = event["event"]

                if event_kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        assistant_parts.append(chunk.content)
                        yield {"type": "text_chunk", "content": chunk.content}

                elif event_kind == "on_tool_start":
                    tool_name = event["name"]
                    tool_input = event["data"].get("input", {})
                    self.agent_logger.info(
                        "工具调用: %s, 输入: %s", tool_name, str(tool_input)[:200]
                    )
                    tool_calls.append({"tool": tool_name, "input": tool_input})
                    yield {"type": "tool_call", "tool": tool_name, "input": tool_input}

                elif event_kind == "on_tool_end":
                    tool_data = event.get("data", {})
                    tool_output = tool_data.get("output", "")
                    tool_name = event.get("name", "")
                    serialized_output = self._tool_output_text(tool_output)
                    tool_results.append(serialized_output)
                    yield {
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": serialized_output,
                    }
                    knowledge_status = self._knowledge_status_text(
                        tool_name, serialized_output, display_language
                    )
                    if knowledge_status:
                        assistant_parts.append(knowledge_status)
                        yield {"type": "text_chunk", "content": knowledge_status}

        except Exception as e:
            self.agent_logger.error("Agent 流式执行异常: %s", str(e), exc_info=True)
            error_message = (
                f"Processing failed: {str(e)}"
                if display_language == "en"
                else f"处理出错：{str(e)}"
            )
            assistant_parts.append(error_message)
            yield {"type": "error", "content": error_message}
        finally:
            if user_id is not None and session_id and assistant_parts:
                self._save_history_message(
                    user_id,
                    session_id,
                    "assistant",
                    "".join(assistant_parts),
                    tool_calls=tool_calls or None,
                    tool_result=self._compact_tool_results(tool_results),
                )
            _tool_user_id.reset(user_token)
            _tool_scene_id.reset(scene_token)
            _tool_lang.reset(language_token)
            if extra_context_teardown and extra_tokens is not None:
                extra_context_teardown(extra_tokens)

        yield {
            "type": "done",
            "full_text": "".join(assistant_parts),
        }
