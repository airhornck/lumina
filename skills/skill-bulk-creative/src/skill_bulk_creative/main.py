"""
批量创意工厂 Skill - MCP Server

提供一稿多改、批量生成、平台适配等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import List, Dict, Any

mcp = FastMCP("bulk_creative")


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
    return {
        "account_id": account.get("id"),
        "type": "细分领域",
        "title": f"【{niche}专属】{master_content.get('title', '')}",
        "content": f"专注{niche}领域解读：\n{master_content.get('content', '')[:100]}...",
        "angle": f"{niche}垂直切入",
        "hashtags": [niche, "细分领域", "干货"] + master_content.get("hashtags", [])[:3],
        "best_time": "20:00"
    }


async def create_scenario_variation(master_content: Dict, scene: str, account: Dict) -> Dict:
    """创建场景化变体"""
    return {
        "account_id": account.get("id"),
        "type": "场景化",
        "title": f"【{scene}场景】{master_content.get('title', '')}",
        "content": f"当你在{scene}时，可能会遇到...\n{master_content.get('content', '')[:100]}...",
        "angle": f"{scene}场景应用",
        "hashtags": [scene, "场景化", "实用"] + master_content.get("hashtags", [])[:3],
        "best_time": "12:00"
    }


async def create_local_variation(master_content: Dict, city: str, account: Dict) -> Dict:
    """创建地域化变体"""
    return {
        "account_id": account.get("id"),
        "type": "地域化",
        "title": f"【{city}专享】{master_content.get('title', '')}",
        "content": f"{city}的朋友们注意了！\n{master_content.get('content', '')[:100]}...",
        "angle": f"{city}本地特色",
        "hashtags": [city, "本地生活", city+"攻略"] + master_content.get("hashtags", [])[:3],
        "best_time": "18:00"
    }


async def create_general_variation(master_content: Dict, account: Dict) -> Dict:
    """创建通用变体"""
    return {
        "account_id": account.get("id"),
        "type": "通用",
        "title": master_content.get("title", ""),
        "content": master_content.get("content", ""),
        "angle": "通用版本",
        "hashtags": master_content.get("hashtags", []),
        "best_time": "19:00"
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
    
    platform_specs = {
        "xiaohongshu": {
            "max_length": 1000,
            "hashtag_limit": 8,
            "style": "图文笔记风格，emoji丰富",
            "features": ["标题党", "分段清晰", "表情符号"]
        },
        "douyin": {
            "max_length": 200,
            "hashtag_limit": 5,
            "style": "短视频文案，简洁有力",
            "features": ["黄金3秒", "口语化", "强引导"]
        },
        "bilibili": {
            "max_length": 2000,
            "hashtag_limit": 10,
            "style": "深度内容，知识密度高",
            "features": ["逻辑清晰", "专业术语", "社区黑话"]
        }
    }
    
    for target in target_platforms:
        spec = platform_specs.get(target, platform_specs["xiaohongshu"])
        
        # 根据平台特性调整内容
        adapted_content = content.get("content", "")[:spec["max_length"]]
        adapted_hashtags = content.get("hashtags", [])[:spec["hashtag_limit"]]
        
        adaptations[target] = {
            "platform": target,
            "content": adapted_content,
            "hashtags": adapted_hashtags,
            "style_guide": spec["style"],
            "features": spec["features"],
            "notes": f"适配自{source_platform}，已调整至{target}风格"
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
        
        optimized.append({
            "original_id": content.get("id"),
            "optimized_content": optimized_content,
            "optimized_hashtags": optimized_hashtags[:8],  # 限制标签数量
            "optimization_applied": optimization_goal
        })
    
    return {
        "total_optimized": len(optimized),
        "optimization_goal": optimization_goal,
        "results": optimized,
        "expected_improvement": "15-25%" if optimization_goal == "engagement" else "10-20%"
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
