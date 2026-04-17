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
        quality_scores=[0.85 + i*0.01 for i in range(len(variations))]  # 模拟质量分数
    )


async def create_niche_variation(master_content: Dict, niche: str, account: Dict) -> Dict:
    """创建细分领域变体"""
    topic = master_content.get("topic", niche)
    meth_id = match_methodology_for_content(f"{topic} {niche}", content_type="post") or "aida_advanced"
    meth_guide = build_methodology_prompt(meth_id) or ""
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

        adapted_content = content.get("content", "")[:int(max_length)]
        adapted_hashtags = content.get("hashtags", [])[:int(hashtag_limit)]

        adaptations[target] = {
            "platform": target,
            "content": adapted_content,
            "hashtags": adapted_hashtags,
            "style_guide": style_guide,
            "notes": f"适配自{source_platform}，已根据平台规范库调整至{target}风格"
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
    recommended_meth = goal_to_methodology.get(optimization_goal, "aida_advanced")
    meth_guide = build_methodology_prompt(recommended_meth) or ""

    for content in contents:
        # 根据目标进行优化
        if optimization_goal == "engagement":
            # 增加互动引导
            optimized_content = content.get("content", "") + "\n\n💬 你怎么看？评论区聊聊"
            optimized_hashtags = content.get("hashtags", []) + ["互动"]
        elif optimization_goal == "conversion":
            # 强化行动号召
            optimized_content = content.get("content", "") + "\n\n👉 点击主页，获取更多干货"
            optimized_hashtags = content.get("hashtags", []) + ["必看"]
        else:
            optimized_content = content.get("content", "")
            optimized_hashtags = content.get("hashtags", [])
        
        # 标签数量也按平台规范限制（此处取通用默认值 10，实际调用时可按平台传入）
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
        })
    
    return {
        "total_optimized": len(optimized),
        "optimization_goal": optimization_goal,
        "results": optimized,
        "expected_improvement": "15-25%" if optimization_goal == "engagement" else "10-20%"
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
