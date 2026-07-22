"""
检测子 Agent（阶段二）— 只负责病害检测，持有 4 个检测工具

相比阶段一的变化：
  1. 继承 BaseAgent，复用通用 SSE 流式逻辑
  2. 工具从 8 个精简为 4 个（只保留检测工具）
  3. Prompt 使用精简版检测子 Agent 提示词
  4. 保留 _local_stream 降级方案（LLM 不可用时直接调用检测服务）
"""

import contextvars
import json
from pathlib import Path
from typing import AsyncGenerator

from app.agent.base_agent import BaseAgent, create_llm, _is_video_path, _is_zip_path
from app.agent.prompts import get_detection_agent_prompt
from app.agent.tools.detection_tool import (
    DETECTION_TOOLS,
    reset_detection_tool_context,
    set_detection_tool_context,
)
from app.core.logger import get_logger

logger = get_logger(__name__)

# 对外保留完整工具清单，测试和后续扩展可使用同一份定义。
from app.agent.tools.analysis_tool import ANALYSIS_TOOLS
from app.agent.tools.knowledge_tool import KNOWLEDGE_TOOLS
ALL_TOOLS = DETECTION_TOOLS + KNOWLEDGE_TOOLS + ANALYSIS_TOOLS

# 检测工具专用的 ContextVar（_local_stream 降级方案需要）
_tool_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "tool_user_id", default=None
)
_tool_scene_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "tool_scene_id", default=None
)
_tool_display_language: contextvars.ContextVar[str] = contextvars.ContextVar(
    "tool_display_language", default="zh"
)


def _detection_context_setup(user_id, scene_id, display_language, is_admin):
    """设置检测工具的上下文。"""
    return set_detection_tool_context(user_id, scene_id, display_language)


def _detection_context_teardown(tokens):
    """清理检测工具的上下文。"""
    reset_detection_tool_context(tokens)


