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
    platform: str
    content_type: str
    tone: str = "professional"
    keywords: Optional[List[str]] = None
    user_id: str


class TextGenerationOutput(BaseModel):
    """文案生成输出"""
    title: str
    content: str
    hashtags: List[str]
    cover_copy: str
    call_to_action: str


class ScriptGenerationInput(BaseModel):
    """脚本生成输入"""
    topic: str
    platform: str
    duration: int
    hook_type: str = "curiosity"
    target_audience: Optional[str] = None
    user_id: str


class ScriptGenerationOutput(BaseModel):
    """脚本生成输出"""
    title: str
    hook: str
    script_segments: List[Dict[str, Any]]
    visual_notes: List[str]
    bgm_suggestion: str
    total_duration: int


@mcp.tool()
async def generate_text(input: TextGenerationInput) -> TextGenerationOutput:
    """
    生成营销文案
    
    使用 LLM 根据主题、平台和调性生成专业文案
    """
    # 平台特定模板
    platform_specs = {
        "xiaohongshu": {
            "structure": "痛点引入 + 解决方案 + 使用体验 + 购买建议",
            "emoji_usage": "适量，增加亲和力",
            "length": "300-800字",
            "style": "真实分享、种草氛围"
        },
        "douyin": {
            "structure": "黄金3秒 + 信息密度 + 引导互动",
            "emoji_usage": "大量使用，增强表现力",
            "length": "50-200字",
            "style": "口语化、快节奏"
        },
        "bilibili": {
            "structure": "知识密度 + 逻辑清晰 + 社区黑话",
            "emoji_usage": "少量，专业为主",
            "length": "500-1500字",
            "style": "深度、硬核、有梗"
        }
    }
    
    spec = platform_specs.get(input.platform, platform_specs["xiaohongshu"])
    
    prompt = f"""作为资深文案创作者，请为{input.platform}平台创作一篇{input.content_type}：

主题：{input.topic}
调性：{input.tone}
关键词：{input.keywords or []}

平台要求：
- 结构：{spec['structure']}
- Emoji使用：{spec['emoji_usage']}
- 长度：{spec['length']}
- 风格：{spec['style']}

请生成：
1. 吸睛标题（使用数字、悬念或利益点，15-25字）
2. 正文内容（符合平台风格和结构）
3. 相关标签（5-8个，包含热门标签）
4. 封面文案（10-15字，突出核心利益）
5. 引导行动的结尾（自然且有吸引力）

以 JSON 格式输出：
{{
    "title": "...",
    "content": "...",
    "hashtags": [],
    "cover_copy": "...",
    "call_to_action": "..."
}}"""
    
    try:
        from lumina_skills.llm_utils import call_llm
        
        result = await call_llm(
            prompt=prompt,
            skill_name="creative_studio",
            temperature=0.8,
            response_format={"type": "json_object"},
            fallback_response={
                "title": f"【必看】{input.topic}的秘密",
                "content": f"今天来聊聊{input.topic}...（这是fallback内容）",
                "hashtags": [input.platform, input.topic, "干货", "种草"],
                "cover_copy": "不看后悔！",
                "call_to_action": "点赞收藏，评论区聊聊你的想法"
            }
        )
        
        return TextGenerationOutput(
            title=result.get("title", f"【必看】{input.topic}"),
            content=result.get("content", ""),
            hashtags=result.get("hashtags", [input.platform, input.topic]),
            cover_copy=result.get("cover_copy", "必看！"),
            call_to_action=result.get("call_to_action", "点赞关注")
        )
        
    except Exception as e:
        print(f"[generate_text] LLM 调用失败: {e}")
        return TextGenerationOutput(
            title=f"【必看】{input.topic}的终极指南",
            content=f"关于{input.topic}，你想知道的都在这里...",
            hashtags=[input.platform, input.topic, "干货", "必看"],
            cover_copy="不看后悔！",
            call_to_action="觉得有用就点赞收藏吧"
        )


