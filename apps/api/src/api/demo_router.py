"""
Demo 工作台 REST 路由

提供定位矩阵和本周榜单两个接口，直接调用 llm_hub + fetch_trending_topics
不经过 orchestra 和独立 MCP Skill Server
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt_template(name: str) -> str:
    """加载 Prompt 模板文件"""
    path = _PROMPTS_DIR / f"{name}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    # 如果模板文件不存在，使用内置 fallback
    return ""


def _build_position_matrix_prompt(
    industry: str | None,
    stage: str | None,
    platform: str | None,
    goal: str | None,
    pain_point: str | None,
) -> str:
    profile_parts = []
    if industry:
        profile_parts.append(f"行业：{industry}")
    if stage:
        profile_parts.append(f"阶段：{stage}")
    if platform:
        profile_parts.append(f"平台：{platform}")
    if goal:
        profile_parts.append(f"目标：{goal}")
    if pain_point:
        profile_parts.append(f"痛点：{pain_point}")

    profile_str = "；".join(profile_parts) if profile_parts else "暂无具体画像信息"

    template = _load_prompt_template("position_matrix")
    if template:
        return template.format(profile=profile_str)

    # fallback
    return f"""你是 Lumina「内容定位矩阵」分析师。

基于以下用户画像，生成定位矩阵分析结果：
{profile_str}

要求：
- x 轴（0-100）：专业独特性 — 用户在其领域的专业差异化程度
- y 轴（0-100）：市场需求度 — 该领域内容的市场受众规模与需求强度
- feedback：用 1-2 句话给出定位现状的客观评价
- suggestion：用 1-2 句话给出下一步行动建议

必须严格按以下 JSON 格式输出，不要任何额外文字：
{{
  "x": <0-100的整数>,
  "y": <0-100的整数>,
  "feedback": "定位反馈文案...",
  "suggestion": "行动建议文案..."
}}
"""


def _build_weekly_rankings_prompt(
    real_topics: List[Dict[str, Any]],
    sort_by: str,
    limit: int,
    industry: str | None,
    stage: str | None,
    platform: str | None,
    goal: str | None,
    pain_point: str | None,
) -> str:
    profile_parts = []
    if industry:
        profile_parts.append(f"行业：{industry}")
    if stage:
        profile_parts.append(f"阶段：{stage}")
    if platform:
        profile_parts.append(f"平台：{platform}")
    if goal:
        profile_parts.append(f"目标：{goal}")
    if pain_point:
        profile_parts.append(f"痛点：{pain_point}")

    profile_str = "；".join(profile_parts) if profile_parts else "暂无具体画像信息"

    if real_topics:
        topics_str = "\n".join(
            [f"- [{t.get('source', '?')}] {t.get('title', '')}" for t in real_topics]
        )
    else:
        topics_str = "（暂无实时数据，请基于通用热门趋势生成）"

    template = _load_prompt_template("weekly_rankings")
    if template:
        return template.format(
            topics=topics_str,
            profile=profile_str,
            sort_by=sort_by,
            limit=limit,
        )

    # fallback
    return f"""你是 Lumina「本周内容选题榜单」分析师。

【真实热门话题】（来自平台实时抓取）
{topics_str}

【用户画像】
{profile_str}

要求：
- 结合真实热门话题和用户画像，推荐最有价值的 {limit} 个选题
- fit_score：该选题对用户的匹配程度（0-100）
- heat：该选题的市场热度（0-100），可参考真实话题排名
- delta：热度周环比变化（可虚构合理数值）
- risk_level：low / medium / high
- angles：3 个推荐切入角度
- title_templates：2 个推荐标题模板
- 按 {sort_by} 从高到低排序

