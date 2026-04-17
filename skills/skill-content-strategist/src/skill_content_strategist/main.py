"""
内容策略师 Skill - MCP Server

提供账号定位、选题策略、内容规划等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

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

mcp = FastMCP("content_strategist")


def _load_platform_spec(platform: str) -> Dict[str, str]:
    """加载平台规范库中的 DNA 和审核规则"""
    try:
        spec = PlatformRegistry().load(platform)
        dna_lines = [f"- {item.get('element', '')}: {item.get('value', '')}" for item in spec.content_dna]
        audit_lines = [
            f"- {rule.get('category', '')}类禁用词: {', '.join(rule.get('forbidden_terms', []))}"
            for rule in spec.audit_rules
        ]
        platform_dna = "\n".join(dna_lines) if dna_lines else "- 暂无平台DNA规范"
        audit_rules = "\n".join(audit_lines) if audit_lines else "- 暂无特殊审核规则"
    except Exception:
        platform_dna = "- 暂无平台DNA规范"
        audit_rules = "- 暂无特殊审核规则"
    return {"dna": platform_dna, "audit": audit_rules}


class PositioningInput(BaseModel):
    """定位分析输入"""
    platform: str
    niche: str
    target_audience: Optional[str] = None
    competitor_accounts: Optional[List[str]] = None
    user_id: str


class PositioningOutput(BaseModel):
    """定位分析输出"""
    positioning_statement: str
    target_persona: Dict[str, Any]
    content_pillars: List[str]
    differentiation: str
    posting_frequency: str


class TopicCalendarInput(BaseModel):
    """选题日历输入"""
    platform: str
    niche: str
    positioning: str
    duration_days: int = 30
    user_id: str


class TopicCalendarOutput(BaseModel):
    """选题日历输出"""
    calendar: List[Dict[str, Any]]
    theme_weeks: List[Dict[str, Any]]
    hot_topics: List[str]


@mcp.tool()
async def analyze_positioning(input: PositioningInput) -> PositioningOutput:
    """
    分析账号定位
    
    使用 LLM 进行专业的定位分析
    """
    spec = _load_platform_spec(input.platform)

    # 为定位分析加载定位方法论
    positioning_meth = build_methodology_prompt("positioning") or ""

    # 构建提示词
    prompt = f"""作为资深内容策略师，请为以下账号进行定位分析：

平台：{input.platform}
赛道：{input.niche}
目标受众：{input.target_audience or '未指定'}
对标账号：{input.competitor_accounts or '未指定'}

平台 DNA 规范（来自平台规范库）：
{spec['dna']}

平台审核规则：
{spec['audit']}

{positioning_meth}

请提供：
1. 一句话定位声明（我是谁，为谁，提供什么价值）
2. 目标人群画像（年龄、性别、痛点、需求）
3. 3-5个内容支柱（核心内容方向，需结合平台 DNA 与上述方法论）
4. 差异化策略（如何与竞品区隔，并符合平台调性与方法论框架）
5. 发布频率建议

