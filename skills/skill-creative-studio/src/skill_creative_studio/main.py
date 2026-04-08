"""
创意工厂 Skill - MCP Server

提供文案生成、脚本创作、标题优化等创意能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

mcp = FastMCP("creative_studio")


class TextGenerationInput(BaseModel):
    """文案生成输入"""
    topic: str
    platform: str  # xiaohongshu, douyin, bilibili
    content_type: str  # post, title, copy, caption
    tone: str = "professional"  # professional, casual, humorous, emotional
    keywords: Optional[List[str]] = None
    user_id: str


class TextGenerationOutput(BaseModel):
    """文案生成输出"""
    title: str
    content: str
    hashtags: List[str]
    cover_copy: str  # 封面文案
    call_to_action: str


class ScriptGenerationInput(BaseModel):
    """脚本生成输入"""
    topic: str
    platform: str
    duration: int  # 秒
    hook_type: str = "curiosity"  # curiosity, pain_point, benefit, story
    target_audience: Optional[str] = None
    user_id: str


class ScriptGenerationOutput(BaseModel):
    """脚本生成输出"""
    title: str
    hook: str  # 黄金3秒钩子
    script_segments: List[Dict[str, Any]]  # 分段脚本
    visual_notes: List[str]  # 画面提示
    bgm_suggestion: str
    total_duration: int


@mcp.tool()
async def generate_text(input: TextGenerationInput) -> TextGenerationOutput:
    """
    生成营销文案
    
    根据主题、平台和调性生成适合的文案内容
    """
    # 获取 LLM 客户端（优先使用 Claude 创意模型）
    try:
        from llm_hub import get_client
        llm = get_client(skill_name="creative_studio")
    except ImportError:
        llm = None
    
    # 平台特定模板
    platform_templates = {
        "xiaohongshu": {
            "structure": "痛点引入 + 解决方案 + 使用体验 + 购买建议",
            "emoji_usage": "适量",
            "length": "300-800字"
        },
        "douyin": {
            "structure": "黄金3秒 + 信息密度 + 引导互动",
            "emoji_usage": "大量",
            "length": "50-200字"
        },
        "bilibili": {
            "structure": "知识密度 + 逻辑清晰 + 社区黑话",
            "emoji_usage": "少量",
            "length": "500-1500字"
        }
    }
    
    template = platform_templates.get(input.platform, platform_templates["xiaohongshu"])
    
    prompt = f"""
    作为资深文案创作者，请为{input.platform}平台创作一篇{input.content_type}：
    
    主题：{input.topic}
    调性：{input.tone}
    关键词：{input.keywords or []}
    
    平台特点：
    - 结构：{template['structure']}
    - Emoji使用：{template['emoji_usage']}
    - 长度：{template['length']}
    
    请生成：
    1. 吸睛标题（使用数字、悬念或利益点）
    2. 正文内容
    3. 相关标签（5-8个）
    4. 封面文案（15字以内）
    5. 引导行动的结尾
    
    以 JSON 格式输出。
    """
    
    if llm:
        try:
            response = await llm.complete(prompt, temperature=0.8)
            import json
            data = json.loads(response)
            
            return TextGenerationOutput(
                title=data.get("title", ""),
                content=data.get("content", ""),
                hashtags=data.get("hashtags", []),
                cover_copy=data.get("cover_copy", ""),
                call_to_action=data.get("call_to_action", "")
            )
        except Exception as e:
            print(f"LLM error: {e}")
    
    # Fallback
    return TextGenerationOutput(
        title=f"【必看】{input.topic}的秘密",
        content=f"今天来聊聊{input.topic}...",
        hashtags=[input.platform, input.topic, "干货", "种草"],
        cover_copy="不看后悔！",
        call_to_action="点赞收藏，评论区聊聊你的想法"
    )


@mcp.tool()
async def generate_script(input: ScriptGenerationInput) -> ScriptGenerationOutput:
    """
    生成视频脚本
    
    根据主题和时长生成完整的视频脚本
    """
    # 计算每段时长
    segment_duration = input.duration // 5
    
    hooks = {
        "curiosity": "你有没有好奇过，为什么...",
        "pain_point": "是不是经常遇到这样的问题...",
        "benefit": "学会这招，让你轻松...",
        "story": "去年这个时候，我遇到了一件特别的事..."
    }
    
    hook = hooks.get(input.hook_type, hooks["curiosity"])
    
    return ScriptGenerationOutput(
        title=f"【{input.topic}】完整攻略",
        hook=hook,
        script_segments=[
            {"time": f"0-{segment_duration}s", "content": "开场钩子 + 自我介绍", "visual": "真人出镜，表情夸张"},
            {"time": f"{segment_duration}-{segment_duration*2}s", "content": "问题陈述", "visual": "字幕+示意图"},
            {"time": f"{segment_duration*2}-{segment_duration*3}s", "content": "解决方案介绍", "visual": "产品展示/操作录屏"},
            {"time": f"{segment_duration*3}-{segment_duration*4}s", "content": "效果展示/案例", "visual": "对比图/数据可视化"},
            {"time": f"{segment_duration*4}-{input.duration}s", "content": "总结 + CTA", "visual": "真人出镜"},
        ],
        visual_notes=["开头3秒必须抓人眼球", "每15秒一个信息点", "字幕要大要清晰"],
        bgm_suggestion="轻快节奏，符合平台调性",
        total_duration=input.duration
    )


@mcp.tool()
async def optimize_title(titles: List[str], platform: str, user_id: str) -> Dict[str, Any]:
    """
    优化标题
    
    分析并提供标题优化建议
    """
    optimizations = []
    
    for title in titles:
        suggestions = []
        
        # 检查是否包含数字
        if not any(c.isdigit() for c in title):
            suggestions.append("加入数字，如'3个技巧'、'5分钟学会'")
        
        # 检查长度
        if len(title) < 10:
            suggestions.append("标题稍短，可以增加具体信息")
        elif len(title) > 30:
            suggestions.append("标题较长，考虑精简")
        
        # 检查情感词
        emotional_words = ["必看", "震惊", "绝了", "干货", "救命"]
        if not any(w in title for w in emotional_words):
            suggestions.append("考虑加入情感词增强吸引力")
        
        optimizations.append({
            "original": title,
            "suggestions": suggestions,
            "optimized": title if not suggestions else f"【优化建议】{title}"
        })
    
    return {
        "optimizations": optimizations,
        "best_practices": ["前10字最关键", "使用数字和具体信息", "制造悬念或承诺利益"]
    }


@mcp.tool()
async def suggest_visual(content_type: str, platform: str, topic: str, user_id: str) -> Dict[str, Any]:
    """
    提供视觉建议
    
    为内容提供封面、配图等视觉建议
    """
    return {
        "cover_style": "真人出镜 + 大字体标题 + 高对比配色",
        "color_scheme": ["亮黄色", "黑色", "白色"],
        "font_recommendation": "粗体无衬线字体",
        "layout": "中心构图，标题在上半部分",
        "elements": ["产品主体", "效果对比", "数字标注"],
        "tools": ["Canva", "醒图", "美图秀秀"]
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
