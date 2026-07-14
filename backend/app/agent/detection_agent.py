"""
检测智能体 — ReAct Agent + 检测工具绑定

职责：
  -. 创建 LangChain ReAct Agent
  - 绑定检测相关工具（单图/批量/ZIP）
  - 处理 SSE 流式输出 Agent 的思考过程和结果

架构：
  用户消息 → Agent（LLM 决策）→ 调用 DetectionTool → 返回 结果

使用方式：
  from app.agent.detection_agent import DetectionAgent

  agent = DetectionAgent()
  response = await agent.chat("检测这张图片", image_path="xxx.jpg")
"""

import asyncio
import contextvars
import json
from typing import AsyncGenerator

import httpx
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.core.logger import get_logger
from app.services.detection_service import detection_service

logger = get_logger(__name__)

# Tool 函数没有 HTTP 请求上下文，使用 ContextVar 安全传递当前用户和场景。
_tool_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("tool_user_id", default=None)
_tool_scene_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("tool_scene_id", default=None)


# ══════════════════════════════════════════════════════════════
# 一、定义检测工具（Agent 可调用的 Tools）
# ══════════════════════════════════════════════════════════════


@tool
def detect_single_image(image_path: str, conf: float = 0.25, iou: float = 0.45) -> str:
    """
    检测单张图片中的目标物体。

    Args:
        image_path: 图片文件路径或 URL
        conf: 置信度阈值，默认 0.25
        iou: NMS IoU 阈值，默认 0.45

    Returns:
        JSON 字符串，包含检测结果（目标数量、类别统计、标注图路径）
    """
    result = detection_service.detect_single(
        image_path,
        conf=conf,
        iou=iou,
        scene_id=_tool_scene_id.get(),
        user_id=_tool_user_id.get(),
    )
    return json.dumps(result, ensure_ascii=False)


@tool
def detect_batch_images(image_paths: list[str], conf: float = 0.25, iou: float = 0.45) -> str:
    """
    批量检测多张图片中的目标物体。

    Args:
        image_paths: 图片文件路径列表
        conf: 置信度阈值，默认 0.25

    Returns:
        JSON 字符串，包含每张图片的检测结果汇总
    """
    result = detection_service.detect_batch(
        image_paths,
        conf=conf,
        iou=iou,
        scene_id=_tool_scene_id.get(),
        user_id=_tool_user_id.get(),
    )
    return json.dumps(result, ensure_ascii=False)


@tool
def detect_zip_images_file(zip_path: str, conf: float = 0.25, iou: float = 0.45) -> str:
    """
    解压 ZIP 文件并批量检测其中所有图片的目标物体。

    Args:
        zip_path: ZIP 文件路径
        conf: 置信度阈值，默认 0.25

    Returns:
        JSON 字符串，包含 ZIP 内所有图片的检测结果汇总
    """
    result = detection_service.detect_zip(
        zip_path,
        conf=conf,
        iou=iou,
        scene_id=_tool_scene_id.get(),
        user_id=_tool_user_id.get(),
    )
    return json.dumps(result, ensure_ascii=False)


# 工具列表（绑定到 Agent）
DETECTION_TOOLS = [detect_single_image, detect_batch_images, detect_zip_images_file]


# ══════════════════════════════════════════════════════════════
# 二、创建 LLM 实例
# ══════════════════════════════════════════════════════════════


def create_llm():
    """
    根据配置创建 LLM 实例

    支持三种 LLM 后端：
      1. 通义千问（Qwen，通过 OpenAI 兼容接口）
      2. OpenAI（GPT-4o-mini）
      3. Ollama 本地部署

    本项目按当前要求只启用通义千问。指导书中的 ChatOpenAI 是 LangChain
    对 OpenAI 兼容协议的客户端类名；本项目只传入 DashScope 地址，不调用 OpenAI 服务。
    """
    # 优先使用通义千问（国内访问快，有免费额度）
    qwen_api_key = getattr(settings, "QWEN_API_KEY", "")
    api_key = qwen_api_key
    base_url = getattr(settings, "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model_name = getattr(settings, "QWEN_MODEL", "qwen-plus")

    # 未配置 Key 时不初始化远程客户端，后续由本地 Tool 降级链路处理。
    if not api_key:
        return None

    # DashScope 可直接访问。默认忽略系统代理，防止失效代理在 TLS 握手时中断请求；
    # 如部署网络必须经代理，可通过 QWEN_PROXY 显式配置。
    proxy = getattr(settings, "QWEN_PROXY", "").strip() or None
    async_http_client = httpx.AsyncClient(
        proxy=proxy,
        timeout=httpx.Timeout(60.0, connect=15.0),
        trust_env=False,
    )
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.1,  # 低温度，减少随机性，检测结果需要确定性
        http_async_client=async_http_client,
    )


