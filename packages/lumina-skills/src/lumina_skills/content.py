from __future__ import annotations

import json
from typing import Any, Dict, List

from knowledge_base.platform_registry import PlatformRegistry

from lumina_skills.methodology_utils import (
    build_methodology_prompt,
    list_available_methodologies,
    match_methodology_for_content,
)
from lumina_skills.tool_skills import fetch_industry_news


async def generate_text(
    topic: str,
    platform: str,
    content_dna: Dict[str, Any],
    methodology_hint: str = "AIDA",
    user_id: str = "anonymous",
    constraints: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    constraints = constraints or {}
    spec = PlatformRegistry().load(platform)
    dna = {**content_dna, "platform_spec_snippet": spec.content_dna[:2]}

    # 解析并注入方法论详情
    meth_id = methodology_hint.lower().replace(" ", "_").replace("-", "_")
    meth_prompt = build_methodology_prompt(meth_id)
    if not meth_prompt:
        # 如果精确ID未命中，尝试用 topic 匹配一次
        matched = match_methodology_for_content(topic)
        meth_id = matched or meth_id
        meth_prompt = build_methodology_prompt(meth_id) or f"方法论提示：{methodology_hint}"

    try:
        from llm_hub import get_client

        client = get_client(skill_name="generate_text")
        if client and client.config.api_key:
            prompt = (
                f"为主题「{topic}」写{platform}文案。\n\n"
                f"{meth_prompt}\n\n"
                f"DNA 参数：{json.dumps(dna, ensure_ascii=False)[:800]}，约束：{constraints}。"
                '输出 JSON：{"title","content","hashtags":[]}'
            )
            raw = await client.complete(
                prompt, response_format={"type": "json_object"}, temperature=0.7
            )
            data = json.loads(raw)
            return {
                "title": data.get("title", topic),
                "content": data.get("content", ""),
                "hashtags": data.get("hashtags") or [],
                "hook_analysis": {"type": "curiosity", "position": "0-3s", "strength": 0.7},
                "platform_optimization": {"tips": list(spec.content_dna[:3])},
                "methodology_used": meth_id,
                "user_id": user_id,
            }
    except Exception:
        pass

    return {
        "title": f"{topic}｜{platform}",
        "content": f"（占位）{methodology_hint} 结构下围绕「{topic}」展开，DNA={list(dna)[:2]}。",
        "hashtags": [topic[:10], platform],
        "hook_analysis": {"type": "placeholder", "position": "opening", "strength": 0.5},
        "platform_optimization": {"tips": [str(x) for x in spec.content_dna[:2]]},
        "methodology_used": meth_id,
        "user_id": user_id,
    }


async def generate_script(
    topic: str,
    hook_type: str,
    duration: int,
    platform: str,
    user_id: str,
    visual_elements: List[str] | None = None,
    methodology_hint: str = "",
) -> Dict[str, Any]:
    visual_elements = visual_elements or []

    meth_id = ""
    meth_prompt = ""
    if methodology_hint:
        meth_id = methodology_hint.lower().replace(" ", "_").replace("-", "_")
        meth_prompt = build_methodology_prompt(meth_id)
    if not meth_prompt:
        matched = match_methodology_for_content(topic, content_type="video")
        meth_id = matched or "story_arc"
        meth_prompt = build_methodology_prompt(meth_id) or "方法论提示：故事弧线结构"

    # 可扩展：将 meth_prompt 注入 LLM 生成脚本；当前为占位返回
    return {
        "hook_script": f"【{hook_type}】3 秒内抓住注意力：{topic[:40]}…",
        "full_script": f"口播稿占位，时长约 {duration}s，平台 {platform}。方法论：{meth_id}",
        "shot_list": [
            {"timestamp": "0-3s", "visual": "特写", "audio": "钩子", "text": topic[:20]},
            {"timestamp": "3-15s", "visual": "演示", "audio": "展开", "text": "主体"},
        ],
        "bgm_suggestion": "轻快电子（占位）",
        "caption_highlights": visual_elements or ["字幕关键词1", "字幕关键词2"],
        "methodology_used": meth_id,
        "user_id": user_id,
    }


async def select_topic(
    industry: str,
    user_id: str,
    platform: str,
    account_stage: str = "growth",
    hot_topics: List[str] | None = None,
) -> Dict[str, Any]:
    hot_topics = hot_topics or []
    news = await fetch_industry_news(category=industry, days=3)
    nlist = news.get("news_list") or []
    topics = []

    available_methods = list_available_methodologies()
    if not available_methods:
        available_methods = ["aida_advanced"]

    for i, item in enumerate(nlist[:5]):
        # 动态轮换真实存在的方法论
        meth = available_methods[i % len(available_methods)]
        topics.append(
            {
                "topic": item.get("title", f"选题{i}"),
                "score": 0.85 - i * 0.05,
                "reason": "结合新闻占位与账号阶段 " + account_stage,
                "methodology": meth,
            }
        )
    for ht in hot_topics[:3]:
        # 热点默认用 trend_ride，若不存在则回退第一个可用
        meth = "trend_ride" if "trend_ride" in available_methods else available_methods[0]
        topics.append(
            {"topic": ht, "score": 0.75, "reason": "用户指定热点", "methodology": meth}
        )
    return {
        "recommended_topics": topics,
        "content_calendar": [{"day_offset": j, "topic": topics[j % len(topics)]["topic"]} for j in range(min(3, max(1, len(topics))))],
        "trend_analysis": news.get("trend_prediction", ""),
        "user_id": user_id,
        "platform": platform,
    }
