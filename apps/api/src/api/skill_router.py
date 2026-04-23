"""
Skill API 路由

暴露所有 Agent Skills 的 HTTP 接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/skill", tags=["skill"])


class SkillExecuteRequest(BaseModel):
    skill_name: str
    method: str
    params: Dict[str, Any]
    user_id: str


@router.post("/execute")
async def execute_skill(request: SkillExecuteRequest):
    """
    执行 Skill 方法
    
    通过 SkillHubClient 调用对应的 Skill 工具
    """
    # Skill 路由映射（别名 -> TOOL_REGISTRY 中的工具名）
    skill_routes = {
        "content_strategist": "generate_script",
        "creative_studio": "generate_script",
        "data_analyst": "diagnose_account",
        "growth_hacker": "analyze_traffic",
        "community_manager": "generate_text",
        "compliance_officer": "detect_risk",
        "matrix_commander": "generate_variations",
        "bulk_creative": "generate_variations",
        "account_keeper": "diagnose_account",
        "traffic_broker": "analyze_traffic",
        "knowledge_miner": "qa_knowledge",
        "sop_evolver": "retrieve_methodology",
        "rpa_executor": "fetch_trending_topics",
    }
    
    # 优先用 method 作为工具名，fallback 到 skill_routes 映射
    tool_name = request.method or skill_routes.get(request.skill_name, request.skill_name)
    
    # 尝试通过 SkillHubClient 真实调用
    try:
        from skill_hub_client.client import SkillHubClient
        
        client = SkillHubClient()
        result = await client.call(tool_name, request.params)
        
        if result.get("ok"):
            return {
                "success": True,
                "skill": request.skill_name,
                "method": request.method,
                "result": result.get("result"),
            }
        
        # 非 unknown_skill 错误，返回具体错误信息
        error_msg = result.get("error", "")
        if "unknown_skill" not in error_msg:
            return {
                "success": False,
                "skill": request.skill_name,
                "method": request.method,
                "error": error_msg,
            }
    except Exception as e:
        pass
    
    # Fallback：返回模拟结果但明确标注
    return {
        "success": True,
        "skill": request.skill_name,
        "method": request.method,
        "result": {
            "message": f"Skill {request.skill_name}.{request.method} executed (系统提示：真实Skill调用暂时不可用，返回模拟结果)",
            "params_received": list(request.params.keys()),
            "tool_attempted": tool_name,
        }
    }


@router.get("/list")
async def list_skills():
    """
    列出所有可用 Skills
    """
    return {
        "single_account_agents": [
            {"id": "content_strategist", "name": "内容策略师"},
            {"id": "creative_studio", "name": "创意工厂"},
            {"id": "data_analyst", "name": "数据分析师"},
            {"id": "growth_hacker", "name": "投放优化师"},
            {"id": "community_manager", "name": "用户运营官"},
            {"id": "compliance_officer", "name": "合规审查员"},
        ],
        "matrix_agents": [
            {"id": "matrix_commander", "name": "矩阵指挥官"},
            {"id": "bulk_creative", "name": "批量创意工厂"},
            {"id": "account_keeper", "name": "账号维护工"},
            {"id": "traffic_broker", "name": "流量互导员"},
            {"id": "knowledge_miner", "name": "知识提取器"},
            {"id": "sop_evolver", "name": "SOP进化师"},
        ],
        "utility_agents": [
            {"id": "rpa_executor", "name": "RPA执行器"},
        ]
    }