class DetectionAgent(BaseAgent):
    """检测子 Agent，只持有 4 个检测工具。"""

    AGENT_NAME = "detection"
    TOOLS = DETECTION_TOOLS
    PROMPT_KEY = "detection_sub"

    def __init__(self):
        super().__init__()
        # 额外使用旧版全能 Prompt（保留兼容性，让 LLM 知道可以调用检测工具）
        # 但实际只绑定了检测工具，LLM 不会误调用知识/分析工具

    def _get_system_prompt(self, display_language: str) -> str:
        """使用旧版全能 Prompt（包含检测工具路由规则）。"""
        return get_detection_agent_prompt(display_language)

    async def chat(
        self,
        message: str,
        image_path: str = None,
        image_paths: list[str] | None = None,
        user_id: int | None = None,
        is_admin: bool = False,
        display_language: str = "zh",
    ) -> dict:
        """非流式对话（保留兼容性）。"""
        from app.agent.tools.analysis_tool import set_tool_context, reset_tool_context

        message, _ = self._attachment_message(
            message, image_path, image_paths, display_language
        )
        if display_language == "en":
            message += "\n[System instruction: Respond in English.]"

        if self.executor is None:
            return {
                "output": self._fallback_reply(message, display_language),
                "intermediate_steps": [],
            }

        detection_context_tokens = set_detection_tool_context(
            user_id, None, display_language
        )
        analysis_context_tokens = set_tool_context(user_id, is_admin)
        try:
            result = await self.executor.ainvoke(
                {
                    "input": message,
                    "response_language": display_language,
                    "system_prompt": self._get_system_prompt(display_language),
                }
            )
            return {
                "output": result["output"],
                "intermediate_steps": result.get("intermediate_steps", []),
            }
        except Exception as e:
            logger.error("Agent 执行异常: %s", str(e), exc_info=True)
            return {
                "output": (
                    f"An error occurred while processing your request: {str(e)}"
                    if display_language == "en"
                    else f"抱歉，处理过程中出现错误：{str(e)}"
                ),
                "intermediate_steps": [],
            }
        finally:
            reset_detection_tool_context(detection_context_tokens)
            reset_tool_context(analysis_context_tokens)

    def _fallback_reply(self, message: str, display_language: str) -> str:
        if "[附件" in message or "[attachment " in message:
            if display_language == "en":
                return "The AI service is currently unavailable. Please try again later."
            else:
                return "AI 服务暂时不可用，请稍后重试。"
        if display_language == "en":
            return "The AI service is currently unavailable. Please try again later."
        return "AI 服务暂时不可用，请稍后重试。"

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
    ) -> AsyncGenerator:
        """
        SSE 流式对话入口。
        相比 BaseAgent 的通用实现，增加了 _local_stream 降级方案：
        当 LLM 不可用时，如果有附件图片/视频，直接调用检测服务返回结果。
        """
        original_message = message
        message, attachment_paths = self._attachment_message(
            original_message, image_path, image_paths, display_language
        )
        if display_language == "en":
            message += "\n[System instruction: Respond in English.]"

        from app.agent.memory import conversation_memory
        from app.services.chat_history_service import chat_history_service

        persisted_user_message = self._message_for_history(
            original_message, attachment_paths, display_language
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

        user_token = _tool_user_id.set(user_id)
        scene_token = _tool_scene_id.set(scene_id)
        language_token = _tool_display_language.set(display_language)
        detection_context_tokens = set_detection_tool_context(
            user_id, scene_id, display_language
        )
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
                # LLM 不可用，降级到本地检测
                async for event in self._local_stream(
                    message, attachment_paths, display_language
                ):
                    if event.get("type") == "text_chunk":
                        assistant_parts.append(event.get("content", ""))
                    elif event.get("type") == "tool_call":
                        tool_calls.append(
                            {"tool": event.get("tool"), "input": event.get("input", {})}
                        )
                    elif event.get("type") == "tool_result":
                        tool_results.append(event.get("result", ""))
                    yield event
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
                    logger.info("工具调用: %s, 输入: %s", tool_name, str(tool_input)[:200])
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

            if tool_results and not assistant_parts:
                fallback_text = (
                    "Detection completed. Please review the result card, confidence values, and annotated outputs. "
                    "Use clear original images and field observations for final confirmation."
                    if display_language == "en"
                    else "检测已完成，请查看结果卡片、置信度和标注结果。最终判断仍建议结合清晰原图和现场情况复核。"
                )
                assistant_parts.append(fallback_text)
                yield {"type": "text_chunk", "content": fallback_text}

        except Exception as e:
            logger.error("Agent 流式执行异常: %s", str(e), exc_info=True)
            # LLM 临时不可用时，有附件的请求仍可直接执行本地检测并返回结果卡片。
            if attachment_paths:
                async for event in self._local_stream(
                    message, attachment_paths, display_language
                ):
                    if event.get("type") == "text_chunk":
                        assistant_parts.append(event.get("content", ""))
                    elif event.get("type") == "tool_call":
                        tool_calls.append(
                            {"tool": event.get("tool"), "input": event.get("input", {})}
                        )
                    elif event.get("type") == "tool_result":
                        tool_results.append(event.get("result", ""))
                    yield event
                return
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
            _tool_display_language.reset(language_token)
            reset_detection_tool_context(detection_context_tokens)

        yield {
            "type": "done",
            "full_text": "".join(assistant_parts),
        }

    async def _local_stream(
        self, message: str, attachment_paths: list[str], display_language: str
    ):
        """LLM 不可用时的降级方案：直接调用检测服务。"""
        from app.services.detection_service import detection_service

        if not attachment_paths:
            error_msg = (
                "Please provide an image or video for detection."
                if display_language == "en"
                else "请提供图片或视频进行检测。"
            )
            yield {"type": "error", "content": error_msg}
            return

        if len(attachment_paths) > 1:
            if any(_is_video_path(path) or _is_zip_path(path) for path in attachment_paths):
                error_msg = (
                    "Please upload either multiple images, one ZIP file, or one video file."
                    if display_language == "en"
                    else "请上传多张图片、单个 ZIP 文件或单个视频文件，不要混合上传。"
                )
                yield {"type": "error", "content": error_msg}
                return

            yield {
                "type": "tool_call",
                "tool": "detect_batch_images",
                "input": {"image_paths": attachment_paths},
            }
            try:
                result = detection_service.detect_batch(
                    attachment_paths,
                    scene_id=_tool_scene_id.get(),
                    user_id=_tool_user_id.get(),
                    display_language=_tool_display_language.get(),
                )
                yield {
                    "type": "tool_result",
                    "tool": "detect_batch_images",
                    "result": json.dumps(result, ensure_ascii=False),
                }
                yield {
                    "type": "text_chunk",
                    "content": "Batch detection completed. Please review the result card."
                    if display_language == "en"
                    else "批量检测完成，请查看结果卡片。",
                }
            except Exception as e:
                yield {"type": "error", "content": str(e)}
            return

        for path in attachment_paths:
            if _is_video_path(path):
                yield {
                    "type": "tool_call",
                    "tool": "detect_video_file",
                    "input": {"video_path": path},
                }
                try:
                    result = detection_service.detect_video(
                        path,
                        scene_id=_tool_scene_id.get(),
                        user_id=_tool_user_id.get(),
                        display_language=_tool_display_language.get(),
                    )
                    result["type"] = "video"
                    yield {
                        "type": "tool_result",
                        "tool": "detect_video_file",
                        "result": json.dumps(result, ensure_ascii=False),
                    }
                    yield {
                        "type": "text_chunk",
                        "content": "Video detection completed. Please review the result card."
                        if display_language == "en"
                        else "视频检测完成，请查看结果卡片。",
                    }
                except Exception as e:
                    yield {"type": "error", "content": str(e)}
            elif _is_zip_path(path):
                yield {
                    "type": "tool_call",
                    "tool": "detect_zip_images_file",
                    "input": {"zip_path": path},
                }
                try:
                    result = detection_service.detect_zip(
                        path,
                        scene_id=_tool_scene_id.get(),
                        user_id=_tool_user_id.get(),
                        display_language=_tool_display_language.get(),
                    )
                    yield {
                        "type": "tool_result",
                        "tool": "detect_zip_images_file",
                        "result": json.dumps(result, ensure_ascii=False),
                    }
                    yield {
                        "type": "text_chunk",
                        "content": "ZIP detection completed. Please review the result card."
                        if display_language == "en"
                        else "ZIP 检测完成，请查看结果卡片。",
                    }
                except Exception as e:
                    yield {"type": "error", "content": str(e)}
            else:
                yield {
                    "type": "tool_call",
                    "tool": "detect_single_image",
                    "input": {"image_path": path},
                }
                try:
                    result = detection_service.detect_single(
                        path,
                        scene_id=_tool_scene_id.get(),
                        user_id=_tool_user_id.get(),
                        display_language=_tool_display_language.get(),
                    )
                    yield {
                        "type": "tool_result",
                        "tool": "detect_single_image",
                        "result": json.dumps(result, ensure_ascii=False),
                    }
                    yield {
                        "type": "text_chunk",
                        "content": "Detection completed. Please review the result card."
                        if display_language == "en"
                        else "检测完成，请查看结果卡片。",
                    }
                except Exception as e:
                    yield {"type": "error", "content": str(e)}


detection_agent = DetectionAgent()
