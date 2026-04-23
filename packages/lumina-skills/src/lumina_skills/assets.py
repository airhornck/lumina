from __future__ import annotations

import json
from typing import Any, Dict, List

from knowledge_base.methodology_registry import MethodologyRegistry

try:
    from llm_hub import get_client
except Exception:
    get_client = None  # type: ignore


async def retrieve_methodology(
    query: str,
    industry: str,
    goal: str = "awareness",
    user_id: str = "anonymous",
) -> Dict[str, Any]:
    reg = MethodologyRegistry()
    m = reg.find_best_match(query, industry=industry, goal=goal)
    if not m:
        return {
            "methodology_id": "",
            "name": "未找到方法论",
            "steps": [],
            "prompt_templates": {},
            "success_cases": [],
            "applicable_scenarios": [],
            "user_id": user_id,
        }
    return {
        "methodology_id": m.methodology_id,
        "name": m.name,
        "steps": m.steps,
        "prompt_templates": m.prompt_templates,
        "success_cases": m.case_studies,
        "applicable_scenarios": m.applicable_scenarios,
        "user_id": user_id,
    }


async def match_cases(
    content_type: str,
    industry: str,
    user_id: str,
    target_metrics: Dict[str, Any] | None = None,
    limit: int = 5,
) -> Dict[str, Any]:
    _ = target_metrics
    lim = max(1, min(10, limit))

    # 尝试用 LLM 生成相关案例
    llm_cases = None
    try:
        client = get_client(skill_name="match_cases")
        if client and client.config.api_key:
            metrics_hint = ""
            if target_metrics:
                metrics_hint = f"目标指标：{json.dumps(target_metrics, ensure_ascii=False)[:200]}"
            prompt = (
                f"你是一位营销案例研究专家。请基于行业和内容类型生成{lim}个相关的成功案例。\n\n"
                f"【行业】{industry}\n"
                f"【内容类型】{content_type}\n"
                f"{metrics_hint}\n\n"
                f"要求：\n"
                f"1. 每个案例要有具体的标题、核心成功因素（3-5条）；\n"
                f"2. 给出可复用的模式分析（pattern_analysis）；\n"
                f"3. 给出可操作的关键 takeaway（actionable_takeaways，2-3条）。\n\n"
                f"输出严格JSON："
                f'{{"cases":[{{"case_id":"","title":"","similarity_score":0.85,"key_success_factors":[]}}],'
                f'"pattern_analysis":"","actionable_takeaways":[]}}'
            )
            raw = await client.complete(
                prompt,
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=2000,
            )
            data = json.loads(raw)
            llm_cases = {
                "matched_cases": data.get("cases", []),
                "pattern_analysis": data.get("pattern_analysis", ""),
                "actionable_takeaways": data.get("actionable_takeaways", []),
            }
    except Exception:
        pass

    if llm_cases:
        return {
            **llm_cases,
            "user_id": user_id,
        }

    # Fallback：返回通用模板但明确标注
    cases = [
        {
            "case_id": f"demo_{i}",
            "title": f"{industry}/{content_type} 案例 {i}",
            "similarity_score": round(0.9 - i * 0.05, 2),
            "key_success_factors": ["强钩子", "清晰 CTA", "精准标签"],
        }
        for i in range(lim)
    ]
    return {
        "matched_cases": cases,
        "pattern_analysis": "系统提示：LLM案例匹配服务暂时不可用，返回通用模板案例。",
        "actionable_takeaways": ["对齐高相似案例的结构与节奏", "借鉴成功案例的钩子设计"],
        "user_id": user_id,
    }


async def qa_knowledge(
    question: str,
    knowledge_domain: str = "methodology",
    user_id: str = "anonymous",
) -> Dict[str, Any]:
    # 加载相关知识库作为上下文
    knowledge_context = ""
    try:
        reg = MethodologyRegistry()
        mids = reg.list_ids()
        if mids:
            knowledge_context = "\n".join(
                f"- {mid}: {reg.load(mid).name}"
                for mid in mids[:10]
            )
    except Exception:
        pass

    # 尝试用 LLM 回答问题
    llm_answer = None
    try:
        client = get_client(skill_name="qa_knowledge")
        if client and client.config.api_key:
            prompt = (
                f"你是一位营销方法论专家。请基于以下知识库回答用户问题。\n\n"
                f"【知识库】\n{knowledge_context or '暂无详细知识库'}\n\n"
                f"【用户问题】{question}\n"
                f"【知识领域】{knowledge_domain}\n\n"
                f"要求：\n"
                f"1. 回答要具体、专业，不要泛泛而谈；\n"
                f"2. 如果知识库不足以回答，基于你的专业知识补充；\n"
                f"3. 给出相关的方法论ID列表；\n"
                f"4. 给出置信度（0.0-1.0）。\n\n"
                f"输出严格JSON："
                f'{{"answer":"","sources":[],"confidence":0.75,"related_methodologies":[]}}'
            )
            raw = await client.complete(
                prompt,
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1500,
            )
            data = json.loads(raw)
            llm_answer = {
                "answer": data.get("answer", ""),
                "sources": data.get("sources", []),
                "confidence": float(data.get("confidence", 0.7)),
                "related_methodologies": data.get("related_methodologies", []),
            }
    except Exception:
        pass

    if llm_answer:
        return {
            **llm_answer,
            "user_id": user_id,
        }

    # Fallback
    return {
        "answer": f"系统提示：LLM知识问答服务暂时不可用。关于「{question[:80]}」的问题，建议参考 aida_advanced 等基础方法论。",
        "sources": [],
        "confidence": 0.35,
        "related_methodologies": ["aida_advanced"],
        "user_id": user_id,
    }
