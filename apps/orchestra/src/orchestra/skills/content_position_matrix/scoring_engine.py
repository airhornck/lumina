"""定位矩阵评分引擎。"""

from __future__ import annotations

import re
from typing import Any


_PROFESSIONAL_TERMS = {
    "成分", "测评", "教程", "步骤", "数据", "研究", "原理", "攻略", "指南",
    "配方", "浓度", "功效", "对比", "实验", "分析", "专业", "方法",
}

_DATA_CASE_PATTERNS = [
    re.compile(r"\d+\s*[%-]?"),  # 数字+百分号
    re.compile(r"提升|下降|增加|减少|改善.*\d+"),
    re.compile(r"实测|实验|对比|案例"),
]

_STRUCTURE_PATTERNS = [
    re.compile(r"第[一二三四五六七八九十\d]+[步点条]"),
    re.compile(r"^[\s]*[\d\-\*•]+[\.、\s]", re.M),
    re.compile(r"首先|其次|然后|最后|总结"),
]

_EMOTION_WORDS = {
    "震惊", "没想到", "竟然", "绝了", "救命", "天呐", "卧槽", "泪目",
    "破防", "上头", "治愈", "爽", "怒", "笑死", "哭死", "爱了",
}

_NARRATIVE_TENSION_WORDS = {
    "但是", "然而", "没想到", "竟然", "反转", "结果", "最后", "原来",
    "揭秘", "真相", "结局",
}

_INTERACTION_HOOKS = {
    "评论区", "你怎么看", "你也有吗", "告诉我", "一起", "求问",
    "有没有", "对吗", "是不是",
}

_VISUAL_IMPACT_WORDS = {
    "对比", "前后", "特写", "放大", "素颜", "原相机", "无滤镜",
    "Before", "After",
}


def _count_matches(text: str, patterns: list[Any]) -> int:
    return sum(1 for p in patterns if p.search(text))


def score_professional(text: str) -> float:
    """专业度评分 1-10。"""
    text = text or ""
    base = 3.0

    # 信息密度
    chars = len(text)
    paragraphs = max(1, text.count("\n") + 1)
    density = chars / paragraphs
    info_score = min(2.5, density / 80)

    # 专业术语
    term_count = sum(1 for term in _PROFESSIONAL_TERMS if term in text)
    term_score = min(2.0, term_count * 0.4)

    # 数据/案例
    data_count = _count_matches(text, _DATA_CASE_PATTERNS)
    data_score = min(1.5, data_count * 0.5)

    # 结构清晰度
    structure_count = _count_matches(text, _STRUCTURE_PATTERNS)
    structure_score = min(1.5, structure_count * 0.5)

    return min(10.0, round(base + info_score + term_score + data_score + structure_score, 1))


def score_entertainment(text: str) -> float:
    """娱乐度评分 1-10。"""
    text = text or ""
    base = 3.0

    # 情绪激发
    emotion_count = sum(1 for word in _EMOTION_WORDS if word in text)
    emotion_score = min(2.0, emotion_count * 0.5)

    # emoji
    emoji_count = len(re.findall(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]", text))
    emoji_score = min(1.0, emoji_count * 0.3)

    # 叙事张力
    tension_count = sum(1 for word in _NARRATIVE_TENSION_WORDS if word in text)
    tension_score = min(2.0, tension_count * 0.4)

    # 互动引导
    interaction_count = sum(1 for phrase in _INTERACTION_HOOKS if phrase in text)
    interaction_score = min(1.5, interaction_count * 0.5)

    # 视觉冲击
    visual_count = sum(1 for word in _VISUAL_IMPACT_WORDS if word in text)
    visual_score = min(1.5, visual_count * 0.4)

    return min(10.0, round(base + emotion_score + emoji_score + tension_score + interaction_score + visual_score, 1))


def predict_engagement_intensity(professional: float, entertainment: float) -> float:
    """基于专业度和娱乐度预测互动强度。"""
    base = 0.02
    return min(1.0, round(base + professional * 0.005 + entertainment * 0.008, 3))


def classify_intensity_level(intensity: float) -> str:
    if intensity > 0.10:
        return "超高互动"
    if intensity > 0.05:
        return "高互动"
    if intensity > 0.02:
        return "中等互动"
    return "低互动"
