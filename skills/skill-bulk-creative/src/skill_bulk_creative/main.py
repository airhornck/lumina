"""
批量创意工厂 Skill - MCP Server

提供一稿多改、批量生成、平台适配等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import List, Dict, Any

try:
    from knowledge_base.platform_registry import PlatformRegistry
except ImportError:
    import sys
    from pathlib import Path
    _kb_path = Path(__file__).resolve().parents[3] / "packages" / "knowledge-base" / "src"
    if str(_kb_path) not in sys.path:
        sys.path.insert(0, str(_kb_path))
    from knowledge_base.platform_registry import PlatformRegistry

try:
    from lumina_skills.methodology_utils import build_methodology_prompt, match_methodology_for_content
except ImportError:
    import sys
    from pathlib import Path
    _lu_path = Path(__file__).resolve().parents[3] / "packages" / "lumina-skills" / "src"
    if str(_lu_path) not in sys.path:
        sys.path.insert(0, str(_lu_path))
    from lumina_skills.methodology_utils import build_methodology_prompt, match_methodology_for_content

try:
    from llm_hub import get_client
except ImportError:
    import sys
    from pathlib import Path
    _llm_path = Path(__file__).resolve().parents[3] / "packages" / "llm-hub" / "src"
    if str(_llm_path) not in sys.path:
        sys.path.insert(0, str(_llm_path))
    from llm_hub import get_client

mcp = FastMCP("bulk_creative")


def _get_spec_value(spec: Any, key_path: List[str], default: Any = None) -> Any:
    """从 PlatformSpec.content_formats 中查找第一个匹配 key_path 的值"""
    formats = getattr(spec, "content_formats", {}) or {}
    for fmt_cfg in formats.values():
        if not isinstance(fmt_cfg, dict) or fmt_cfg.get("note"):
            continue
        val = fmt_cfg
        for k in key_path:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                val = None
                break
        if val is not None:
            return val
    return default


async def _llm_rewrite_content(
    master_content: Dict[str, Any],
    instruction: str,
    platform: str = "xiaohongshu",
    extra_context: str = "",
) -> Dict[str, Any] | None:
    """调用 LLM 改写内容，返回改写后的结构化数据。"""
    try:
        client = get_client(skill_name="bulk_creative")
        if client and client.config.api_key:
            prompt = (
                f"你是一位社交媒体内容专家。请根据以下指令改写内容。\n\n"
                f"【改写指令】\n{instruction}\n\n"
                f"【原始内容】\n"
                f"标题：{master_content.get('title', '')}\n"
                f"正文：{master_content.get('content', '')[:800]}\n"
                f"标签：{', '.join(master_content.get('hashtags', [])[:10])}\n\n"
                f"【目标平台】{platform}\n"
                f"{extra_context}\n\n"
                f"要求：\n"
                f"1. 保持原始内容的核心信息不变；\n"
                f"2. 标题吸引人且符合平台调性；\n"
                f"3. 正文口语化、有节奏感；\n"
                f"4. 标签精准且热门（3-8个）；\n"
                f"5. angle 用一句话概括本次改写角度；\n"
                f"6. 输出严格 JSON："
                f'{{"title":"","content":"","hashtags":[],"angle":"","quality_score":0.0-1.0}}'
            )
            raw = await client.complete(
                prompt,
                response_format={"type": "json_object"},
                temperature=0.75,
                max_tokens=2000,
            )
            data = json.loads(raw)
            return {
                "title": data.get("title", master_content.get("title", "")),
                "content": data.get("content", master_content.get("content", "")),
                "hashtags": data.get("hashtags") or master_content.get("hashtags", []),
                "angle": data.get("angle", ""),
                "quality_score": float(data.get("quality_score", 0.8)),
            }
    except Exception:
        pass
    return None


class BulkVariationInput(BaseModel):
    """批量变体输入"""
    master_content: Dict[str, Any]
    target_accounts: List[Dict[str, Any]]  # 各账号的定位信息
    variation_strategy: str = "auto"  # auto, niche, scenario, local
    user_id: str


class BulkVariationOutput(BaseModel):
    """批量变体输出"""
    variations: List[Dict[str, Any]]
    generation_summary: Dict[str, Any]
    quality_scores: List[float]


@mcp.tool()
async def generate_variations(input: BulkVariationInput) -> BulkVariationOutput:
    """
    基于主内容生成多账号变体
    
    一稿多改，生成适合不同账号定位的内容版本
    """
    variations = []
    
    for account in input.target_accounts:
        account_type = account.get("type", "general")
        niche = account.get("niche", "")
        
        if account_type == "细分领域":
            variation = await create_niche_variation(
                input.master_content, 
                niche,
                account
            )
        elif account_type == "场景化":
            variation = await create_scenario_variation(
                input.master_content,
                account.get("scene", "日常"),
                account
            )
        elif account_type == "地域化":
            variation = await create_local_variation(
                input.master_content,
                account.get("city", ""),
                account
            )
        else:
            variation = await create_general_variation(
                input.master_content,
                account
            )
        
        variations.append(variation)
    
    return BulkVariationOutput(
        variations=variations,
        generation_summary={
            "total_generated": len(variations),
            "by_type": {
                "niche": len([v for v in variations if v.get("type") == "细分领域"]),
                "scenario": len([v for v in variations if v.get("type") == "场景化"]),
                "local": len([v for v in variations if v.get("type") == "地域化"]),
            },
            "avg_content_length": sum(len(v.get("content", "")) for v in variations) / max(len(variations), 1)
        },
        quality_scores=[v.get("quality_score", 0.75) for v in variations]  # 优先使用 LLM 返回的质量分
    )


async def create_niche_variation(master_content: Dict, niche: str, account: Dict) -> Dict:
    """创建细分领域变体"""
    topic = master_content.get("topic", niche)
    meth_id = match_methodology_for_content(f"{topic} {niche}", content_type="post") or "aida_advanced"
    meth_guide = build_methodology_prompt(meth_id) or ""
    platform = account.get("platform", "xiaohongshu")

    llm_result = await _llm_rewrite_content(
        master_content,
        instruction=f"改写为【{niche}】细分领域的专属版本，融入该行业的专业术语、痛点和受众语言",
        platform=platform,
        extra_context=f"账号类型：细分领域，领域标签：{niche}",
    )
    if llm_result:
        return {
            "account_id": account.get("id"),
            "type": "细分领域",
            **llm_result,
            "best_time": "20:00",
            "recommended_methodology": meth_id,
            "methodology_guide": meth_guide,
        }

    # Fallback
    return {
        "account_id": account.get("id"),
        "type": "细分领域",
        "title": f"【{niche}专属】{master_content.get('title', '')}",
        "content": f"专注{niche}领域解读：\n{master_content.get('content', '')[:100]}...",
        "angle": f"{niche}垂直切入",
        "hashtags": [niche, "细分领域", "干货"] + master_content.get("hashtags", [])[:3],
        "best_time": "20:00",
        "recommended_methodology": meth_id,
        "methodology_guide": meth_guide,
    }


async def create_scenario_variation(master_content: Dict, scene: str, account: Dict) -> Dict:
    """创建场景化变体"""
    topic = master_content.get("topic", scene)
    meth_id = match_methodology_for_content(f"{topic} {scene}场景", content_type="post") or "story_arc"
    meth_guide = build_methodology_prompt(meth_id) or ""
    platform = account.get("platform", "xiaohongshu")

    llm_result = await _llm_rewrite_content(
        master_content,
        instruction=f"改写为【{scene}场景】的实用版本，从具体使用场景切入，增加代入感",
        platform=platform,
        extra_context=f"账号类型：场景化，场景标签：{scene}",
    )
    if llm_result:
        return {
            "account_id": account.get("id"),
            "type": "场景化",
            **llm_result,
            "best_time": "12:00",
            "recommended_methodology": meth_id,
            "methodology_guide": meth_guide,
        }

    return {
        "account_id": account.get("id"),
        "type": "场景化",
        "title": f"【{scene}场景】{master_content.get('title', '')}",
        "content": f"当你在{scene}时，可能会遇到...\n{master_content.get('content', '')[:100]}...",
        "angle": f"{scene}场景应用",
        "hashtags": [scene, "场景化", "实用"] + master_content.get("hashtags", [])[:3],
        "best_time": "12:00",
        "recommended_methodology": meth_id,
        "methodology_guide": meth_guide,
    }


async def create_local_variation(master_content: Dict, city: str, account: Dict) -> Dict:
    """创建地域化变体"""
    topic = master_content.get("topic", city)
    meth_id = match_methodology_for_content(f"{topic} {city}本地", content_type="post") or "trend_ride"
    meth_guide = build_methodology_prompt(meth_id) or ""
    platform = account.get("platform", "xiaohongshu")

    llm_result = await _llm_rewrite_content(
        master_content,
        instruction=f"改写为【{city}】本地特色版本，融入地域文化、方言元素和本地受众的共鸣点",
        platform=platform,
        extra_context=f"账号类型：地域化，城市标签：{city}",
    )
    if llm_result:
        return {
            "account_id": account.get("id"),
            "type": "地域化",
            **llm_result,
            "best_time": "18:00",
            "recommended_methodology": meth_id,
            "methodology_guide": meth_guide,
        }

    return {
        "account_id": account.get("id"),
        "type": "地域化",
        "title": f"【{city}专享】{master_content.get('title', '')}",
        "content": f"{city}的朋友们注意了！\n{master_content.get('content', '')[:100]}...",
        "angle": f"{city}本地特色",
        "hashtags": [city, "本地生活", city+"攻略"] + master_content.get("hashtags", [])[:3],
        "best_time": "18:00",
        "recommended_methodology": meth_id,
        "methodology_guide": meth_guide,
    }


async def create_general_variation(master_content: Dict, account: Dict) -> Dict:
    """创建通用变体"""
    topic = master_content.get("topic", "")
    meth_id = match_methodology_for_content(topic, content_type="post") or "aida_advanced"
    meth_guide = build_methodology_prompt(meth_id) or ""
    platform = account.get("platform", "xiaohongshu")

    llm_result = await _llm_rewrite_content(
        master_content,
        instruction="优化为通用受众版本，语言通俗易懂，适合大众传播",
        platform=platform,
        extra_context="账号类型：通用受众",
    )
    if llm_result:
        return {
            "account_id": account.get("id"),
            "type": "通用",
            **llm_result,
            "best_time": "19:00",
            "recommended_methodology": meth_id,
            "methodology_guide": meth_guide,
        }

    return {
        "account_id": account.get("id"),
        "type": "通用",
        "title": master_content.get("title", ""),
        "content": master_content.get("content", ""),
        "angle": "通用版本",
        "hashtags": master_content.get("hashtags", []),
        "best_time": "19:00",
        "recommended_methodology": meth_id,
        "methodology_guide": meth_guide,
    }


@mcp.tool()
async def adapt_platform(
    content: Dict[str, Any],
    source_platform: str,
    target_platforms: List[str],
    user_id: str
) -> Dict[str, Any]:
    """
    跨平台内容适配
    
    将内容从源平台格式转换为目标平台格式
    """
    adaptations = {}

    for target in target_platforms:
        # 从平台规范库读取动态规范
        try:
            spec = PlatformRegistry().load(target)
            dna_lines = [f"{item.get('element', '')}: {item.get('value', '')}" for item in spec.content_dna]
            audit_lines = [
                f"{rule.get('category', '')}类禁用词: {', '.join(rule.get('forbidden_terms', []))}"
                for rule in spec.audit_rules
            ]
            style_guide_parts = dna_lines + audit_lines
            style_guide = "；".join(style_guide_parts) if style_guide_parts else "通用风格"

            # 从 content_formats 读取长度/标签限制
            max_length = _get_spec_value(spec, ["content", "max_chars"]) or _get_spec_value(spec, ["content_all", "max_chars"], 1000)
            hashtag_limit = _get_spec_value(spec, ["tags", "max_count"], 10)
        except Exception:
            style_guide = "通用风格"
            max_length = 1000
            hashtag_limit = 10

        # 尝试用 LLM 做跨平台风格改写
        llm_adapted = None
        try:
            client = get_client(skill_name="bulk_creative")
            if client and client.config.api_key:
                prompt = (
                    f"你是一位跨平台内容适配专家。请将以下内容从{source_platform}适配到{target}。\n\n"
                    f"【原始内容】\n"
                    f"正文：{content.get('content', '')[:800]}\n"
                    f"标签：{', '.join(content.get('hashtags', [])[:10])}\n\n"
                    f"【{target}平台规范】\n"
                    f"风格指南：{style_guide}\n"
                    f"正文长度限制：{max_length}字\n"
                    f"标签数量限制：{hashtag_limit}个\n\n"
                    f"要求：\n"
                    f"1. 严格按照目标平台的语言风格和用户习惯改写，不要简单截断；\n"
                    f"2. 正文长度不超过{max_length}字；\n"
                    f"3. 标签数量不超过{hashtag_limit}个，且符合目标平台热门标签习惯；\n"
                    f"4. 保持原始内容的核心信息不变。\n\n"
                    f"输出严格JSON：{{\"content\":\"\",\"hashtags\":[]}}"
                )
                raw = await client.complete(
                    prompt,
                    response_format={"type": "json_object"},
                    temperature=0.7,
                    max_tokens=2000,
                )
                data = json.loads(raw)
                llm_adapted = {
                    "content": data.get("content", "")[:int(max_length)],
                    "hashtags": (data.get("hashtags") or [])[:int(hashtag_limit)],
                }
        except Exception:
            pass

        if llm_adapted:
            adaptations[target] = {
                "platform": target,
                "content": llm_adapted["content"],
                "hashtags": llm_adapted["hashtags"],
                "style_guide": style_guide,
                "notes": f"由LLM智能适配自{source_platform}至{target}",
            }
        else:
            # Fallback：仅做长度截断
            adapted_content = content.get("content", "")[:int(max_length)]
            adapted_hashtags = content.get("hashtags", [])[:int(hashtag_limit)]
            adaptations[target] = {
                "platform": target,
                "content": adapted_content,
                "hashtags": adapted_hashtags,
                "style_guide": style_guide,
                "notes": f"适配自{source_platform}至{target}（系统提示：LLM适配暂时不可用，仅做长度截断）",
            }
    
    return {
        "original_platform": source_platform,
        "adaptations": adaptations,
        "automation_possible": True
    }


@mcp.tool()
async def batch_optimize(
    contents: List[Dict[str, Any]],
    optimization_goal: str,  # engagement, conversion, reach
    user_id: str
) -> Dict[str, Any]:
    """
    批量优化内容
    
    基于优化目标批量改进内容
    """
    optimized = []
    
    # 根据优化目标匹配推荐的方法论
    goal_to_methodology = {
        "engagement": "aida_advanced",
        "conversion": "hook_story_offer",
        "reach": "trend_ride",
    }
    goal_desc = {
        "engagement": "提升互动率，增加互动引导、提问、悬念",
        "conversion": "提升转化率，强化行动号召、稀缺感、社会认同",
        "reach": "提升曝光量，优化关键词、增加热点关联",
    }
    recommended_meth = goal_to_methodology.get(optimization_goal, "aida_advanced")
    meth_guide = build_methodology_prompt(recommended_meth) or ""

    for content in contents:
        # 尝试用 LLM 智能优化
        llm_optimized = None
        try:
            client = get_client(skill_name="bulk_creative")
            if client and client.config.api_key:
                prompt = (
                    f"你是一位内容优化专家。请基于以下优化目标改写内容。\n\n"
                    f"【原始内容】\n"
                    f"正文：{content.get('content', '')[:800]}\n"
                    f"标签：{', '.join(content.get('hashtags', [])[:10])}\n\n"
                    f"【优化目标】{optimization_goal} - {goal_desc.get(optimization_goal, '全面优化')}\n"
                    f"【方法论指引】{meth_guide}\n\n"
                    f"要求：\n"
                    f"1. 根据优化目标有针对性地调整内容，不要简单追加固定句子；\n"
                    f"2. 优化后的内容要自然融入原文，不要生硬拼接；\n"
                    f"3. 标签也要相应优化（3-8个）；\n"
                    f"4. 给出一个质量分数（0.0-1.0）。\n\n"
                    f"输出严格JSON："
                    f'{{"optimized_content":"","optimized_hashtags":[],"quality_score":0.0-1.0}}'
                )
                raw = await client.complete(
                    prompt,
                    response_format={"type": "json_object"},
                    temperature=0.75,
                    max_tokens=2000,
                )
                data = json.loads(raw)
                llm_optimized = {
                    "optimized_content": data.get("optimized_content", content.get("content", "")),
                    "optimized_hashtags": data.get("optimized_hashtags") or content.get("hashtags", []),
                    "quality_score": float(data.get("quality_score", 0.8)),
                }
        except Exception:
            pass

        if llm_optimized:
            optimized.append({
                "original_id": content.get("id"),
                **llm_optimized,
                "optimization_applied": optimization_goal,
                "recommended_methodology": recommended_meth,
                "methodology_guide": meth_guide,
            })
            continue

        # Fallback：简单追加固定模板
        if optimization_goal == "engagement":
            optimized_content = content.get("content", "") + "\n\n💬 你怎么看？评论区聊聊"
            optimized_hashtags = content.get("hashtags", []) + ["互动"]
        elif optimization_goal == "conversion":
            optimized_content = content.get("content", "") + "\n\n👉 点击主页，获取更多干货"
            optimized_hashtags = content.get("hashtags", []) + ["必看"]
        else:
            optimized_content = content.get("content", "")
            optimized_hashtags = content.get("hashtags", [])
        
        try:
            spec = PlatformRegistry().load(content.get("platform", "xiaohongshu"))
            tag_limit = int(_get_spec_value(spec, ["tags", "max_count"], 10))
        except Exception:
            tag_limit = 10

        optimized.append({
            "original_id": content.get("id"),
            "optimized_content": optimized_content,
            "optimized_hashtags": optimized_hashtags[:tag_limit],
            "optimization_applied": optimization_goal,
            "recommended_methodology": recommended_meth,
            "methodology_guide": meth_guide,
            "quality_score": 0.65,
        })
    
    # 收集 LLM 返回的质量分数，fallback 项使用默认值
    quality_scores = [o.get("quality_score", 0.75) for o in optimized]

    return {
        "total_optimized": len(optimized),
        "optimization_goal": optimization_goal,
        "results": optimized,
        "quality_scores": quality_scores,
        "expected_improvement": "15-25%" if optimization_goal == "engagement" else "10-20%"
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
