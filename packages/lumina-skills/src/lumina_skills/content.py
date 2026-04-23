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

try:
    from llm_hub import get_client
except Exception:
    get_client = None  # type: ignore


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
        matched = match_methodology_for_content(topic)
        meth_id = matched or meth_id
        meth_prompt = build_methodology_prompt(meth_id) or f"方法论提示：{methodology_hint}"

    # 提取平台图文规范与审核规则
    platform_constraints = []
    text_format = (
        spec.content_formats.get("图文", {})
        or spec.content_formats.get("仅文字", {})
        or {}
    )
    if text_format:
        content_cfg = text_format.get("content", {})
        if content_cfg:
            platform_constraints.append(f"正文限制：{content_cfg}")
        title_cfg = text_format.get("title", {})
        if title_cfg:
            platform_constraints.append(f"标题限制：{title_cfg}")
        tag_cfg = text_format.get("tags", {})
        if tag_cfg:
            platform_constraints.append(f"标签限制：{tag_cfg}")

    dna_info = [f"{d.get('element', '')}: {d.get('value', '')}" for d in spec.content_dna[:5]]
    audit_info = []
    for rule in spec.audit_rules[:3]:
        terms = rule.get("forbidden_terms", [])
        if terms:
            audit_info.append(f"{rule.get('category', '未知')}类禁用词：{', '.join(terms)}")

    try:
        client = get_client(skill_name="generate_text")
        if client and client.config.api_key:
            output_example = {
                "title": "吸引人的标题（严格符合平台长度限制）",
                "content": "正文内容，口语化、有节奏感，适合平台调性",
                "hashtags": ["标签1", "标签2", "标签3"],
            }
            prompt_parts = [
                f"你是一位专业的社交媒体文案策划师。请为主题「{topic}」撰写一份{platform}平台的图文文案。",
                f"",
                f"【方法论指引】",
                meth_prompt,
                f"",
                f"【用户 DNA 与约束】",
                f"DNA 参数：{json.dumps(dna, ensure_ascii=False)[:600]}",
                f"额外约束：{constraints}",
                f"",
                f"【平台规范】",
                "\n".join(platform_constraints or ["按平台通用规范创作"]),
            ]
            if dna_info:
                prompt_parts += [f"", f"【平台内容 DNA】", "\n".join(dna_info)]
            if audit_info:
                prompt_parts += [f"", f"【审核合规】", "\n".join(audit_info)]
            prompt_parts += [
                f"",
                f"要求：",
                f"1. title 必须严格符合平台标题长度限制，吸引人且口语化；",
                f"2. content 必须是完整的正文文案，带节奏感，适合直接发布；",
                f"3. hashtags 给出 3-8 个精准标签，与主题高度相关；",
                f"4. 严格遵守平台审核规则，禁用词一个都不能出现；",
                f"5. 结合用户 DNA 参数调整语气和风格。",
                f"",
                f"请严格按以下 JSON 格式输出，不要包含任何解释性文字，只返回合法 JSON：",
                json.dumps(output_example, ensure_ascii=False, indent=2),
            ]
            prompt = "\n".join(prompt_parts)

            raw = await client.complete(
                prompt, response_format={"type": "json_object"}, temperature=0.7, max_tokens=2000
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

    # Fallback：LLM 失败时返回带警告的降级内容
    return {
        "title": f"{topic}｜{platform}（系统提示：文案生成服务暂时不可用）",
        "content": f"（系统提示：文案生成服务暂时不可用，未能为「{topic}」生成完整内容。请稍后重试或联系管理员。占位信息：{methodology_hint} 结构，平台 {platform}）",
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

    # 加载平台规范并提取约束
    spec = PlatformRegistry().load(platform)
    platform_constraints = []
    video_format = spec.content_formats.get("视频", {}) if spec.content_formats else {}
    if video_format:
        vd = video_format.get("video_duration", {})
        if vd:
            platform_constraints.append(f"视频时长限制：{vd}")
        content_cfg = video_format.get("content", {})
        if content_cfg:
            platform_constraints.append(f"口播稿字数建议：{content_cfg}")
        title_cfg = video_format.get("title", {})
        if title_cfg:
            platform_constraints.append(f"标题限制：{title_cfg}")
        tag_cfg = video_format.get("tags", {})
        if tag_cfg:
            platform_constraints.append(f"标签限制：{tag_cfg}")

    dna_info = [f"{d.get('element', '')}: {d.get('value', '')}" for d in spec.content_dna[:5]]
    audit_info = []
    for rule in spec.audit_rules[:3]:
        terms = rule.get("forbidden_terms", [])
        if terms:
            audit_info.append(f"{rule.get('category', '未知')}类禁用词：{', '.join(terms)}")

    # 按约 4 字/秒估算口播稿字数（240 字/分钟）
    estimated_words = int(duration * 4)

    try:
        client = get_client(skill_name="generate_script")
        if client and client.config.api_key:
            # 构造输出格式示例
            output_example = {
                "hook_script": "前3秒钩子话术，必须口语化、有冲击感，能在3秒内抓住注意力",
                "full_script": "完整口播稿，口语化、有节奏感，时长严格对应约X秒（约X字）",
                "shot_list": [
                    {
                        "timestamp": "0-3s",
                        "visual": "画面描述（景别+内容，如：特写-主播惊讶表情）",
                        "audio": "声音/音效说明（如：语气停顿+轻快节奏入点）",
                        "text": "画面文字/字幕（如：你真的知道？）",
                    }
                ],
                "bgm_suggestion": "背景音乐风格与情绪描述（如：轻快电子，节奏明快，适合种草类内容）",
                "caption_highlights": ["关键词1", "关键词2", "关键词3"],
            }

            prompt_parts = [
                f"你是一位专业的短视频脚本策划师。请为以下需求生成一份完整的视频脚本方案。",
                f"",
                f"【主题】{topic}",
                f"【平台】{platform}",
                f"【目标时长】{duration}秒（口播稿字数建议控制在 {estimated_words} 字左右）",
                f"【钩子类型】{hook_type}",
                f"【视觉元素要求】{', '.join(visual_elements) if visual_elements else '无特殊要求'}",
                f"",
                f"【方法论指引】",
                meth_prompt,
                f"",
                f"【平台规范】",
                "\n".join(platform_constraints or ["按平台通用规范创作"]),
            ]
            if dna_info:
                prompt_parts += [f"", f"【平台内容 DNA】", "\n".join(dna_info)]
            if audit_info:
                prompt_parts += [f"", f"【审核合规】", "\n".join(audit_info)]
            prompt_parts += [
                f"",
                f"要求：",
                f"1. hook_script 必须是能在前3秒抓住注意力的口语化钩子，不要套路化；",
                f"2. full_script 必须是完整的口播稿，带时间节奏感，适合直接录制；",
                f"3. shot_list 必须按 {duration} 秒合理拆分镜头，每个镜头有明确的时间戳、画面、声音、字幕；",
                f"4. bgm_suggestion 给出具体音乐风格和情绪，不要只说'轻快电子'；",
                f"5. caption_highlights 提取 3-5 个必须在字幕中突出的关键词；",
                f"6. 严格遵守平台审核规则，禁用词一个都不能出现。",
                f"",
                f"请严格按以下 JSON 格式输出，不要包含任何解释性文字，只返回合法 JSON：",
                json.dumps(output_example, ensure_ascii=False, indent=2),
            ]
            prompt = "\n".join(prompt_parts)

            raw = await client.complete(
                prompt,
                response_format={"type": "json_object"},
                temperature=0.75,
                max_tokens=2500,
            )
            data = json.loads(raw)

            shot_list = data.get("shot_list") or []
            if isinstance(shot_list, str):
                try:
                    shot_list = json.loads(shot_list)
                except Exception:
                    shot_list = []

            return {
                "hook_script": data.get("hook_script", f"【{hook_type}】{topic[:40]}"),
                "full_script": data.get("full_script", ""),
                "shot_list": shot_list,
                "bgm_suggestion": data.get("bgm_suggestion", ""),
                "caption_highlights": data.get("caption_highlights") or visual_elements or [],
                "methodology_used": meth_id,
                "user_id": user_id,
            }
    except Exception:
        pass

    # Fallback：LLM 失败时返回带警告的降级内容
    return {
        "hook_script": f"【{hook_type}】{topic[:40]}…（系统提示：脚本生成服务暂时不可用，以下为模板占位）",
        "full_script": f"（系统提示：脚本生成服务暂时不可用，未能为「{topic}」生成完整口播稿。请稍后重试或联系管理员。占位信息：时长约 {duration}s，平台 {platform}，方法论 {meth_id}）",
        "shot_list": [
            {"timestamp": "0-3s", "visual": "特写", "audio": "钩子", "text": topic[:20]},
            {"timestamp": f"3-{duration}s", "visual": "演示", "audio": "展开", "text": "主体内容（待生成）"},
        ],
        "bgm_suggestion": "（系统提示：BGM 推荐暂时不可用）",
        "caption_highlights": visual_elements or ["待生成"],
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

    available_methods = list_available_methodologies()
    if not available_methods:
        available_methods = ["aida_advanced"]

    # 尝试用 LLM 批量生成推荐理由和方法论匹配
    llm_topics = []
    try:
        client = get_client(skill_name="select_topic")
        if client and client.config.api_key:
            news_items = "\n".join(
                f"{idx + 1}. {it.get('title', '')} - {it.get('description', '')[:100]}"
                for idx, it in enumerate(nlist[:5])
            )
            hot_items = "\n".join(f"- {ht}" for ht in hot_topics[:3]) or "无"

            prompt = (
                f"你是一位资深内容策划师。请基于以下行业新闻和用户热点，"
                f"为{platform}平台的{account_stage}阶段账号生成选题推荐。\n\n"
                f"【行业新闻】\n{news_items}\n\n"
                f"【用户热点】\n{hot_items}\n\n"
                f"【可用方法论】{', '.join(available_methods)}\n\n"
                f"要求：\n"
                f"1. 为每条新闻和每个热点各生成一个选题推荐；\n"
                f"2. score 为 0.0-1.0 的相关性评分；\n"
                f"3. reason 必须具体、可操作（1-2句话），不要泛泛而谈；\n"
                f"4. methodology 必须从可用方法论中选择最匹配的一个；\n"
                f"5. 热点类选题优先匹配 trend_ride。\n\n"
                f"输出严格 JSON："
                f'{{"recommendations":[{{"topic":"标题","score":0.85,"reason":"具体理由","methodology":"方法论ID"}}]}}'
            )
            raw = await client.complete(
                prompt, response_format={"type": "json_object"}, temperature=0.7, max_tokens=2000
            )
            data = json.loads(raw)
            recs = data.get("recommendations") or []
            for r in recs:
                llm_topics.append({
                    "topic": r.get("topic", ""),
                    "score": float(r.get("score", 0.7)),
                    "reason": r.get("reason", ""),
                    "methodology": r.get("methodology", available_methods[0]),
                })
    except Exception:
        pass

    # 如果 LLM 成功返回且数量足够，直接使用
    if len(llm_topics) >= len(nlist[:5]) + len(hot_topics[:3]):
        topics = llm_topics
    else:
        # Fallback：按原有逻辑填充，但 reason 不再写死"占位"
        topics = llm_topics.copy()
        covered = {t["topic"] for t in topics}

        for i, item in enumerate(nlist[:5]):
            title = item.get("title", f"选题{i}")
            if title in covered:
                continue
            meth = available_methods[i % len(available_methods)]
            desc = item.get("description", "")[:60]
            reason = f"基于「{title}」行业动态，适合{account_stage}阶段账号借势传播"
            if desc:
                reason += f"：{desc}"
            topics.append({
                "topic": title,
                "score": round(0.85 - i * 0.05, 2),
                "reason": reason,
                "methodology": meth,
            })

        for ht in hot_topics[:3]:
            if ht in covered:
                continue
            meth = "trend_ride" if "trend_ride" in available_methods else available_methods[0]
            topics.append({
                "topic": ht,
                "score": 0.75,
                "reason": f"用户关注热点「{ht}」，建议快速跟进获取流量红利",
                "methodology": meth,
            })

    return {
        "recommended_topics": topics,
        "content_calendar": [{"day_offset": j, "topic": topics[j % len(topics)]["topic"]} for j in range(min(3, max(1, len(topics))))],
        "trend_analysis": news.get("trend_prediction", ""),
        "user_id": user_id,
        "platform": platform,
    }
