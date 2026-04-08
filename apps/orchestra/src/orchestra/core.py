"""Layer 2：多 Agent 中枢 — 意图路由 + SOP DAG 骨架 + 调用 Skill Hub。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from knowledge_base.methodology_registry import MethodologyRegistry
from knowledge_base.platform_registry import PlatformRegistry
from skill_hub_client import SkillHubClient
from sop_engine import compile_methodology_dag


_CASUAL_GREETING = re.compile(
    r"^(你好|您好|哈喽|嗨|在吗|在么|有人吗|早上好|下午好|晚上好|早啊|晚安|"
    r"谢谢|多谢|感谢|谢了|不客气|拜拜|再见|好的|嗯嗯|嗯|好哒|ok|OK|哈喽|"
    r"hi|hello|hey)[\s!！。…~～，,]*$",
    re.I,
)


def _is_casual_or_greeting(text: str) -> bool:
    """寒暄、致谢、告别等短句，不走方法论检索。"""
    t = (text or "").strip()
    if not t or len(t) > 100:
        return False
    if _CASUAL_GREETING.match(t):
        return True
    if t in ("👋", "哈哈", "哈哈哈", "嗯", "好"):
        return True
    return False


_MARKETING_ANCHOR = re.compile(
    r"营销|账号|小红书|抖音|b站|bilibili|视频号|快手|内容|涨粉|流量|转化|"
    r"直播|笔记|种草|品牌|投放|达人|带货|私域|公域|爆款|钩子|选题|文案|脚本",
    re.I,
)

# 明显非营销场景（除非同句含营销锚点）
# 同步：vendor/openclaw/extensions/lumina-ai-marketing/intent-gate.ts（OpenClaw Layer1 闸）
_OFF_TOPIC_CHITCHAT = re.compile(
    r"天气|气温|下雨|下雪|刮风|台风|雾霾|冷不冷|热不热|"
    r"几点了|星期几|周几|今天是|"
    r"讲个笑话|讲个段子|讲故事|唱首歌|你会什么|你是谁做的|"
    r"晚饭吃|午饭吃|早餐吃|外卖吃|睡不着|累死了",
    re.I,
)

# 明确要「翻方法论库 / 检索框架」时才走 retrieve_methodology（general）
_METHODOLOGY_BROWSE = re.compile(
    r"方法论库|有哪些方法论|什么方法论|推荐.*方法论|匹配.*方法论|"
    r"检索.*方法|适合我的框架|运营框架|增长框架|内容框架|"
    r"AIDA|增长黑客|定位理论|4P|4C|漏斗模型",
    re.I,
)


def _has_marketing_anchor(text: str) -> bool:
    return bool(_MARKETING_ANCHOR.search(text or ""))


def _is_off_topic_chitchat(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 200:
        return False
    if not _OFF_TOPIC_CHITCHAT.search(t):
        return False
    return not _has_marketing_anchor(t)


# 用户对流程的质疑：应先澄清而非再用演示数据跑 Skill（须早于「诊断|账号」等规则）
_CLARIFY_FEEDBACK = re.compile(
    r"没问|不问|还没问|你为什么(不|没)|你应该先|连我.*都不知道|"
    r"假的|不真实|占位|随意编|糊弄|没理解|答非所问|乱(编|说)|"
    r"都不知道我.*账号|账号是什么|主页.*呢|链接呢",
    re.I,
)


def _is_clarify_feedback(text: str) -> bool:
    t = (text or "").strip()
    return bool(t and _CLARIFY_FEEDBACK.search(t))


def _is_demo_account_url(url: Optional[str]) -> bool:
    u = (url or "").strip().lower()
    if not u:
        return True
    if "example.com" in u or "/demo" in u or "demo." in u:
        return True
    if u.startswith("http://localhost"):
        return True
    return False


def _context_has_user_metrics(ctx: Dict[str, Any]) -> bool:
    """仅当调用方在 context 中显式传入非空 metrics 时，才视为用户已提供数据。"""
    if "metrics" not in ctx:
        return False
    m = ctx.get("metrics")
    if m is None or not isinstance(m, dict):
        return False
    return len(m) > 0


def _is_account_creation_or_howto(text: str) -> bool:
    """起号/新开账号/怎么做账号——走对话引导，勿当成「账号诊断」。"""
    t = (text or "").strip()
    if not t:
        return False
    if re.search(
        r"(想做|要做|准备做|打算做|想开|从零|从0|新手|刚注册).{0,16}账号|"
        r"做个账号|起号|开号|养号|新号|从0起号|"
        r"账号怎么(做|起)|怎么(做|起).*账号|如何起号|如何做账号",
        t,
        re.I,
    ):
        return True
    return False


def _is_diagnosis_intent(text: str) -> bool:
    """明确的「看号/体检」类诉求；单独的「账号」二字不命中。"""
    t = (text or "").strip()
    if re.search(r"诊断|基因|体检", t):
        return True
    if re.search(
        r"账号.{0,10}(诊断|分析|看看|瞧瞧|瞅瞅|体检|评估|问题|好不好|怎么样|咋样|还有救|废了没)|"
        r"(诊断|分析|看看|瞧瞧|瞅瞅|体检|评估).{0,10}账号|"
        r"帮(我)?(看|瞧).{0,6}号|看看(我)?(这|这个)?号",
        t,
        re.I,
    ):
        return True
    return False


def _conversation_fallback_reply(user_input: str) -> Optional[str]:
    """无 LLM 时的场景化兜底，避免所有对话都复读同一段开场白。"""
    t = (user_input or "").strip()
    if not t:
        return None

    if re.search(
        r"你能(帮)?我(做)?什么|你会什么|有什么功能|能干什么|可以做什么|介绍下你|介绍一下你|你是(做)?什么的",
        t,
        re.I,
    ):
        return (
            "可以啊，我主要能帮你这几块——你挑一个最贴你现状的，我们往下细聊：\n"
            "• **起号与定位**：选平台、人群、内容方向怎么定；\n"
            "• **流量与数据**：曝光/互动变差时一起拆原因（你愿意的话可以补一点数字）；\n"
            "• **文案与脚本**：种草标题、正文、短视频分镜草稿；\n"
            "• **风险合规**：稿子有没有容易踩线的说法；\n"
            "• **方法论 SOP**：比如按 AIDA 一步步带你过。\n\n"
            "你现在最卡的是哪一步？一句话说说也行。"
        )

    if re.search(
        r"僵硬|生硬|死板|像机器人|复读|模板|机械|不自然|敷衍|没意思|太官方",
        t,
        re.I,
    ):
        return (
            "说得对，刚才那种「说明书腔」确实容易听着硬。\n"
            "我这边在无大模型兜底时会话比较模板化，后面我会改口风：你可以选更想怎么聊——"
            "**随便聊**捋思路，或 **直接要步骤/清单**。你现在更想要哪一种？"
        )

    if _is_account_creation_or_howto(t):
        return (
            "做新账号可以一步步来。先对齐三件事：**选哪个平台**、**你想吸引谁**、**你擅长讲什么**。\n"
            "你更想做图文还是短视频？有没有已经想好的赛道（比如美妆、职场、家居）？说一句就行。"
        )

    if _is_casual_or_greeting(t):
        if re.match(r"^(谢谢|感谢|谢了|多谢|谢啦)", t):
            return "不客气～后面要是还有选题、文案、流量之类的事，继续叫我就行。"
        if len(t) <= 20 and not re.search(r"什么|帮|做|账号|流量", t):
            return "嗨，我在～你更想聊**起号**、**流量数据**，还是**写文案/脚本**？随便从一句开始。"

    return None


# 平台名称识别（用于多轮对话中检测用户补充的平台信息）
_PLATFORM_NAMES = re.compile(
    r"(小红书|抖音|B站|bilibili|视频号|快手|微博|知乎|公众号|今日头条)",
    re.I,
)

# 检测是否为账号信息补充格式（平台 + 昵称/账号名）
_ACCOUNT_INFO_SUPPLY = re.compile(
    r"(小红书|抖音|B站|bilibili|视频号|快手|微博|知乎|公众号|今日头条).{0,5}([\w\u4e00-\u9fa5]{2,20})|"
    r"([\w\u4e00-\u9fa5]{2,20}).{0,3}(小红书|抖音|B站|bilibili|视频号|快手)",
    re.I,
)


def _is_diagnosis_followup(user_input: str, session_history: List[Dict[str, Any]]) -> bool:
    """
    检测当前输入是否为对上一轮诊断澄清的回复。
    
    场景：上轮系统要求提供"平台+昵称"，本轮用户回复"抖音平台，金木林"之类的。
    """
    if not session_history:
        return False
    
    # 获取上一轮助手回复
    last_assistant_msg = None
    for msg in reversed(session_history):
        if msg.get("role") == "assistant":
            last_assistant_msg = msg.get("content", "")
            break
    
    if not last_assistant_msg:
        return False
    
    # 上轮是否在要求补充账号信息
    is_asking_for_account = any(
        phrase in last_assistant_msg
        for phrase in [
            "主页链接",
            "平台 + 可搜索",
            "平台+可搜索",
            "锁定是哪个账号",
            "先锁定是哪个账号",
        ]
    )
    
    if not is_asking_for_account:
        return False
    
    # 本轮输入是否包含平台名称
    has_platform = bool(_PLATFORM_NAMES.search(user_input))
    
    # 本轮输入看起来像账号信息（平台+昵称组合，或包含平台名）
    looks_like_account_info = bool(_ACCOUNT_INFO_SUPPLY.search(user_input)) or has_platform
    
    return looks_like_account_info


class MarketingOrchestra:
    def __init__(self) -> None:
        self.methodology_lib = MethodologyRegistry()
        self.platform_lib = PlatformRegistry()
        self.skill_hub_client = SkillHubClient()

    def _classify_intent(
        self, user_input: str, session_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        t = (user_input or "").strip()
        session_history = session_history or []
        
        if _is_casual_or_greeting(t):
            return {"kind": "conversation", "sop_id": None}
        if _is_off_topic_chitchat(t):
            return {"kind": "conversation", "sop_id": None}
        if _is_clarify_feedback(t):
            return {"kind": "clarify_feedback", "sop_id": None}
        # 检测是否为诊断意图的跟进回复（补充账号信息）
        if _is_diagnosis_followup(t, session_history):
            return {"kind": "diagnosis", "sop_id": None}
        # 先判「流量/曝光」再判「账号」，避免「有账号但流量差」被误路由成仅诊断
        if re.search(
            r"流量|曝光|播放|阅读|上不去|没人看|不涨粉|掉粉|下滑|漏斗|ctr|互动率",
            t,
            re.I,
        ):
            return {"kind": "traffic", "sop_id": None}
        if _is_account_creation_or_howto(t):
            return {"kind": "conversation", "sop_id": None}
        if _is_diagnosis_intent(t):
            return {"kind": "diagnosis", "sop_id": None}
        if re.search(r"数据|指标", t):
            return {"kind": "traffic", "sop_id": None}
        if re.search(r"风险|违规|审核", t):
            return {"kind": "risk", "sop_id": None}
        if re.search(r"文案|生成|标题", t):
            return {"kind": "content", "sop_id": None}
        if re.search(r"脚本|分镜|视频", t):
            return {"kind": "script", "sop_id": None}
        if re.search(r"选题|日历|热点", t):
            return {"kind": "topic", "sop_id": None}
        if re.search(r"方法论|SOP|步骤", t):
            return {"kind": "methodology", "sop_id": "aida_advanced"}
        if re.search(r"案例|对标", t):
            return {"kind": "cases", "sop_id": None}
        if re.search(r"新闻|资讯|行业", t):
            return {"kind": "news", "sop_id": None}
        if re.search(r"竞品|对手", t):
            return {"kind": "competitor", "sop_id": None}
        if re.search(r"图表|可视化", t):
            return {"kind": "viz", "sop_id": None}
        if re.search(r"知识库|问答|什么是", t):
            return {"kind": "qa", "sop_id": None}
        # 默认不再落到「general→方法论检索」，避免天气/闲聊等被误匹配 AIDA
        if _METHODOLOGY_BROWSE.search(t):
            return {"kind": "general", "sop_id": None}
        return {"kind": "conversation", "sop_id": None}

    def _extract_account_info_from_input(self, user_input: str) -> tuple[Optional[str], Optional[str]]:
        """
        从用户输入中提取平台名称和账号信息。
        
        支持的格式：
        - "抖音平台，金木林"
        - "小红书 xxx"
        - "抖音：xxx"
        - "我在抖音叫 xxx"
        
        返回: (platform_name, account_identifier)
        """
        t = (user_input or "").strip()
        if not t:
            return None, None
        
        # 平台名称映射（标准化）
        platform_mapping = {
            "小红书": "xiaohongshu",
            "抖音": "douyin",
            "b站": "bilibili",
            "bilibili": "bilibili",
            "视频号": "shipinhao",
            "快手": "kuaishou",
            "微博": "weibo",
            "知乎": "zhihu",
            "公众号": "wechat",
            "今日头条": "toutiao",
        }
        
        # 尝试匹配 "平台+账号" 模式
        # 模式1: "抖音平台，金木林" 或 "抖音，金木林"
        pattern1 = re.search(
            r"(小红书|抖音|B站|bilibili|视频号|快手|微博|知乎|公众号|今日头条).{0,5}[，,、:\s]+([\w\u4e00-\u9fa5]{2,20})",
            t, re.I
        )
        if pattern1:
            platform_cn = pattern1.group(1)
            account = pattern1.group(2).strip()
            platform_en = platform_mapping.get(platform_cn, "xiaohongshu")
            return platform_en, account
        
        # 模式2: 先提到账号名，然后说平台
        # "金木林，抖音" 或 "我叫金木林，在抖音"
        pattern2 = re.search(
            r"([\w\u4e00-\u9fa5]{2,20}).{0,5}(小红书|抖音|B站|bilibili|视频号|快手)",
            t, re.I
        )
        if pattern2:
            account = pattern2.group(1).strip()
            platform_cn = pattern2.group(2)
            platform_en = platform_mapping.get(platform_cn, "xiaohongshu")
            return platform_en, account
        
        # 模式3: 仅包含平台名称（后续可能需要进一步询问账号名）
        platform_only = _PLATFORM_NAMES.search(t)
        if platform_only:
            platform_cn = platform_only.group(1)
            platform_en = platform_mapping.get(platform_cn, "xiaohongshu")
            # 尝试提取后面的文字作为账号名
            after_platform = t[platform_only.end():].strip(" ，,、:\n")
            if after_platform and len(after_platform) <= 20:
                return platform_en, after_platform
            return platform_en, None
        
        return None, None

    async def run_sop(self, sop_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        platform = context.get("platform") or "xiaohongshu"
        dag = compile_methodology_dag(
            sop_id,
            platform,
            methodology_lib=self.methodology_lib,
            platform_lib=self.platform_lib,
        )
        results: Dict[str, Any] = {}
        for node in dag:
            skill = node.get("skill")
            params = dict(node.get("params") or {})
            params.setdefault("user_id", context.get("user_id") or "anonymous")
            params.setdefault("platform", platform)
            nid = node.get("id") or skill
            results[nid] = await self.skill_hub_client.call(skill or "", params)
        return {"dag": dag, "node_results": results}

    async def run_dynamic(
        self,
        user_input: str,
        context: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        uid = context.get("user_id") or "anonymous"
        platform = context.get("platform") or "xiaohongshu"
        kind = intent.get("kind")

        if kind == "clarify_feedback":
            return {
                "ok": True,
                "result": {
                    "type": "clarification",
                    "reason": "process_feedback",
                    "missing": ["account_url", "platform", "metrics"],
                    "reply": (
                        "你说得对：上一轮在没有你的**主页链接**或**真实后台数据**的情况下，"
                        "我不该当成已经做完分析。\n\n"
                        "请先补这几项里能提供的（越具体越好）：\n"
                        "1）**平台**（小红书 / 抖音 / 视频号等）；\n"
                        "2）**账号**：主页链接，或「平台 + 可搜到的昵称」；\n"
                        "3）若要看流量：**近 7 天**左右曝光/阅读、点赞、收藏、评论等（手抄数字或文字描述均可）。\n\n"
                        "补全后我会再调用诊断或流量分析；若你暂时只有账号没有数字，也可以说「只做账号诊断」或「先给通用优化清单」。"
                    ),
                },
            }

        if kind == "diagnosis":
            url = context.get("account_url")
            extracted_platform = None
            extracted_account = None
            
            # 如果 context 中没有有效的 account_url，尝试从用户输入中提取
            if _is_demo_account_url(url):
                # 尝试从用户输入中提取平台和账号信息
                extracted_platform, extracted_account = self._extract_account_info_from_input(user_input)
                if extracted_platform and extracted_account:
                    # 构造一个伪 URL 用于诊断
                    url = f"https://{extracted_platform}/{extracted_account}"
                    platform = extracted_platform
            
            if _is_demo_account_url(url):
                return {
                    "ok": True,
                    "result": {
                        "type": "clarification",
                        "reason": "no_account_url",
                        "missing": ["account_url", "platform"],
                        "reply": (
                            "要做**账号诊断**，需要先锁定是哪个账号：请发 **主页链接**，"
                            "或说明 **平台 + 可搜索到的昵称**。\n\n"
                            "当前能力侧未接自动爬取时，我会根据你补充的信息给结构化建议；"
                            "在缺少账号信息前，我不会再用演示数据假装已完成诊断。"
                        ),
                    },
                }
            
            # 如果提取了新的平台信息，使用它
            if extracted_platform:
                platform = extracted_platform
                
            return await self.skill_hub_client.call(
                "diagnose_account",
                {
                    "account_url": url,
                    "platform": platform,
                    "user_id": uid,
                },
            )
        if kind == "traffic":
            if not _context_has_user_metrics(context):
                return {
                    "ok": True,
                    "result": {
                        "type": "clarification",
                        "reason": "no_metrics",
                        "missing": ["metrics"],
                        "reply": (
                            "要做**流量结构分析**，需要你的真实数据（或手抄后台数字）。"
                            "请补充例如：**近 7 天** 曝光/阅读、点赞、收藏、评论、分享、主页访问等——有几项写几项。\n\n"
                            "API 调试时可在请求的 `context` 里传 `metrics`，例如 "
                            '`{"views": 12000, "likes": 480, "shares": 12}`。\n\n'
                            "若暂时没有数据、只要通用思路，请直接说「先给通用优化清单」，我按通用框架回复，不伪造漏斗数字。"
                        ),
                    },
                }
            return await self.skill_hub_client.call(
                "analyze_traffic",
                {
                    "metrics": context["metrics"],
                    "user_id": uid,
                    "platform": platform,
                },
            )
        if kind == "risk":
            return await self.skill_hub_client.call(
                "detect_risk",
                {
                    "content_text": user_input,
                    "platform": platform,
                },
            )
        if kind == "content":
            return await self.skill_hub_client.call(
                "generate_text",
                {
                    "topic": user_input[:200] or "品牌故事",
                    "platform": platform,
                    "content_dna": context.get("content_dna") or {},
                    "user_id": uid,
                },
            )
        if kind == "script":
            return await self.skill_hub_client.call(
                "generate_script",
                {
                    "topic": user_input[:120] or "产品种草",
                    "hook_type": "curiosity",
                    "duration": 60,
                    "platform": platform,
                    "user_id": uid,
                },
            )
        if kind == "topic":
            return await self.skill_hub_client.call(
                "select_topic",
                {
                    "industry": context.get("industry") or "beauty",
                    "user_id": uid,
                    "platform": platform,
                },
            )
        if kind == "cases":
            return await self.skill_hub_client.call(
                "match_cases",
                {
                    "content_type": "note",
                    "industry": context.get("industry") or "general",
                    "user_id": uid,
                },
            )
        if kind == "news":
            return await self.skill_hub_client.call(
                "fetch_industry_news",
                {"category": context.get("industry") or "general", "days": 3},
            )
        if kind == "competitor":
            return await self.skill_hub_client.call(
                "monitor_competitor",
                {
                    "account_id": context.get("competitor_id") or "demo_competitor",
                    "platform": platform,
                    "user_id": uid,
                },
            )
        if kind == "viz":
            return await self.skill_hub_client.call(
                "visualize_data",
                {
                    "data": context.get("metrics") or {},
                    "chart_type": "line",
                    "title": user_input[:80] or "数据概览",
                    "user_id": uid,
                },
            )
        if kind == "qa":
            return await self.skill_hub_client.call(
                "qa_knowledge",
                {"question": user_input, "user_id": uid},
            )
        if kind == "conversation":
            reply = await self._natural_conversation_reply(user_input, context)
            return {
                "ok": True,
                "result": {
                    "reply": reply,
                    "type": "conversation",
                    "user_id": uid,
                },
            }

        return await self.skill_hub_client.call(
            "retrieve_methodology",
            {
                "query": user_input,
                "industry": context.get("industry") or "",
                "user_id": uid,
            },
        )

    async def _natural_conversation_reply(
        self, user_input: str, context: Dict[str, Any]
    ) -> str:
        """正常对话：有 LLM 时结合简短历史；无 Key 时固定友好话术。"""
        system = (
            "你是 Lumina 智能营销助手，只负责小红书/抖音等内容增长与营销相关话题。\n"
            "若用户问天气、时间、笑话、吃饭等与营销无关的问题：礼貌说明你不处理这类信息，"
            "并一句话引导到营销场景（账号/流量/选题/文案等）。\n"
            "若用户寒暄：自然、简短、亲切（2～4 句），并温和列出你能帮的营销方向。\n"
            "不要输出 JSON 或代码块，除非用户明确要求。"
        )
        history = context.get("session_history") or []
        lines: List[str] = [system, "", "【近期对话摘要】"]
        for h in history[-8:]:
            role, content = h.get("role"), h.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                lines.append(f"{role}: {content.strip()[:2000]}")
        lines.extend(["", f"用户说：{user_input.strip()}", "", "请直接回复："])
        prompt = "\n".join(lines)

        try:
            from llm_hub import get_client

            client = get_client(skill_name="orchestra_chat")
            if client and client.config.api_key:
                return await client.complete(prompt, temperature=0.75, max_tokens=512)
        except Exception:
            pass

        if _is_off_topic_chitchat(user_input):
            return (
                "我主要负责小红书/抖音等内容营销与增长相关的问题，没法回答天气、时间这类生活信息。"
                "你可以说说账号流量、选题、文案或想用的营销方法论，我来帮你。"
            )

        fb = _conversation_fallback_reply(user_input)
        if fb:
            return fb

        return (
            "你好，我是 Lumina 营销助手～可以帮你做账号诊断、选题方向、文案/脚本、内容风险检查等。"
            "直接说说你现在最想解决的一个问题就行。"
        )

    async def process(
        self,
        user_input: str,
        user_id: str,
        session_history: Optional[List[Dict[str, Any]]] = None,
        platform: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session_history = session_history or []
        ctx: Dict[str, Any] = {
            "user_id": user_id,
            "platform": platform or "xiaohongshu",
            "session_history": session_history,
        }
        if extra_context:
            ctx.update(extra_context)

        intent = self._classify_intent(user_input, session_history)
        sop_id = intent.get("sop_id")

        if sop_id:
            sop_out = await self.run_sop(sop_id, ctx)
            from orchestra.nlg import format_sop_summary

            reply = await format_sop_summary(sop_out, user_input)
            return {
                "layer": "orchestra",
                "mode": "sop",
                "intent": intent,
                "sop": sop_out,
                "reply": reply,
            }

        dyn = await self.run_dynamic(user_input, ctx, intent)
        from orchestra.nlg import format_orchestra_reply

        kind = intent.get("kind") or "general"
        reply = await format_orchestra_reply(kind, dyn, user_input)
        return {
            "layer": "orchestra",
            "mode": "dynamic",
            "intent": intent,
            "hub": dyn,
            "reply": reply,
        }
