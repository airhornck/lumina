"""
用户运营官 Skill - MCP Server

提供评论回复、粉丝管理、私域运营等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

mcp = FastMCP("community_manager")


class CommentReplyInput(BaseModel):
    """评论回复输入"""
    comment_text: str
    commenter_info: Optional[Dict[str, Any]] = None
    content_context: Optional[str] = None
    tone: str = "friendly"  # friendly, professional, humorous
    user_id: str


class CommentReplyOutput(BaseModel):
    """评论回复输出"""
    reply_text: str
    reply_tone: str
    suggested_emoji: Optional[List[str]]
    follow_up_action: Optional[str]


class FanSegmentationInput(BaseModel):
    """粉丝分层输入"""
    fans_data: List[Dict[str, Any]]
    segmentation_criteria: Optional[List[str]] = None
    user_id: str


@mcp.tool()
async def generate_comment_reply(input: CommentReplyInput) -> CommentReplyOutput:
    """
    生成评论回复
    
    根据评论内容和语境生成合适的回复
    """
    comment = input.comment_text.lower()
    
    # 简单规则匹配
    if any(word in comment for word in ["谢谢", "感谢", "有用"]):
        reply = "能帮到你太开心啦！有问题随时问我～"
        emoji = ["😊", "💪"]
        follow_up = "建议关注该用户"
    elif any(word in comment for word in ["怎么", "如何", "怎样"]):
        reply = "很好的问题！我会专门出一期内容详细讲解，记得关注哦～"
        emoji = ["🤔", "✨"]
        follow_up = "记录问题，后续内容选题"
    elif any(word in comment for word in ["喜欢", "爱", "棒"]):
        reply = "谢谢支持！你的喜欢是我创作的动力❤️"
        emoji = ["❤️", "🙏"]
        follow_up = "转化为忠实粉丝"
    else:
        reply = "感谢评论！有什么想法欢迎继续交流～"
        emoji = ["👋"]
        follow_up = None
    
    return CommentReplyOutput(
        reply_text=reply,
        reply_tone=input.tone,
        suggested_emoji=emoji,
        follow_up_action=follow_up
    )


@mcp.tool()
async def segment_fans(input: FanSegmentationInput) -> Dict[str, Any]:
    """
    粉丝分层
    
    基于互动行为对粉丝进行分层管理
    """
    segments = {
        "super_fans": [],      # 超级粉丝：高频互动
        "active_fans": [],     # 活跃粉丝：定期互动
        "occasional_fans": [], # 偶尔互动
        "silent_followers": [], # 沉默关注
        "new_fans": []         # 新粉丝
    }
    
    for fan in input.fans_data:
        engagement_count = fan.get("engagement_count", 0)
        days_since_last = fan.get("days_since_last_interaction", 999)
        follow_days = fan.get("follow_days", 0)
        
        if engagement_count > 20 and days_since_last < 7:
            segments["super_fans"].append(fan)
        elif engagement_count > 5 and days_since_last < 30:
            segments["active_fans"].append(fan)
        elif engagement_count > 0:
            segments["occasional_fans"].append(fan)
        elif follow_days < 7:
            segments["new_fans"].append(fan)
        else:
            segments["silent_followers"].append(fan)
    
    return {
        "segments": {
            k: {
                "count": len(v),
                "fans": v[:5],  # 只返回前5个示例
                "strategy": get_segment_strategy(k)
            }
            for k, v in segments.items()
        },
        "recommendations": [
            f"超级粉丝专属福利：{len(segments['super_fans'])}人",
            f"需激活的沉默用户：{len(segments['silent_followers'])}人"
        ]
    }


def get_segment_strategy(segment: str) -> str:
    """获取分层运营策略"""
    strategies = {
        "super_fans": "专属福利、优先回复、线下活动邀请",
        "active_fans": "定期互动、内容共创邀请",
        "occasional_fans": "优质内容触达、激活活动",
        "silent_followers": "唤醒活动、重新定位",
        "new_fans": "欢迎互动、新手引导"
    }
    return strategies.get(segment, "常规维护")


@mcp.tool()
async def auto_reply_settings(
    trigger_keywords: List[str],
    reply_templates: Dict[str, str],
    user_id: str
) -> Dict[str, Any]:
    """
    配置自动回复规则
    """
    return {
        "rules_count": len(trigger_keywords),
        "active_rules": [
            {
                "keyword": kw,
                "template": reply_templates.get(kw, "感谢您的留言！"),
                "match_type": "contains",
                "cooldown_minutes": 30
            }
            for kw in trigger_keywords
        ],
        "best_practices": [
            "自动回复后24小时内人工跟进",
            "避免过于机械的回复模板",
            "定期检查自动回复效果"
        ]
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
