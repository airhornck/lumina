from __future__ import annotations

from typing import Any, Dict, List

from knowledge_base.methodology_registry import MethodologyRegistry


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
    cases = [
        {
            "case_id": f"demo_{i}",
            "title": f"{industry}/{content_type} 案例 {i}",
            "similarity_score": 0.9 - i * 0.05,
            "key_success_factors": ["强钩子", "清晰 CTA"],
        }
        for i in range(lim)
    ]
    return {
        "matched_cases": cases,
        "pattern_analysis": "向量库未接，返回占位案例。",
        "actionable_takeaways": ["对齐高相似案例的结构与节奏"],
        "user_id": user_id,
    }


async def qa_knowledge(
    question: str,
    knowledge_domain: str = "methodology",
    user_id: str = "anonymous",
) -> Dict[str, Any]:
    _ = knowledge_domain
    return {
        "answer": f"（占位 RAG）关于「{question[:80]}」：请接入向量库后返回答案。",
        "sources": [],
        "confidence": 0.35,
        "related_methodologies": ["aida_advanced"],
        "user_id": user_id,
    }
