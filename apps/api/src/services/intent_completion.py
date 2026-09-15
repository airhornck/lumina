"""短消息意图补全逻辑（阶段五 P1-8/P1-9）。

检测省略表达（「那么图文的又咋做」「接上一个问题」等），
结合最近一轮对话历史补全为完整意图；低置信度时返回 None 以走确认流程。
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 省略/指代标记词
_REFERENCE_MARKERS = [
    "那么", "那", "接上", "接上", "刚才", "刚才那个", "之前",
    "上面的", "上一条", "上一个", "继续", "接着说", "接下去",
    "然后", "还有", "另外", "同样的", "类似的",
]

# 表示要求确认的格式
_CONFIRMATION_PATTERNS = [
    r"^[是还]?\s*[吗嘛吧]?\s*$",
    r"^然后呢\s*$",
    r"^所以呢\s*$",
    r"^什么意思\s*$",
    r"^能具体点吗\s*$",
]


def is_likely_referencing(message: str) -> bool:
    """检测当前消息是否可能包含指代/省略表达。"""
    if not message or len(message) < 3:
        return True
    msg_lower = message.lower().strip()
    for marker in _REFERENCE_MARKERS:
        if marker in msg_lower:
            return True
    # 纯疑问词或非常短的消息
    if len(message) < 5 and any(w in message for w in ["呢", "吗", "嘛", "吧", "?"]):
        return True
    return False


def get_last_topic_from_history(
    session_history: List[Dict[str, str]],
) -> Optional[str]:
    """从对话历史中提取最近的话题（取最后一轮 assistant 回复的前 100 字）。"""
    if not session_history:
        return None
    # 倒序找最后一条 assistant 消息
    for msg in reversed(session_history):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            # 取前 100 字作为话题摘要
            return content[:100] if len(content) > 100 else content
    return None


def get_last_user_message(
    session_history: List[Dict[str, str]],
) -> Optional[str]:
    """从对话历史中获取最近一条用户消息。"""
    if not session_history:
        return None
    for msg in reversed(session_history):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return None


def complete_intent(
    message: str,
    session_history: List[Dict[str, str]],
) -> str:
    """尝试补全短消息意图。

    如果消息明显是省略表达，返回补全后的意图描述；
    如果置信度低，返回空字符串让调用方走确认流程。
    """
    if not is_likely_referencing(message):
        return ""

    last_topic = get_last_topic_from_history(session_history)
    if not last_topic:
        return ""

    # 补全逻辑
    # "那么图文的又咋做" → "基于上一轮的主题，生成对应的图文内容"
    # "接上一个问题" → "继续上一个问题"
    patterns = [
        # "那么图文的又咋做" / "那图文呢" — 跨格式
        (r"(图文|图片|图文版|图片版|图文内容)", "用户希望基于上一轮主题生成对应的图文内容。"),
        # "那么视频的呢" — 跨格式
        (r"(视频|视频版|短视频)", "用户希望基于上一轮主题生成对应的视频内容。"),
        # "接上一个问题" / "继续"
        (r"(接上|继续|接着说)", "用户希望继续上一个话题。"),
        # "然后呢" / "还有呢"
        (r"(然后|还有|另外)", "用户在追问上一轮主题的更多信息。"),
    ]

    for pattern, completion in patterns:
        if re.search(pattern, message):
            logger.info(
                "Intent completion matched pattern=%r for message=%r, last_topic_head=%r",
                pattern, message, last_topic[:50],
            )
            return f"基于上一轮话题「{last_topic[:80]}」，{completion}"

    # 兜底：非常短的消息但指代词匹配
    if len(message) < 8:
        logger.info(
            "Short message detected, fallback completion for=%r, last_topic_head=%r",
            message, last_topic[:50],
        )
        return f"用户输入为「{message}」，基于上一轮话题「{last_topic[:80]}」继续回答。"

    return ""


def needs_confirmation(message: str, completion: str) -> bool:
    """判断补全结果是否置信度低，需要向用户确认。"""
    if not completion:
        return False
    # 如果用户原本消息已经比较长（>15字），通常不请求确认
    if len(message) > 15:
        return False
    # 如果补全内容完全基于"兜底"规则，建议确认
    if "用户输入为" in completion and "继续回答" in completion:
        return True
    return False