@mcp.tool()
async def generate_script(input: ScriptGenerationInput) -> ScriptGenerationOutput:
    """
    生成视频脚本
    
    使用 LLM 生成专业的视频拍摄脚本
    """
    # 计算每段时长
    segment_duration = input.duration // 5
    
    hook_templates = {
        "curiosity": [
            "你有没有好奇过，为什么{topic}？",
            "{topic}的真相，90%的人都不知道！",
            "关于{topic}，我有一个大胆的猜测..."
        ],
        "pain_point": [
            "是不是经常遇到{topic}的问题？",
            "{topic}让你头疼？今天教你解决！",
            "别再为{topic}烦恼了！"
        ],
        "benefit": [
            "学会这招，让你轻松搞定{topic}！",
            "掌握{topic}，效率提升300%！",
            "{topic}的正确打开方式，建议收藏！"
        ],
        "story": [
            "去年这个时候，我遇到了一个关于{topic}的难题...",
            "讲一个{topic}改变我生活的故事...",
            "关于{topic}，我要分享一个亲身经历..."
        ]
    }
    
    hooks = hook_templates.get(input.hook_type, hook_templates["curiosity"])
    import random
    hook_template = random.choice(hooks)
    hook = hook_template.format(topic=input.topic)
    
    prompt = f"""作为资深短视频导演，请为{input.platform}平台创作一个{input.duration}秒的视频脚本：

主题：{input.topic}
钩子文案：{hook}
目标受众：{input.target_audience or '通用受众'}

要求：
1. 前3秒使用提供的钩子文案
2. 将{input.duration}秒分成5段，每段有明确的时间、内容、画面、字幕
3. 每15秒一个情绪起伏或信息点
4. 结尾有明确的CTA
5. 标注BGM建议

以 JSON 格式输出：
{{
    "title": "...",
    "hook": "{hook}",
    "script_segments": [
        {{"time": "0-{segment_duration}s", "content": "...", "visual": "...", "subtitle": "..."}}
    ],
    "visual_notes": [],
    "bgm_suggestion": "...",
    "total_duration": {input.duration}
}}"""
    
    try:
        from lumina_skills.llm_utils import call_llm
        
        result = await call_llm(
            prompt=prompt,
            skill_name="creative_studio",
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        
        segments = result.get("script_segments", [])
        if not segments:
            # 生成默认分段
            segments = _generate_default_segments(input.topic, input.duration, hook)
        
        return ScriptGenerationOutput(
            title=result.get("title", f"【{input.topic}】完整攻略"),
            hook=result.get("hook", hook),
            script_segments=segments,
            visual_notes=result.get("visual_notes", ["开头3秒必须抓人眼球", "字幕要大要清晰"]),
            bgm_suggestion=result.get("bgm_suggestion", "轻快节奏"),
            total_duration=input.duration
        )
        
    except Exception as e:
        print(f"[generate_script] LLM 调用失败: {e}")
        return ScriptGenerationOutput(
            title=f"【{input.topic}】完整攻略",
            hook=hook,
            script_segments=_generate_default_segments(input.topic, input.duration, hook),
            visual_notes=["开头3秒必须抓人眼球", "每15秒一个信息点", "字幕要大要清晰"],
            bgm_suggestion="轻快节奏，符合平台调性",
            total_duration=input.duration
        )


def _generate_default_segments(topic: str, duration: int, hook: str) -> List[Dict[str, Any]]:
    """生成默认脚本分段"""
    segment_duration = duration // 5
    return [
        {
            "time": f"0-{segment_duration}s",
            "content": f"{hook} + 自我介绍",
            "visual": "真人出镜，表情夸张有吸引力",
            "subtitle": hook[:15]
        },
        {
            "time": f"{segment_duration}-{segment_duration*2}s",
            "content": f"问题陈述：{topic}的常见痛点",
            "visual": "字幕+示意图/场景展示",
            "subtitle": "你是不是也遇到过？"
        },
        {
            "time": f"{segment_duration*2}-{segment_duration*3}s",
            "content": "解决方案介绍",
            "visual": "产品展示/操作录屏/步骤演示",
            "subtitle": "解决方法来了"
        },
        {
            "time": f"{segment_duration*3}-{segment_duration*4}s",
            "content": "效果展示或案例",
            "visual": "对比图/数据可视化/成果展示",
            "subtitle": "看效果！"
        },
        {
            "time": f"{segment_duration*4}-{duration}s",
            "content": "总结 + CTA",
            "visual": "真人出镜，真诚表情",
            "subtitle": "点赞关注，持续分享"
        }
    ]


@mcp.tool()
async def optimize_title(titles: List[str], platform: str, user_id: str) -> Dict[str, Any]:
    """
    优化标题
    
    使用规则和 LLM 分析并提供标题优化建议
    """
    optimizations = []
    
    for title in titles:
        issues = []
        suggestions = []
        
        # 规则检查
        # 1. 检查是否包含数字
        if not any(c.isdigit() for c in title):
            issues.append("缺少数字")
            suggestions.append("加入数字增强可信度，如'3个技巧'、'5分钟学会'")
        
        # 2. 检查长度
        title_len = len(title)
        platform_limits = {
            "douyin": (8, 25),
            "xiaohongshu": (10, 20),
            "bilibili": (15, 40)
        }
        min_len, max_len = platform_limits.get(platform, (10, 30))
        
        if title_len < min_len:
            issues.append("标题过短")
            suggestions.append(f"标题稍短，建议增加到{min_len}-{max_len}字")
        elif title_len > max_len:
            issues.append("标题过长")
            suggestions.append(f"标题较长，考虑精简到{max_len}字以内")
        
        # 3. 检查情感词/吸引力词
        emotional_words = ["必看", "震惊", "绝了", "干货", "救命", "揭秘", "真相"]
        has_emotional = any(w in title for w in emotional_words)
        if not has_emotional:
            issues.append("缺少吸引力词")
            suggestions.append("考虑加入情感词如'必看'、'揭秘'、'干货'增强吸引力")
        
        # 4. 检查疑问词（互动性）
        question_words = ["?", "？", "如何", "怎么", "为什么", "吗"]
        has_question = any(w in title for w in question_words)
        if not has_question and platform == "xiaohongshu":
            suggestions.append("考虑使用疑问句式增加互动性")
        
        # 5. 检查利益点
        benefit_words = ["轻松", "快速", "简单", "免费", "省钱", "高效"]
        has_benefit = any(w in title for w in benefit_words)
        if not has_benefit:
            suggestions.append("突出利益点，如'轻松'、'快速'、'省钱'")
        
        # 计算分数
        score = 100 - len(issues) * 15 - len(suggestions) * 5
        score = max(60, min(100, score))
        
        optimizations.append({
            "original": title,
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "optimized": title if score >= 85 else await _generate_optimized_title(title, platform, suggestions)
        })
    
    # 使用 LLM 生成整体优化建议
    try:
        from lumina_skills.llm_utils import call_llm
        
        prompt = f"""基于以下{platform}平台的标题，提供整体优化建议：

标题列表：{titles}

请提供：
1. 该平台标题的最佳实践（3-5条）
2. 当前标题的共同问题
3. 改进方向建议

以 JSON 格式输出。"""
        
        llm_result = await call_llm(
            prompt=prompt,
            skill_name="creative_studio",
            temperature=0.7,
            response_format={"type": "json_object"},
            fallback_response={
                "best_practices": [
                    f"{platform}标题前10字最关键",
                    "使用数字和具体信息",
                    "制造悬念或承诺利益",
                    "避免标题党但要有吸引力"
                ],
                "common_issues": "根据分析结果",
                "improvement_direction": "参考具体建议"
            }
        )
        
        return {
            "optimizations": optimizations,
            "llm_insights": llm_result,
            "platform": platform
        }
        
    except Exception as e:
        return {
            "optimizations": optimizations,
            "best_practices": [
                f"{platform}标题前10字最关键",
                "使用数字和具体信息",
                "制造悬念或承诺利益",
                "避免标题党但要有吸引力"
            ],
            "error": str(e)
        }


async def _generate_optimized_title(original: str, platform: str, suggestions: List[str]) -> str:
    """使用 LLM 生成优化后的标题"""
    try:
        from lumina_skills.llm_utils import call_llm
        
        prompt = f"""优化以下标题：

原标题：{original}
平台：{platform}
改进建议：{suggestions}

请生成一个优化后的标题，保持原意但更具吸引力。
只返回标题文本，不要解释。"""
        
        result = await call_llm(
            prompt=prompt,
            skill_name="creative_studio",
            temperature=0.8,
        )
        
        return result.get("content", original)[:30]
        
    except Exception:
        # 简单的字符串优化
        prefixes = ["【干货】", "【必看】", "【揭秘】"]
        if not any(p in original for p in prefixes):
            return f"【干货】{original}"[:30]
        return original


@mcp.tool()
async def batch_generate_variations(
    master_content: Dict[str, Any],
    variations: List[Dict[str, str]],
    user_id: str
) -> Dict[str, Any]:
    """
    批量生成内容变体
    
    为主内容生成多个变体版本
    """
    results = []
    
    for var in variations:
        variation_type = var.get("type", "general")
        target_platform = var.get("platform", "xiaohongshu")
        
        try:
            # 调用 generate_text 生成变体
            from pydantic import BaseModel
            
            class TempInput(BaseModel):
                topic: str
                platform: str
                content_type: str
                tone: str
                keywords: List[str]
                user_id: str
            
            input_data = TempInput(
                topic=master_content.get("topic", "主题"),
                platform=target_platform,
                content_type=var.get("content_type", "post"),
                tone=var.get("tone", "professional"),
                keywords=master_content.get("keywords", []),
                user_id=user_id
            )
            
            result = await generate_text(input_data)
            
            results.append({
                "variation_type": variation_type,
                "platform": target_platform,
                "title": result.title,
                "content_preview": result.content[:100] + "..." if len(result.content) > 100 else result.content,
                "hashtags": result.hashtags
            })
            
        except Exception as e:
            results.append({
                "variation_type": variation_type,
                "error": str(e)
            })
    
    return {
        "master_topic": master_content.get("topic"),
        "variations_generated": len(results),
        "variations": results
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