必须严格按以下 JSON 格式输出，不要任何额外文字：
{{
  "list": [
    {{
      "id": "topic_001",
      "name": "选题名称",
      "source": "来源平台",
      "fit_score": 92,
      "heat": 95,
      "delta": 12,
      "risk_level": "low",
      "angles": ["切入角度1", "切入角度2", "切入角度3"],
      "title_templates": ["标题模板1", "标题模板2"],
      "warnings": []
    }}
  ],
  "total": {limit}
}}
"""


def _apply_sort_and_pagination(
    items: List[Dict[str, Any]],
    sort_by: str,
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    """服务端二次排序 + 分页切片"""
    if sort_by == "heat":
        items = sorted(items, key=lambda x: x.get("heat", 0), reverse=True)
    else:
        # 默认 fit_score
        items = sorted(items, key=lambda x: x.get("fit_score", 0), reverse=True)
    return items[offset : offset + limit]


@router.get("/position-matrix")
async def get_position_matrix(
    user_id: str | None = Query(None),
    profile_id: str | None = Query(None),
    industry: str | None = Query(None),
    stage: str | None = Query(None),
    platform: str | None = Query(None),
    goal: str | None = Query(None),
    pain_point: str | None = Query(None),
):
    """
    获取定位矩阵分析结果

    返回用户在「专业独特性 × 市场需求度」矩阵中的坐标与建议
    """
    try:
        from llm_hub import get_client

        client = get_client(skill_name="demo_matrix")
        if not client:
            logger.warning("No LLM client for skill_name=demo_matrix, trying default")
            client = get_client()

        if not client or not client.config.api_key:
            return {"code": 0, "message": "success", "data": None}

        prompt = _build_position_matrix_prompt(
            industry, stage, platform, goal, pain_point
        )
        response = await client.complete(
            prompt=prompt,
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=2048,
            _usage_meta={"user_id": user_id, "skill_name": "demo_matrix"} if user_id else None,
        )

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("LLM response is not valid JSON: %s", response[:200])
            return {"code": 0, "message": "success", "data": None}

        if not isinstance(data, dict) or "x" not in data or "y" not in data:
            return {"code": 0, "message": "success", "data": None}

        return {
            "code": 0,
            "message": "success",
            "data": {
                "x": data.get("x", 50),
                "y": data.get("y", 50),
                "feedback": data.get("feedback", ""),
                "suggestion": data.get("suggestion", ""),
            },
        }

    except Exception as e:
        logger.exception("position_matrix failed")
        return {"code": 0, "message": "success", "data": None}


@router.get("/weekly-rankings")
async def get_weekly_rankings(
    sort_by: str = Query("fit_score"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user_id: str | None = Query(None),
    profile_id: str | None = Query(None),
    industry: str | None = Query(None),
    stage: str | None = Query(None),
    platform: str | None = Query(None),
    goal: str | None = Query(None),
    pain_point: str | None = Query(None),
):
    """
    获取本周内容选题榜单

    采用「RPA 真实抓取 + LLM 增强」混合策略：
    1. 先通过 fetch_trending_topics 抓取各平台真实热门话题
    2. 再用 LLM 基于真实话题 + 用户画像生成结构化榜单
    3. 服务端对结果做二次排序与分页
    4. 若 RPA 失败，自动降级为纯 LLM 生成
    """
    real_topics: List[Dict[str, Any]] = []

    # Step 1: RPA 抓取各平台真实热门话题
    try:
        from lumina_skills.tool_skills import fetch_trending_topics

        for pf in ("douyin", "bilibili"):
            try:
                result = await fetch_trending_topics(pf, category="general", limit=10)
                if result and result.get("topics"):
                    for t in result["topics"][:5]:
                        real_topics.append(
                            {"source": pf, "title": t.get("title", "")}
                        )
            except Exception as e:
                logger.warning("fetch_trending_topics failed for %s: %s", pf, e)

        # 小红书需要 Cookie，单独处理
        try:
            result = await fetch_trending_topics(
                "xiaohongshu", category="general", limit=10
            )
            if result and result.get("topics"):
                for t in result["topics"][:5]:
                    real_topics.append(
                        {"source": "xiaohongshu", "title": t.get("title", "")}
                    )
        except Exception as e:
            logger.warning("fetch_trending_topics failed for xiaohongshu: %s", e)

    except Exception as e:
        logger.warning("RPA fetch module not available: %s", e)

    # Step 2: LLM 基于真实话题 + 用户画像生成结构化榜单
    try:
        from llm_hub import get_client

        client = get_client(skill_name="demo_rankings")
        if not client:
            logger.warning("No LLM client for skill_name=demo_rankings, trying default")
            client = get_client()

        if not client or not client.config.api_key:
            return {
                "code": 0,
                "message": "success",
                "data": {
                    "list": [],
                    "total": 0,
                    "data_source": "llm_only",
                },
            }

        # 请求更多数据以支持分页（让 LLM 生成 limit+offset 的总量）
        llm_limit = limit + offset
        prompt = _build_weekly_rankings_prompt(
            real_topics=real_topics,
            sort_by=sort_by,
            limit=llm_limit,
            industry=industry,
            stage=stage,
            platform=platform,
            goal=goal,
            pain_point=pain_point,
        )

        response = await client.complete(
            prompt=prompt,
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=4096,
            _usage_meta={"user_id": user_id, "skill_name": "demo_rankings"} if user_id else None,
        )

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("LLM response is not valid JSON: %s", response[:200])
            return {
                "code": 0,
                "message": "success",
                "data": {"list": [], "total": 0, "data_source": "llm_only"},
            }

        if not isinstance(data, dict) or "list" not in data:
            return {
                "code": 0,
                "message": "success",
                "data": {"list": [], "total": 0, "data_source": "llm_only"},
            }

        # Step 3: 服务端二次排序 + 分页
        all_items = data.get("list", [])
        sorted_items = _apply_sort_and_pagination(all_items, sort_by, limit, offset)

        data["list"] = sorted_items
        data["total"] = len(all_items)
        data["data_source"] = "rpa+llm" if real_topics else "llm_only"

        return {"code": 0, "message": "success", "data": data}

    except Exception as e:
        logger.exception("weekly_rankings failed")
        return {
            "code": 0,
            "message": "success",
            "data": {"list": [], "total": 0, "data_source": "llm_only"},
        }
