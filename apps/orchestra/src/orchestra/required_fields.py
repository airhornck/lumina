"""内容生成必要字段定义与推断规则。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ContentGenerationIntent:
    """内容生成意图的规范化表示。"""

    kind: str
    platform: str | None = None
    topic: str | None = None
    style: str | None = None
    target_audience: str | None = None
    content_goal: str | None = None


# 字段优先级：每次只询问最靠前的缺失字段
FIELD_ORDER = ["topic", "platform", "style", "target_audience", "content_goal"]

# 平台推断规则
PLATFORM_PATTERNS = {
    "xiaohongshu": r"小红书|xhs|redbook|red",
    "douyin": r"抖音|douyin|tiktok",
    "bilibili": r"b站|bilibili|哔哩哔哩",
    "shipinhao": r"视频号|微信视频号",
    "kuaishou": r"快手|kuaishou",
}

# 风格推断规则
STYLE_PATTERNS = {
    "soft": r"软植入|软一点|软|自然|不.*广告|不像广告",
    "review": r"干货|测评|评测|真实测评|硬核",
    "recommend": r"种草|安利|推荐|必买|清单",
    "story": r"故事|经历|分享|真实故事",
    "tutorial": r"教程|攻略|步骤|怎么做|如何",
}

# 目标人群推断规则
AUDIENCE_PATTERNS = {
    "student": r"学生党|大学生|学生|高中生|初中生",
    "office_worker": r"上班族|白领|打工人|职场",
    "mom": r"宝妈|妈妈|母婴|带娃",
    "beginner": r"新手|小白|入门|刚起步",
}

# 内容目标推断规则
GOAL_PATTERNS = {
    "growth": r"涨粉|爆款|流量|曝光|热门|火",
    "conversion": r"带货|转化|成交|销售|下单|购买",
    "engagement": r"互动|评论|点赞|收藏|转发|讨论",
    "authority": r"人设|专业|信任|专家|权威|ip",
}

# 追问模板（按字段）
CLARIFICATION_TEMPLATES: Dict[str, str] = {
    "topic": "为了写出更贴合你的文案，想先确认一下：**这次的主题或产品是什么？**",
    "platform": "想确认一下：**这次要发哪个平台？**（小红书 / 抖音 / B站 / 视频号）",
    "style": "你希望是什么**风格**？比如软植入、干货测评、种草清单、故事型等。",
    "target_audience": "这篇内容主要面向**哪类人群**？（学生党 / 上班族 / 宝妈 / 新手等）",
    "content_goal": "你希望通过这篇内容达到什么**目的**？（涨粉 / 带货 / 互动 / 立人设）",
}

# 默认配置
DEFAULT_CONTENT_CONFIG: Dict[str, str] = {
    "platform": "xiaohongshu",
    "style": "soft",
    "target_audience": "general",
    "content_goal": "engagement",
}


@dataclass
class ProgressiveCheckResult:
    """渐进式生成检查结果。"""

    is_complete: bool
    collected: Dict[str, Any] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)
    reply: str = ""
    use_defaults: bool = False


def _extract_field(text: str, patterns: Dict[str, str]) -> str | None:
    """从文本中提取第一个匹配的字段值。"""
    if not text:
        return None
    for key, pattern in patterns.items():
        if re.search(pattern, text, re.I):
            return key
    return None


def _extract_topic(user_input: str) -> str | None:
    """从用户输入中提取主题/产品。

    简单实现：寻找"关于/个(.*?)文案/笔记/内容"或"(.*?)文案"中的名词。
    """
    if not user_input:
        return None

    # 模式 1：X 文案 / X 笔记 / X 内容
    m = re.search(r"(?:写|创作|生成).{0,5}?(?:个|篇|一)?(.{2,20}?)(?:文案|笔记|内容|帖子)", user_input)
    if m:
        candidate = m.group(1).strip()
        if candidate and not re.match(r"^[帮我个篇一]$", candidate):
            return candidate

    # 模式 2：关于 X
    m = re.search(r"关于(.{2,20}?)(?:的|文案|笔记|内容)?[？?。.]?$", user_input)
    if m:
        return m.group(1).strip()

    # 模式 3：主题是 X / 话题是 X / 讲 X
    m = re.search(r"(?:主题|话题|讲|说).{0,3}?是(.{2,20}?)(?:的|文案|笔记|内容)?[？?。.]?$", user_input)
    if m:
        return m.group(1).strip()

    return None


def infer_collected_info(
    user_input: str,
    session_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """从用户输入和历史对话中推断已收集的字段信息。"""
    collected: Dict[str, Any] = {}

    # 从当前输入推断
    platform = _extract_field(user_input, PLATFORM_PATTERNS)
    if platform:
        collected["platform"] = platform

    style = _extract_field(user_input, STYLE_PATTERNS)
    if style:
        collected["style"] = style

    audience = _extract_field(user_input, AUDIENCE_PATTERNS)
    if audience:
        collected["target_audience"] = audience

    goal = _extract_field(user_input, GOAL_PATTERNS)
    if goal:
        collected["content_goal"] = goal

    topic = _extract_topic(user_input)
    if topic:
        collected["topic"] = topic

    # 从历史对话中补充
    if session_history:
        for msg in reversed(session_history):
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue

            if "topic" not in collected:
                t = _extract_topic(content)
                if t:
                    collected["topic"] = t

            if "platform" not in collected:
                p = _extract_field(content, PLATFORM_PATTERNS)
                if p:
                    collected["platform"] = p

            if "style" not in collected:
                s = _extract_field(content, STYLE_PATTERNS)
                if s:
                    collected["style"] = s

            if "target_audience" not in collected:
                a = _extract_field(content, AUDIENCE_PATTERNS)
                if a:
                    collected["target_audience"] = a

            if "content_goal" not in collected:
                g = _extract_field(content, GOAL_PATTERNS)
                if g:
                    collected["content_goal"] = g

    return collected


def get_missing_fields(
    collected: Dict[str, Any],
    required_fields: Optional[List[str]] = None,
) -> List[str]:
    """获取缺失字段，按优先级排序。"""
    required = required_fields or FIELD_ORDER
    return [f for f in required if f not in collected or collected[f] is None]


def build_clarification_reply(missing_fields: List[str]) -> str:
    """构建追问回复。"""
    if not missing_fields:
        return ""
    first = missing_fields[0]
    return CLARIFICATION_TEMPLATES.get(
        first,
        f"为了给你更准确的内容，能否补充一下：**{first}**？",
    )
