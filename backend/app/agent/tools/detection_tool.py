"""Detection tools callable by the Agent."""

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
    """Detect plant disease targets in a single uploaded image.

    Use this tool when the user uploads one image and asks for detection,
    recognition, or analysis of disease targets in that image.

    Args:
        image_path: Absolute server path of the image, such as /tmp/rsod_uploads/xxx.jpg.
        conf: Confidence threshold from 0 to 1. Detections below this value are filtered out.
        iou: NMS IoU threshold from 0 to 1, used to remove overlapping boxes.

    Returns:
        JSON string with total_objects, class_counts, detections,
        inference_time, task_id, and annotated image URL/base64 fields.
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
    """Detect plant disease targets in multiple uploaded images.

    Use this tool when the user uploads multiple images or asks to detect all images.

    Args:
        image_paths: List of server-side image paths.
        conf: Confidence threshold from 0 to 1.

    Returns:
        JSON string containing the batch detection summary and per-image results.
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
    """Extract a ZIP file and detect disease targets in all images inside it.

    Use this tool when the user uploads a ZIP archive for batch detection.

    Args:
        zip_path: Server-side path of the ZIP file.
        conf: Confidence threshold from 0 to 1.

    Returns:
        JSON string containing detection results for all valid images in the ZIP file.
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
    """Detect plant disease targets in an uploaded video by sampling frames.

    Use this tool when the user uploads a video and asks for video detection.

    Args:
        video_path: Server-side path of the video file, such as mp4, avi, or mov.
        conf: Confidence threshold from 0 to 1.
        frame_sample_rate: Frame sampling interval. Every Nth frame is processed.

    Returns:
        JSON string containing key-frame results, duration, processed frame count,
        object statistics, and annotated/source video URLs when available.
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
