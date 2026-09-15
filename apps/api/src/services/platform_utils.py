"""平台相关工具函数：从历史消息/工具参数中提取、归一化、校验平台。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# 平台别名映射到统一标识
PLATFORM_ALIASES: Dict[str, str] = {
    # 视频号
    "视频号": "shipinhao",
    "shipinhao": "shipinhao",
    "shipin": "shipinhao",
    "微信视频号": "shipinhao",
    # 小红书
    "小红书": "xiaohongshu",
    "xiaohongshu": "xiaohongshu",
    "xhs": "xiaohongshu",
    "redbook": "xiaohongshu",
    "red": "xiaohongshu",
    # 抖音
    "抖音": "douyin",
    "douyin": "douyin",
    "tiktok": "douyin",
    # B站
    "b站": "bilibili",
    "bilibili": "bilibili",
    "哔哩哔哩": "bilibili",
    # 快手
    "快手": "kuaishou",
    "kuaishou": "kuaishou",
    # 微博
    "微博": "weibo",
    "weibo": "weibo",
    # 知乎
    "知乎": "zhihu",
    "zhihu": "zhihu",
    # 微信公众号
    "微信公众号": "wechat_official",
    "公众号": "wechat_official",
    "微信": "wechat_official",
    "wechat": "wechat_official",
    "wechat_official": "wechat_official",
}

# 用于正则匹配的平台关键词（按长度降序，避免"小红书"被"红书"误匹配）
PLATFORM_KEYWORDS = sorted(PLATFORM_ALIASES.keys(), key=len, reverse=True)


def normalize_platform(platform: Optional[str]) -> Optional[str]:
    """将平台名称/别名归一化为统一标识。"""
    if not platform:
        return None
    p = platform.strip().lower()
    return PLATFORM_ALIASES.get(p) or PLATFORM_ALIASES.get(p.replace(" ", ""))


def extract_platform_from_text(text: str) -> Optional[str]:
    """从文本中提取平台关键词，返回统一标识。"""
    if not text:
        return None
    text_lower = text.lower()
    for keyword in PLATFORM_KEYWORDS:
        if keyword.lower() in text_lower:
            return PLATFORM_ALIASES[keyword]
    return None


def extract_platform_from_history(
    history: List[Dict[str, Any]],
    *,
    include_assistant: bool = False,
) -> Optional[str]:
    """从历史消息中提取用户声明的平台（倒序优先，最近消息优先）。"""
    # 倒序遍历，最近消息优先
    for msg in reversed(history):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        if role == "assistant" and not include_assistant:
            continue
        content = msg.get("content")
        if not isinstance(content, str):
            continue
        platform = extract_platform_from_text(content)
        if platform:
            return platform
    return None


def detect_multi_platform_intent(text: str) -> bool:
    """检测用户是否明确表达多平台对比/跨平台意图。"""
    if not text:
        return False
    text_lower = text.lower()
    contrast_markers = [
        "对比",
        "比较",
        "vs",
        "versus",
        "分别",
        "各平台",
        "多个平台",
        "跨平台",
        "都适合做",
        "哪里更适合",
    ]
    return any(marker in text_lower for marker in contrast_markers)


def resolve_platform_for_request(
    current_message: str,
    history: List[Dict[str, Any]],
    explicit_platform: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """为当前请求解析应使用的平台。

    返回: (platform, source)
    source 取值：
    - explicit: 请求体中显式传入的 platform
    - current_message: 从当前消息中提取
    - history: 从历史消息中提取（用户之前声明过）
    - inferred: 从 assistant 历史消息中推断（兜底）
    - none: 未识别到平台
    """
    # 1. 显式传入优先
    if explicit_platform:
        normalized = normalize_platform(explicit_platform)
        if normalized:
            return normalized, "explicit"

    # 2. 当前消息提取
    from_current = extract_platform_from_text(current_message)
    if from_current:
        return from_current, "current_message"

    # 3. 历史消息中提取（仅限 user 消息，避免 assistant 自说自话）
    from_history = extract_platform_from_history(history, include_assistant=False)
    if from_history:
        return from_history, "history"

    # 4. 兜底：从 assistant 历史消息中推断（平台可能由 assistant 在之前的工具调用中确认）
    from_assistant = extract_platform_from_history(history, include_assistant=True)
    if from_assistant:
        return from_assistant, "inferred"

    return None, "none"


def detect_platform_change_in_message(
    message: str,
    current_profile_platform: str | None,
) -> tuple[bool, str | None]:
    """检测用户消息中是否包含与当前画像平台不同的新平台声明。
    
    返回: (is_changed, new_platform)
    - is_changed: 是否检测到平台变更
    - new_platform: 新的平台标识（如果有）
    """
    if not current_profile_platform:
        return False, None
    
    extracted = extract_platform_from_text(message)
    if extracted and extracted != current_profile_platform:
        return True, extracted
    return False, None


def align_tool_platforms(
    tools: List[Dict[str, Any]],
    resolved_platform: Optional[str],
    current_message: str,
) -> List[Dict[str, Any]]:
    """对一次请求中的多个工具调用进行平台归一校验。

    - 如果用户明确表达多平台对比意图，保持不变
    - 如果已解析出统一平台，将所有工具 platform 参数统一为该平台
    - 否则返回原参数（依赖 LLM 自身判断）
    """
    if not tools:
        return tools

    if detect_multi_platform_intent(current_message):
        return tools

    if not resolved_platform:
        return tools

    aligned = []
    for tool in tools:
        if not isinstance(tool, dict):
            aligned.append(tool)
            continue
        name = tool.get("name") or tool.get("function", {}).get("name")
        args = tool.get("args") or tool.get("function", {}).get("arguments", {}) or {}
        # 仅处理已知含 platform 参数的工具
        if isinstance(args, dict) and "platform" in args:
            current = normalize_platform(args.get("platform"))
            if current != resolved_platform:
                args = dict(args)
                args["platform"] = resolved_platform
        aligned.append({"name": name, "args": args})
    return aligned
