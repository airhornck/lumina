"""
SOP进化师 Skill - MCP Server

提供运营流程优化、策略迭代、知识沉淀等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

mcp = FastMCP("sop_evolver")


class SOPEvaluationInput(BaseModel):
    """SOP评估输入"""
    sop_id: str
    execution_history: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]
    user_id: str


class SOPEvaluationOutput(BaseModel):
    """SOP评估输出"""
    sop_id: str
    effectiveness_score: float
    bottlenecks: List[Dict[str, Any]]
    improvement_opportunities: List[str]
    updated_sop: Optional[Dict[str, Any]]


@mcp.tool()
async def evaluate_sop(input: SOPEvaluationInput) -> SOPEvaluationOutput:
    """
    评估 SOP 效果
    
    基于执行历史和效果数据评估 SOP 有效性
    """
    history = input.execution_history
    
    # 计算成功率
    total = len(history)
    success = sum(1 for h in history if h.get("success", False))
    success_rate = success / total if total > 0 else 0
    
    # 识别瓶颈
    bottlenecks = []
    avg_times = {}
    
    for step in ["准备", "执行", "检查", "优化"]:
        times = [h.get("step_times", {}).get(step, 0) for h in history]
        avg_time = sum(times) / len(times) if times else 0
        avg_times[step] = avg_time
        
        if avg_time > 60:  # 超过60秒视为瓶颈
            bottlenecks.append({
                "step": step,
                "avg_time": avg_time,
                "severity": "high" if avg_time > 120 else "medium"
            })
    
    # 效果评分
    effectiveness = min(100, success_rate * 80 + (1 - len(bottlenecks) * 0.1) * 20)
    
    return SOPEvaluationOutput(
        sop_id=input.sop_id,
        effectiveness_score=round(effectiveness, 1),
        bottlenecks=bottlenecks,
        improvement_opportunities=[
            f"优化'{b['step']}'步骤，当前耗时{b['avg_time']:.1f}秒"
            for b in bottlenecks
        ] if bottlenecks else ["当前SOP运行良好，可保持"],
        updated_sop=None  # 需要时才生成更新版本
    )


@mcp.tool()
async def evolve_strategy(
    current_strategy: Dict[str, Any],
    performance_data: Dict[str, Any],
    user_id: str,
    market_changes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    进化策略
    
    基于数据反馈迭代优化策略
    """
    # 分析当前策略效果
    current_roi = performance_data.get("roi", 0)
    
    # 生成改进建议
    improvements = []
    
    if current_roi < 2.0:
        improvements.append({
            "area": "成本优化",
            "action": "降低低效渠道投入",
            "expected_impact": "ROI +0.5"
        })
    
    if performance_data.get("engagement_rate", 0) < 0.05:
        improvements.append({
            "area": "内容优化",
            "action": "优化内容开头和互动引导",
            "expected_impact": "互动率 +2%"
        })
    
    # 生成新版本策略
    evolved_strategy = {
        "version": current_strategy.get("version", 1) + 1,
        "based_on": current_strategy.get("strategy_id"),
        "changes": improvements,
        "key_adjustments": [
            "增加视频内容比例至60%",
            "调整发布时间至晚8点",
            "优化目标受众定向"
        ],
        "expected_outcome": {
            "roi_improvement": "+20-30%",
            "engagement_lift": "+15-25%",
            "confidence": 0.75
        }
    }
    
    return {
        "evolution_summary": {
            "from_version": current_strategy.get("version", 1),
            "to_version": evolved_strategy["version"],
            "changes_count": len(improvements)
        },
        "evolved_strategy": evolved_strategy,
        "implementation_plan": {
            "phases": [
                {"phase": 1, "duration": "1周", "action": "小范围测试新策略"},
                {"phase": 2, "duration": "2周", "action": "分析测试结果"},
                {"phase": 3, "duration": "持续", "action": "全面 rollout"}
            ],
            "rollback_criteria": "ROI下降超过10%"
        }
    }


@mcp.tool()
async def generate_sop(
    task_description: str,
    best_practices: List[str],
    user_id: str
) -> Dict[str, Any]:
    """
    生成 SOP
    
    基于最佳实践生成标准操作流程
    """
    return {
        "sop_id": f"sop_{int(datetime.now().timestamp())}",
        "name": task_description,
        "version": 1,
        "created_at": datetime.now().isoformat(),
        "steps": [
            {
                "order": 1,
                "name": "准备",
                "description": "收集必要素材和信息",
                "checklist": ["确认主题", "准备素材", "检查工具"],
                "estimated_time": "5分钟"
            },
            {
                "order": 2,
                "name": "执行",
                "description": "按照标准流程执行",
                "checklist": ["遵循模板", "注意细节", "记录数据"],
                "estimated_time": "20分钟"
            },
            {
                "order": 3,
                "name": "检查",
                "description": "检查输出质量",
                "checklist": ["核对标准", "检查错误", "确认完整"],
                "estimated_time": "5分钟"
            },
            {
                "order": 4,
                "name": "优化",
                "description": "记录反馈并优化",
                "checklist": ["记录问题", "总结经验", "更新模板"],
                "estimated_time": "5分钟"
            }
        ],
        "best_practices_applied": best_practices,
        "quality_criteria": [
            "符合品牌调性",
            "无错别字",
            "信息准确",
            "格式规范"
        ]
    }


@mcp.tool()
async def knowledge_retrieval(
    query: str,
    knowledge_type: str,  # sop, case, template, best_practice
    user_id: str
) -> Dict[str, Any]:
    """
    知识检索
    
    从知识库中检索相关内容
    """
    # 模拟检索结果
    mock_results = {
        "sop": [
            {"title": "内容创作SOP", "relevance": 0.95, "id": "sop_001"},
            {"title": "账号诊断SOP", "relevance": 0.82, "id": "sop_002"}
        ],
        "case": [
            {"title": "爆款案例分析", "relevance": 0.88, "id": "case_001"},
            {"title": "矩阵运营案例", "relevance": 0.75, "id": "case_002"}
        ],
        "template": [
            {"title": "标题模板库", "relevance": 0.90, "id": "tmpl_001"},
            {"title": "脚本模板", "relevance": 0.85, "id": "tmpl_002"}
        ]
    }
    
    return {
        "query": query,
        "type": knowledge_type,
        "results": mock_results.get(knowledge_type, []),
        "recommended_actions": [
            "查看最相关的SOP文档",
            "参考相似案例",
            "应用推荐模板"
        ]
    }


@mcp.tool()
async def update_knowledge_base(
    new_content: Dict[str, Any],
    content_type: str,
    source: str,
    user_id: str
) -> Dict[str, Any]:
    """
    更新知识库
    
    将新经验沉淀到知识库
    """
    return {
        "content_id": f"kb_{int(datetime.now().timestamp())}",
        "type": content_type,
        "source": source,
        "status": "added",
        "indexed": True,
        "available_for": ["检索", "推荐", "SOP生成"],
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