以 JSON 格式输出：
{{
    "positioning_statement": "...",
    "target_persona": {{"age": "...", "gender": "...", "pain_points": [...], "needs": []}},
    "content_pillars": [],
    "differentiation": "...",
    "posting_frequency": "..."
}}"""
    
    try:
        from lumina_skills.llm_utils import call_llm
        
        result = await call_llm(
            prompt=prompt,
            skill_name="content_strategist",
            temperature=0.7,
            response_format={"type": "json_object"},
            fallback_response={
                "positioning_statement": f"专注{input.niche}领域的优质内容创作者",
                "target_persona": {"age": "18-35", "gender": "女性为主", "pain_points": ["信息不对称"], "needs": ["实用知识"]},
                "content_pillars": ["干货分享", "案例拆解", "避坑指南"],
                "differentiation": "深入浅出，实用导向",
                "posting_frequency": "每周3-4更"
            }
        )
        
        return PositioningOutput(
            positioning_statement=result.get("positioning_statement", ""),
            target_persona=result.get("target_persona", {}),
            content_pillars=result.get("content_pillars", []),
            differentiation=result.get("differentiation", ""),
            posting_frequency=result.get("posting_frequency", "每周3-4更")
        )
        
    except Exception as e:
        print(f"[analyze_positioning] LLM 调用失败: {e}")
        # 使用更智能的 fallback，基于输入生成
        return PositioningOutput(
            positioning_statement=f"专注{input.niche}领域的优质内容创作者，为{input.target_audience or '目标用户'}提供实用价值",
            target_persona={
                "age": "18-35",
                "gender": "女性为主",
                "pain_points": [f"{input.niche}信息不对称", "选择困难"],
                "needs": ["实用知识", "避坑指南"]
            },
            content_pillars=[f"{input.niche}干货", "案例拆解", "趋势解读", "工具推荐"],
            differentiation=f"深耕{input.niche}，提供可落地的实操方案",
            posting_frequency="每周3-4更"
        )


@mcp.tool()
async def generate_topic_calendar(input: TopicCalendarInput) -> TopicCalendarOutput:
    """
    生成选题日历
    
    使用 LLM 生成专业的选题规划
    """
    spec = _load_platform_spec(input.platform)

    # 根据赛道智能匹配内容方法论
    matched_meth_id = match_methodology_for_content(input.niche, content_type="calendar")
    calendar_meth = build_methodology_prompt(matched_meth_id) or ""

    prompt = f"""作为资深内容策略师，请为以下账号生成{input.duration_days}天的选题日历：

平台：{input.platform}
赛道：{input.niche}
账号定位：{input.positioning}

平台 DNA 规范（来自平台规范库）：
{spec['dna']}

平台审核规则：
{spec['audit']}

{calendar_meth}

要求：
1. 每天有明确的主题和话题
2. 内容形式要平台化（结合平台 DNA 与方法论选择短视频、图文等）
3. 考虑一周内的节奏变化
4. 规划4个主题周，每周有统一主题
5. 提供3-5个热点追踪建议
6. 选题需避开平台审核禁用词，符合平台调性与方法论框架

以 JSON 格式输出：
{{
    "calendar": [
        {{"day": 1, "date": "周一", "theme": "...", "topic": "...", "format": "视频/图文", "best_time": "18:00"}}
    ],
    "theme_weeks": [
        {{"week": 1, "theme": "...", "focus": "..."}}
    ],
    "hot_topics": ["...", "..."]
}}"""
    
    try:
        from lumina_skills.llm_utils import call_llm
        
        result = await call_llm(
            prompt=prompt,
            skill_name="content_strategist",
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        
        calendar = result.get("calendar", [])
        theme_weeks = result.get("theme_weeks", [])
        hot_topics = result.get("hot_topics", [])
        
        # 如果返回数据不完整，生成基础日历
        if not calendar:
            calendar = _generate_basic_calendar(input.niche, input.duration_days)
        if not theme_weeks:
            theme_weeks = [
                {"week": 1, "theme": "基础认知建立", "focus": "入门科普"},
                {"week": 2, "theme": "深度价值输出", "focus": "干货分享"},
                {"week": 3, "theme": "互动与转化", "focus": "案例互动"},
                {"week": 4, "theme": "趋势与展望", "focus": "行业趋势"},
            ]
        if not hot_topics:
            hot_topics = [f"{input.niche}行业最新趋势", "平台算法更新解读", "竞品爆款分析"]
        
        return TopicCalendarOutput(
            calendar=calendar,
            theme_weeks=theme_weeks,
            hot_topics=hot_topics
        )
        
    except Exception as e:
        print(f"[generate_topic_calendar] LLM 调用失败: {e}")
        # 生成基础日历
        return TopicCalendarOutput(
            calendar=_generate_basic_calendar(input.niche, input.duration_days),
            theme_weeks=[
                {"week": 1, "theme": "基础认知建立", "focus": "入门科普"},
                {"week": 2, "theme": "深度价值输出", "focus": "干货分享"},
                {"week": 3, "theme": "互动与转化", "focus": "案例互动"},
                {"week": 4, "theme": "趋势与展望", "focus": "行业趋势"},
            ],
            hot_topics=[f"{input.niche}行业最新趋势", "平台算法更新解读", "竞品爆款分析"]
        )


def _generate_basic_calendar(niche: str, duration_days: int) -> List[Dict[str, Any]]:
    """生成基础选题日历"""
    calendar = []
    themes = ["干货分享", "案例拆解", "互动话题", "热点追踪", "工具推荐"]
    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    
    for day in range(1, duration_days + 1):
        week_day = week_days[(day - 1) % 7]
        theme = themes[day % len(themes)]
        
        calendar.append({
            "day": day,
            "date": week_day,
            "theme": theme,
            "topic": f"{niche} - {theme}专题 #{day}",
            "format": "视频" if day % 2 == 1 else "图文",
            "best_time": "18:00" if day % 2 == 1 else "12:00"
        })
    
    return calendar


@mcp.tool()
async def predict_trends(niche: str, platform: str, user_id: str) -> Dict[str, Any]:
    """
    预测热点趋势
    
    使用 LLM + RPA 抓取的真实趋势数据
    """
    # 首先尝试获取平台真实趋势
    hot_topics = []
    try:
        from rpa.skill_utils import get_rpa_helper
        
        rpa = get_rpa_helper()
        result = await rpa.fetch_platform_data(
            platform=platform,
            data_type="hot_topics",
            account_id=user_id,
        )
        
        if result.success:
            hot_topics = [t.get("title", "") for t in result.data.get("hot_topics", [])[:5]]
    except Exception as e:
        print(f"[predict_trends] RPA 获取趋势失败: {e}")
    
    spec = _load_platform_spec(platform)

    # 热点趋势匹配热点借势方法论
    trend_meth = build_methodology_prompt("trend_ride") or ""

    # 使用 LLM 分析趋势
    prompt = f"""基于以下信息，预测 {niche} 领域在 {platform} 平台的热点趋势：