# ══════════════════════════════════════════════════════════════
# 三、创建 ReAct Agent
# ══════════════════════════════════════════════════════════════


class DetectionAgent:
    """检测智能体 — 封装 ReAct Agent 创建和对话逻辑"""

    def __init__(self):
        """初始化 Agent，创建 LLM 和 AgentExecutor"""
        self.llm = create_llm()
        self.executor = None
        if self.llm is None:
            logger.info("未配置 LLM API Key，DetectionAgent 使用本地检测降级模式")
            return

        # OpenAI Tools Agent 系统提示词
        # 实际请求发送至通义千问的 OpenAI 兼容接口。
        system_prompt = """你是一个专业的目标检测助手。你可以帮用户检测图片中的目标物体。

重要规则：
- 当用户消息中包含 [附件图片路径: xxx] 时，xxx 就是图片的服务器路径，你应直接使用它调用检测工具
- 当用户消息中包含 [附件图片路径列表: [...]] 时，必须将列表中的全部路径传给 detect_batch_images 的 image_paths 参数
- 不要要求用户再次提供路径，直接使用附件中给出的路径
- 对于单张图片，调用 detect_single_image 工具
- 对于多张图片，调用 detect_batch_images；对于 ZIP 文件，调用 detect_zip_images_file

工作流程：
1. 理解用户意图
2. 如果有附件图片路径，直接调用检测工具
3. 调用工具获取检测结果
4. 用自然语言总结检测结果

回复格式要求：
- 先报告检测到的目标总数
- 列出各类别的数量统计
- 如果有标注图，告知用户可以在结果卡片中查看
- 简洁专业，不要过度解释"""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        # 创建 OpenAI Tools Agent（与 ChatPromptTemplate + MessagesPlaceholder 完全兼容）
        # 实际使用 Qwen 的 OpenAI 兼容协议。
        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=DETECTION_TOOLS,
            prompt=prompt,
        )

        self.executor = AgentExecutor(
            agent=agent,
            tools=DETECTION_TOOLS,
            verbose=True,  # 开发阶段开启，可查看 Agent 思考过程
            max_iterations=5,  # 限制循环次数，防止无限循环
            return_intermediate_steps=True,  # 返回中间步骤（Tool 调用记录）
        )

        logger.info("DetectionAgent 初始化完成，绑定 %d 个工具", len(DETECTION_TOOLS))

    @staticmethod
    def _attachment_message(message: str, image_path: str | None = None, image_paths: list[str] | None = None) -> tuple[str, list[str]]:
        """标准化单附件和多附件输入，并生成供 Agent 读取的路径提示。"""
        attachment_paths = image_paths or ([image_path] if image_path else [])
        if len(attachment_paths) == 1:
            return f"{message}\n[附件图片路径: {attachment_paths[0]}]", attachment_paths
        if attachment_paths:
            paths_json = json.dumps(attachment_paths, ensure_ascii=False)
            return f"{message}\n[附件图片路径列表: {paths_json}]", attachment_paths
        return message, attachment_paths

    async def chat(self, message: str, image_path: str = None, image_paths: list[str] | None = None) -> dict:
        """
        处理用户对话消息

        Args:
            message: 用户文本消息
            image_path: 附带的图片路径（可选）

        Returns:
            Agent 响应字典
        """
        message, _ = self._attachment_message(message, image_path, image_paths)

        if self.executor is None:
            return {"output": self._fallback_reply(message), "intermediate_steps": []}
        try:
            result = await self.executor.ainvoke({"input": message})

            return {
                "output": result["output"],
                "intermediate_steps": result.get("intermediate_steps", []),
            }
        except Exception as e:
            logger.error("Agent 执行异常: %s", str(e), exc_info=True)
            return {
                "output": f"抱歉，处理过程中出现错误：{str(e)}",
                "intermediate_steps": [],
            }

    async def chat_stream(
        self,
        message: str,
        image_path: str = None,
        image_paths: list[str] | None = None,
        user_id: int | None = None,
        scene_id: int | None = None,
    ) -> AsyncGenerator:
        """
        流式处理对话消息（用于 SSE）

        逐个 yield Agent 的思考步骤和最终结果

        Args:
            message: 用户文本消息
            image_path: 单个附带图片或 ZIP 路径（可选）
            image_paths: 多张附带图片路径（可选）

        Yields:
            SSE 事件数据字典
        """
        message, attachment_paths = self._attachment_message(message, image_path, image_paths)

        user_token = _tool_user_id.set(user_id)
        scene_token = _tool_scene_id.set(scene_id)
        try:
            if self.executor is None:
                async for event in self._local_stream(message, attachment_paths):
                    yield event
                return

            async for event in self.executor.astream_events({"input": message}, version="v2"):
                event_kind = event["event"]

                if event_kind == "on_chat_model_stream":
                    # LLM 正在生成回复的文本片段
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        yield {"type": "text_chunk", "content": chunk.content}

                elif event_kind == "on_tool_start":
                    # Agent 开始调用工具
                    tool_name = event["name"]
                    tool_input = event["data"].get("input", {})
                    logger.info("工具调用: %s, 输入: %s", tool_name, str(tool_input)[:200])
                    yield {"type": "tool_call", "tool": tool_name, "input": tool_input}

                elif event_kind == "on_tool_end":
                    # 工具调用完成
                    # 兼容不同 LangChain 版本的 output 路径
                    tool_data = event.get("data", {})
                    tool_output = tool_data.get("output", "")
                    tool_name = event.get("name", "")
                    logger.info(
                        "工具完成: %s, output类型=%s, output长度=%d",
                        tool_name,
                        type(tool_output).__name__,
                        len(str(tool_output)) if tool_output else 0,
                    )
                    # 记录 event data 的所有键，便于调试
                    logger.debug("on_tool_end data keys: %s", list(tool_data.keys()))
                    yield {
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": str(tool_output) if tool_output else "",
                    }

        except Exception as e:
            logger.error("Agent 流式执行异常: %s", str(e), exc_info=True)
            yield {"type": "error", "content": f"处理出错：{str(e)}"}
        finally:
            _tool_user_id.reset(user_token)
            _tool_scene_id.reset(scene_token)

    @staticmethod
    def _fallback_reply(message: str) -> str:
        """未配置外部 LLM 时仍返回明确、不过度承诺的基础回复。"""
        if any(keyword in message for keyword in ("防治", "治疗", "用药")):
            return "请先上传叶片图片完成检测。确认病害类别后，再结合当地登记农药标签、作物生育期和农技部门建议制定防治方案。"
        return "我是果蔬病害检测助手。你可以上传一张或多张叶片图片，也可以上传 ZIP 图片包，我会识别病害并返回标注图和统计结果。"

    async def _local_stream(self, message: str, image_paths: list[str]) -> AsyncGenerator:
        """无 LLM Key 时保留与指导书相同的 Tool/SSE 事件协议。"""
        if not image_paths:
            for chunk in self._text_chunks(self._fallback_reply(message)):
                yield {"type": "text_chunk", "content": chunk}
            return

        if len(image_paths) > 1:
            tool_function = detect_batch_images
            tool_name = "detect_batch_images"
            tool_input = {"image_paths": image_paths}
        elif image_paths[0].lower().endswith(".zip"):
            tool_function = detect_zip_images_file
            tool_name = "detect_zip_images_file"
            tool_input = {"zip_path": image_paths[0]}
        else:
            tool_function = detect_single_image
            tool_name = "detect_single_image"
            tool_input = {"image_path": image_paths[0]}

        yield {"type": "tool_call", "tool": tool_name, "input": tool_input}
        tool_output = await asyncio.to_thread(tool_function.invoke, tool_input)
        yield {"type": "tool_result", "tool": tool_name, "result": tool_output}
        result = json.loads(tool_output)
        if result.get("error"):
            reply = f"检测未完成：{result['error']}"
        else:
            summary = "、".join(f"{name} {count} 个" for name, count in result.get("class_counts", {}).items())
            reply = f"检测完成，共发现 {result.get('total_objects', 0)} 个目标"
            reply += f"，包括 {summary}" if summary else ""
            reply += "。标注图和详细统计已生成。"
        for chunk in self._text_chunks(reply):
            yield {"type": "text_chunk", "content": chunk}

    @staticmethod
    def _text_chunks(text: str, width: int = 12) -> list[str]:
        return [text[index : index + width] for index in range(0, len(text), width)]


# 创建全局单例
detection_agent = DetectionAgent()
