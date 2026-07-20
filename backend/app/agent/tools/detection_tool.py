"""
检测工具集 — Agent 可调用的检测相关工具

工具列表：
  - detect_single_image: 单张图片检测
  - detect_batch_images: 批量图片检测
  - detect_zip_images_file: ZIP 文件解压检测
  - detect_video_file: 视频文件检测

设计原则：
  - 每个工具使用 @tool 装饰器定义
  - docstring 必须详细，LLM 通过 docstring 理解工具用途
  - 返回值使用 JSON 字符串，便于 LLM 解析
"""

import contextvars
import json

from app.core.logger import get_logger
from app.config.detection import DetectionConfig
from app.services.detection_service import detection_service
from langchain_core.tools import tool

logger = get_logger(__name__)

# Agent 工具运行在独立调用链中，使用 ContextVar 隔离并发请求的用户、场景和语言。
_tool_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "detection_tool_user_id", default=None
)
_tool_scene_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "detection_tool_scene_id", default=None
)
_tool_display_language: contextvars.ContextVar[str] = contextvars.ContextVar(
    "detection_tool_display_language", default="zh"
)


def set_detection_tool_context(
    user_id: int | None, scene_id: int | None, display_language: str
):
    """写入本轮检测工具上下文，并返回请求结束时恢复所需的令牌。"""
    return (
        _tool_user_id.set(user_id),
        _tool_scene_id.set(scene_id),
        _tool_display_language.set(display_language),
    )


def reset_detection_tool_context(tokens) -> None:
    """恢复检测工具上下文，防止并发请求之间串用用户或语言信息。"""
    user_token, scene_token, language_token = tokens
    _tool_user_id.reset(user_token)
    _tool_scene_id.reset(scene_token)
    _tool_display_language.reset(language_token)


@tool
def detect_single_image(
    image_path: str,
    conf: float = DetectionConfig.conf_threshold,
    iou: float = DetectionConfig.iou_threshold,
) -> str:
    """检测单张遥感图片中的目标物体（飞机、油罐、立交桥、操场）。

    当用户上传了一张图片并要求检测、识别、分析图中的目标时使用此工具。

    Args:
        image_path: 图片文件的服务器路径（绝对路径），如 /tmp/rsod_uploads/xxx.jpg
        conf: 置信度阈值，0~1 之间，默认使用 DetectionConfig.conf_threshold。低于此值的检测结果会被过滤
        iou: NMS（非极大值抑制）IoU 阈值，0~1 之间，默认使用 DetectionConfig.iou_threshold。用于去除重叠的检测框

    Returns:
        JSON 字符串，包含：
        - total_objects: 检测到的目标总数
        - class_counts: 各类别目标数量统计
        - objects: 每个目标的详细信息（类别、置信度、边界框）
        - inference_time: 推理耗时（毫秒）
        - annotated_image_url: 标注后的图片 URL
    """
    try:
        result = detection_service.detect_single(
            image_path,
            conf=conf,
            iou=iou,
            user_id=_tool_user_id.get(),
            scene_id=_tool_scene_id.get(),
            display_language=_tool_display_language.get(),
        )
        logger.info(
            "单图检测完成: %s, 目标数: %d", image_path, result.get("total_objects", 0)
        )
        result.pop("annotated_image_base64", None)
        result.pop("detections", None)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error("单图检测失败: %s, 错误: %s", image_path, str(e))
        return json.dumps({"error": f"检测失败: {str(e)}"}, ensure_ascii=False)


@tool
def detect_batch_images(
    image_paths: list[str], conf: float = DetectionConfig.conf_threshold
) -> str:
    """批量检测多张遥感图片中的目标物体。

    当用户一次上传了多张图片，或者要求"检测所有图片"时使用此工具。

    Args:
        image_paths: 图片文件路径列表
        conf: 置信度阈值，默认使用 DetectionConfig.conf_threshold

    Returns:
        JSON 字符串，包含每张图片的检测结果汇总
    """
    try:
        result = detection_service.detect_batch(
            image_paths,
            conf=conf,
            user_id=_tool_user_id.get(),
            scene_id=_tool_scene_id.get(),
            display_language=_tool_display_language.get(),
        )
        logger.info("批量检测完成: %d 张图片", len(image_paths))
        result.pop("annotated_image_base64", None)
        result.pop("detections", None)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error("批量检测失败: %s", str(e))
        return json.dumps({"error": f"批量检测失败: {str(e)}"}, ensure_ascii=False)


@tool
def detect_zip_images_file(
    zip_path: str, conf: float = DetectionConfig.conf_threshold
) -> str:
    """解压 ZIP 文件并批量检测其中所有图片的目标物体。

    当用户上传了 ZIP 压缩包进行批量检测时使用此工具。

    Args:
        zip_path: ZIP 文件的服务器路径
        conf: 置信度阈值，默认使用 DetectionConfig.conf_threshold

    Returns:
        JSON 字符串，包含 ZIP 内所有图片的检测结果汇总
    """
    try:
        result = detection_service.detect_zip(
            zip_path,
            conf=conf,
            user_id=_tool_user_id.get(),
            scene_id=_tool_scene_id.get(),
            display_language=_tool_display_language.get(),
        )
        logger.info("ZIP 检测完成: %s", zip_path)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error("ZIP 检测失败: %s", str(e))
        result.pop("annotated_image_base64", None)
        result.pop("detections", None)
        return json.dumps({"error": f"ZIP 检测失败: {str(e)}"}, ensure_ascii=False)


@tool
def detect_video_file(
    video_path: str,
    conf: float = DetectionConfig.conf_threshold,
    frame_sample_rate: int = 5,
) -> str:
    """检测视频文件中的目标物体。对视频进行帧采样后逐帧检测。

    当用户上传了视频文件并要求检测视频中的目标时使用此工具。

    Args:
        video_path: 视频文件的服务器路径（mp4/avi/mov 等格式）
        conf: 置信度阈值，默认使用 DetectionConfig.conf_threshold
        frame_sample_rate: 帧采样间隔，每 N 帧取 1 帧进行检测，默认 5

    Returns:
        JSON 字符串，包含视频检测结果（关键帧目标统计、视频时长、处理帧数）
    """
    try:
        result = detection_service.detect_video(
            video_path,
            conf=conf,
            frame_sample_rate=frame_sample_rate,
            user_id=_tool_user_id.get(),
            scene_id=_tool_scene_id.get(),
            display_language=_tool_display_language.get(),
        )
        # 前端会使用标注视频地址和关键帧恢复结果，不能在工具层删除这些字段。
        result["type"] = "video"
        logger.info("视频检测完成: %s", video_path)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error("视频检测失败: %s", str(e))
        return json.dumps({"error": f"视频检测失败: {str(e)}"}, ensure_ascii=False)


# 检测工具列表
DETECTION_TOOLS = [
    detect_single_image,
    detect_batch_images,
    detect_zip_images_file,
    detect_video_file,
]