赛道：{niche}
平台：{platform}
当前热门话题：{hot_topics or '未获取'}

平台 DNA 规范（来自平台规范库）：
{spec['dna']}

平台审核规则：
{spec['audit']}

{trend_meth}

请提供：
1. 新兴话题（3-5个，需符合平台调性）
2. 季节性机会（2-3个）
3. 推荐内容形式（结合平台 DNA 与热点借势方法论）
4. 趋势可信度评分（0-1）

以 JSON 格式输出。"""
    
    try:
        from lumina_skills.llm_utils import call_llm
        
        result = await call_llm(
            prompt=prompt,
            skill_name="content_strategist",
            temperature=0.8,
            response_format={"type": "json_object"},
            fallback_response={
                "emerging_topics": [f"{niche}新玩法", "AI+内容创作", "短剧营销"],
                "seasonal_opportunities": ["618购物节", "暑期档", "开学季"],
                "content_formats": ["短视频", "图文笔记", "直播切片"],
                "confidence": 0.75,
                "real_time_topics": hot_topics
            }
        )
        
        return {
            "emerging_topics": result.get("emerging_topics", []),
            "seasonal_opportunities": result.get("seasonal_opportunities", []),
            "content_formats": result.get("content_formats", []),
            "confidence": result.get("confidence", 0.75),
            "real_time_topics": hot_topics,
            "data_source": "llm+rpa" if hot_topics else "llm_only"
        }
        
    except Exception as e:
        return {
            "emerging_topics": [f"{niche}新玩法", "AI+内容创作", "短剧营销"],
            "seasonal_opportunities": ["618购物节", "暑期档", "开学季"],
            "content_formats": ["短视频", "图文笔记", "直播切片"],
            "confidence": 0.75,
            "real_time_topics": hot_topics,
            "error": str(e)
        }


@mcp.tool()
async def analyze_competitor_real(
    competitor_id: str,
    platform: str,
    analysis_depth: str = "standard",
    user_id: str = None,
) -> Dict[str, Any]:
    """
    真实竞品分析
    
    使用 RPA 抓取竞品账号的真实数据
    """
    if user_id is None:
        user_id = "system"
    
    # 构建竞品账号 URL
    platform_urls = {
        "douyin": f"https://www.douyin.com/user/{competitor_id}",
        "xiaohongshu": f"https://www.xiaohongshu.com/user/profile/{competitor_id}",
    }
    
    account_url = platform_urls.get(platform)
    if not account_url:
        return {
            "error": f"不支持的平台: {platform}",
            "competitor_id": competitor_id,
        }
    
    try:
        from rpa.skill_utils import get_rpa_helper
        
        rpa = get_rpa_helper()
        result = await rpa.crawl_account(
            account_url=account_url,
            platform=platform,
            account_id=competitor_id,
            user_id=user_id,
            max_contents=15 if analysis_depth == "deep" else 10,
        )
        
        if not result.success:
            return {
                "competitor_id": competitor_id,
                "platform": platform,
                "error": result.error,
                "fallback_analysis": await _fallback_competitor_analysis(competitor_id, platform)
            }
        
        data = result.data
        diagnosis = data.get("diagnosis", {})
        recent_contents = data.get("recent_contents", [])
        
        # 使用 LLM 深度分析
        if analysis_depth in ["standard", "deep"]:
            spec = _load_platform_spec(platform)

            # 竞品分析可结合定位与差异化方法论
            competitor_meth = build_methodology_prompt("positioning") or ""

            prompt = f"""基于以下竞品数据，进行深度分析：

