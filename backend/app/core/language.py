"""面向用户响应的请求级语言解析工具。"""

from typing import Any

# 当前仅支持中文和英文；未识别值统一回退中文。
SUPPORTED_LANGUAGES = {"zh", "en"}
DEFAULT_LANGUAGE = "zh"


def normalize_language(value: str | None) -> str:
    """把浏览器或接口语言值归一化为 ``zh`` 或 ``en``。"""
    if not value:
        return DEFAULT_LANGUAGE
    value = value.split(",", 1)[0].strip().lower().replace("_", "-")
    if value.startswith("zh"):
        return "zh"
    if value.startswith("en"):
        return "en"
    return DEFAULT_LANGUAGE


def request_language(request: Any, user: Any = None) -> str:
    """优先使用请求头，其次使用用户已保存的语言偏好。"""
    header_value = request.headers.get("X-Display-Language") if request else None
    if header_value:
        return normalize_language(header_value)
    return normalize_language(getattr(user, "display_language", None))