竞品昵称：{data.get('nickname')}
简介：{data.get('bio')}
粉丝数：{data.get('followers')}
获赞数：{data.get('likes')}
作品数：{data.get('content_count')}
内容类型：{diagnosis.get('account_gene', {}).get('content_types')}
风格标签：{diagnosis.get('account_gene', {}).get('style_tags')}

最近作品内容：
{[c.get('title', '') for c in recent_contents[:5]]}

平台 DNA 规范（来自平台规范库）：
{spec['dna']}

平台审核规则：
{spec['audit']}

{competitor_meth}

请提供：
1. 优势和劣势分析（结合平台 DNA 与定位方法论评估内容适配度）
2. 可学习的策略（符合平台调性的打法）
3. 差异化机会

以 JSON 格式输出。"""
            
            try:
                from lumina_skills.llm_utils import call_llm
                
                llm_result = await call_llm(
                    prompt=prompt,
                    skill_name="content_strategist",
                    temperature=0.7,
                    response_format={"type": "json_object"},
                )
                
                return {
                    "competitor_id": competitor_id,
                    "platform": platform,
                    "analysis_depth": analysis_depth,
                    "real_data": True,
                    "overview": {
                        "nickname": data.get("nickname"),
                        "bio": data.get("bio"),
                        "followers": data.get("followers"),
                        "following": data.get("following"),
                        "likes": data.get("likes"),
                        "content_count": data.get("content_count"),
                        "health_score": diagnosis.get("health_score"),
                    },
                    "content_analysis": {
                        "content_types": diagnosis.get("account_gene", {}).get("content_types"),
                        "style_tags": diagnosis.get("account_gene", {}).get("style_tags"),
                        "recent_contents": recent_contents[:5],
                    },
                    "llm_analysis": llm_result,
                    "crawled_at": data.get("crawled_at"),
                }
                
            except Exception as e:
                print(f"[analyze_competitor_real] LLM 分析失败: {e}")
        
        # 基础分析（无 LLM）
        return {
            "competitor_id": competitor_id,
            "platform": platform,
            "analysis_depth": analysis_depth,
            "real_data": True,
            "overview": {
                "nickname": data.get("nickname"),
                "bio": data.get("bio"),
                "followers": data.get("followers"),
                "likes": data.get("likes"),
                "content_count": data.get("content_count"),
                "health_score": diagnosis.get("health_score"),
            },
            "strengths": ["内容质量稳定", "更新频率高"] if data.get("content_count", 0) > 20 else ["有潜力"],
            "weaknesses": diagnosis.get("key_issues", []),
            "learnable_strategies": ["参考内容结构", "学习发布节奏"],
            "crawled_at": data.get("crawled_at"),
        }
        
    except Exception as e:
        return {
            "competitor_id": competitor_id,
            "platform": platform,
            "error": str(e),
            "fallback_analysis": await _fallback_competitor_analysis(competitor_id, platform)
        }


async def _fallback_competitor_analysis(competitor_id: str, platform: str) -> Dict[str, Any]:
    """竞品分析 fallback"""
    return {
        "competitor_id": competitor_id,
        "platform": platform,
        "note": "RPA 抓取失败，返回基础分析",
        "overview": {
            "follower_count": "未知",
            "content_style": "需手动分析",
        },
        "suggestions": ["尝试手动访问竞品主页获取信息"]
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
