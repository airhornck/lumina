"""Layer 2：多 Agent 中枢 — 意图路由 + SOP DAG 骨架 + 调用 Skill Hub。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from knowledge_base.methodology_registry import MethodologyRegistry
from knowledge_base.platform_registry import PlatformRegistry
from skill_hub_client import SkillHubClient
from sop_engine import compile_methodology_dag

from orchestra.agent_orchestrator import AgentOrchestrator, ExecutionResult


# ========== 矩阵 Agent Skill 兼容导入 ==========
def _import_matrix_skills():
    """动态导入矩阵 Agent Skills（若未在 sys.path 中则自动添加）。"""
    from pathlib import Path
    import sys

    root = Path(__file__).resolve().parents[3]
    skills_to_path = {
        "skill_matrix_commander": root / "skills" / "skill-matrix-commander" / "src",
        "skill_bulk_creative": root / "skills" / "skill-bulk-creative" / "src",
        "skill_account_keeper": root / "skills" / "skill-account-keeper" / "src",
        "skill_traffic_broker": root / "skills" / "skill-traffic-broker" / "src",
    }
    for p in skills_to_path.values():
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)

    imports = {}
    try:
        from skill_matrix_commander.main import (
            MatrixSetupInput,
            plan_matrix_strategy,
        )
        imports["plan_matrix_strategy"] = (plan_matrix_strategy, MatrixSetupInput)
    except Exception:
        pass
    try:
        from skill_traffic_broker.main import (
            TrafficRouteInput,
            design_traffic_route,
            calculate_traffic_value,
        )
        imports["design_traffic_route"] = (design_traffic_route, TrafficRouteInput)
        imports["calculate_traffic_value"] = (calculate_traffic_value, None)
    except Exception:
        pass
    try:
        from skill_bulk_creative.main import (
            BulkVariationInput,
            generate_variations,
        )
        imports["generate_variations"] = (generate_variations, BulkVariationInput)
    except Exception:
        pass
    try:
        from skill_account_keeper.main import (
            BatchLoginInput,
            batch_login,
            check_account_health_batch,
        )
        imports["batch_login"] = (batch_login, BatchLoginInput)
        imports["check_account_health_batch"] = (check_account_health_batch, None)
    except Exception:
        pass
    return imports


_MATRIX_SKILLS = _import_matrix_skills()


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


# 登录意图匹配
_QR_LOGIN_INTENT = re.compile(
    r"(?:扫码|二维码)?\s*(?:登录|登陆|授权)\s*(抖音|小红书|b站|bilibili|视频号|快手)?|"
    r"(?:我要?|帮我?|想|需要)?\s*(?:登录|登陆|授权)\s*(抖音|小红书|b站|bilibili|视频号|快手)?|"
    r"(?:抖音|小红书|b站|bilibili|视频号|快手)\s*(?:登录|登陆|授权)",
    re.I,
)


def _extract_login_platform(text: str) -> Optional[str]:
    """从登录请求中提取平台名称"""
    t = (text or "").strip()
    if not t:
        return None
    
    platform_mapping = {
        "抖音": "douyin",
        "小红书": "xiaohongshu",
        "b站": "bilibili",
        "bilibili": "bilibili",
        "视频号": "shipinhao",
        "快手": "kuaishou",
    }
    
    for cn_name, en_name in platform_mapping.items():
        if cn_name in t:
            return en_name
    
    return None


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
        self.agent_orchestrator = AgentOrchestrator(skill_hub_client=self.skill_hub_client)

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
        # 检测登录意图（如"登录抖音"、"扫码登录小红书"）
        # 排除批量登录场景（批量登录应由 account_keeper 处理）
        if not re.search(r"批量", t) and _QR_LOGIN_INTENT.search(t):
            return {"kind": "qr_login", "sop_id": None}
        # 检测是否为诊断意图的跟进回复（补充账号信息）
        if _is_diagnosis_followup(t, session_history):
            return {"kind": "diagnosis", "sop_id": None}
        # 矩阵/批量/导流相关意图优先于单账号 traffic/script/diagnosis
        if re.search(r"矩阵.*(流量|导流|互导)|流量.*互导|设计.*导流.*路径|主号.*卫星号.*导流", t):
            return {"kind": "general", "sop_id": None}
        if re.search(r"一稿多改|改写.*多平台|改写成适合.*平台.*版本|适配.*平台", t):
            return {"kind": "content", "sop_id": None}
        if re.search(r"批量.*检查.*健康|检查.*所有账号.*健康|所有账号.*健康.*检查", t):
            return {"kind": "general", "sop_id": None}
        if re.search(r"计算.*(流量|互导).*价值|估算.*(流量|互导).*价值", t):
            return {"kind": "general", "sop_id": None}
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
        # 先判 cases（避免"爆款数据"被后面的"数据"规则拦截为 traffic）
        if re.search(r"案例|对标|拆解|爆款.*模式|可复用|归因|爆款.*数据", t):
            return {"kind": "cases", "sop_id": None}
        if re.search(r"竞品.*数据|数据.*竞品|抓取.*数据", t):
            return {"kind": "competitor", "sop_id": None}
        if re.search(r"数据|指标", t):
            return {"kind": "traffic", "sop_id": None}
        if re.search(r"风险|违规|审核|限流|封号|屏蔽|下架", t):
            return {"kind": "risk", "sop_id": None}
        if re.search(r"方法论|SOP|步骤|框架|模型", t):
            return {"kind": "methodology", "sop_id": "aida_advanced"}
        # A/B测试、投放相关优先于 content
        if re.search(r"A/B|对照组|实验组", t):
            return {"kind": "traffic", "sop_id": None}
        if re.search(r"文案|生成.*(标题|正文)|标题|笔记|撰写|推文|推广.*文案|种草.*文案", t) and not re.search(r"选题|日历", t):
            return {"kind": "content", "sop_id": None}
        if re.search(r"脚本|分镜|口播|拍摄", t):
            return {"kind": "script", "sop_id": None}
        if re.search(r"视频", t) and not re.search(r"拆解|分析|爆款|对标", t):
            return {"kind": "script", "sop_id": None}
        if re.search(r"选题|日历|热点|定位|人设|赛道|方向选择|IP打造|怎么做账号|账号怎么|生成.*选题|生成.*日历", t):
            return {"kind": "topic", "sop_id": None}
        if re.search(r"新闻|资讯|行业", t):
            return {"kind": "news", "sop_id": None}
        if re.search(r"竞品|对手|抓取.*账号|抓取.*数据", t):
            return {"kind": "competitor", "sop_id": None}
        if re.search(r"图表|可视化", t):
            return {"kind": "viz", "sop_id": None}
        if re.search(r"知识库|问答|什么是|为什么.*流量|怎么做.*账号", t):
            return {"kind": "qa", "sop_id": None}
        if re.search(r"矩阵|多账号.*规划|批量.*管理|主号|卫星号|协同", t):
            return {"kind": "general", "sop_id": None}
        if re.search(r"评论|回复粉丝|私域|社群|粉丝分层|粉丝画像|互动回复", t):
            return {"kind": "general", "sop_id": None}
        if re.search(r"投放|广告|千川|本地推|推广策略|竞价|ROI", t):
            return {"kind": "traffic", "sop_id": None}
        if re.search(r"账号.*健康|健康.*账号|批量.*检查|检查.*批量|封号|限流.*检查", t):
            return {"kind": "diagnosis", "sop_id": None}
        # 默认不再落到「general→方法论检索」，避免天气/闲聊等被误匹配 AIDA
        if _METHODOLOGY_BROWSE.search(t):
            return {"kind": "general", "sop_id": None}
        return {"kind": "conversation", "sop_id": None}

    async def _resolve_matrix_intent(
        self, user_input: str, platform: str, uid: str
    ) -> Optional[Dict[str, Any]]:
        """
        检测 general 意图下的矩阵/批量/导流诉求，并调用对应的矩阵 Agent Skill。
        若未匹配到矩阵意图，返回 None，由上层继续 fallback。
        """
        t = (user_input or "").strip()
        if not _MATRIX_SKILLS:
            return None

        def _wrap(result, agents):
            data = result.model_dump() if hasattr(result, "model_dump") else dict(result) if result else {}
            data["agent_calls"] = agents
            return {"ok": True, "result": data}

        # 1. 矩阵规划
        if re.search(r"矩阵.*规划|帮我规划.*矩阵|账号矩阵|主号.*卫星号.*规划|矩阵.*搭建", t):
            fn, InCls = _MATRIX_SKILLS.get("plan_matrix_strategy", (None, None))
            if fn and InCls:
                niches = {
                    "职场": "职场发展", "穿搭": "时尚穿搭", "美食": "美食探店",
                    "美妆": "美妆护肤", "健身": "健身运动", "家居": "家居生活",
                    "母婴": "母婴育儿", "数码": "数码科技", "汽车": "汽车",
                    "旅行": "旅行", "火锅": "美食餐饮",
                }
                niche = "general"
                for k, v in niches.items():
                    if k in t:
                        niche = v
                        break
                target_platforms = [platform]
                for cn, en in {
                    "抖音": "douyin", "小红书": "xiaohongshu",
                    "B站": "bilibili", "bilibili": "bilibili",
                    "视频号": "shipinhao", "快手": "kuaishou",
                }.items():
                    if cn in t and en not in target_platforms:
                        target_platforms.append(en)
                result = await fn(
                    InCls(
                        master_account="master",
                        niche=niche,
                        target_platforms=target_platforms,
                        satellite_count=5,
                        budget_level="medium",
                        user_id=uid,
                    )
                )
                return _wrap(result, ["matrix_commander"])

        # 2. 流量互导路径设计
        if re.search(r"导流.*路径|流量.*互导|从.*导流到.*|主号.*卫星号.*导流|设计.*导流", t):
            fn, InCls = _MATRIX_SKILLS.get("design_traffic_route", (None, None))
            if fn and InCls:
                src = "source_main"
                tgt = "target_sat"
                route_method = "comment"
                for cn, en in {
                    "抖音": "douyin", "小红书": "xiaohongshu",
                    "B站": "bilibili", "bilibili": "bilibili",
                }.items():
                    if cn in t:
                        if "主号" in t or "抖音" in t:
                            src = f"{en}_main"
                        else:
                            tgt = f"{en}_sat"
                result = await fn(
                    InCls(
                        source_account=src,
                        target_account=tgt,
                        content_id="content_001",
                        route_method=route_method,
                        user_id=uid,
                    )
                )
                return _wrap(result, ["matrix_commander", "traffic_broker"])

        # 3. 一稿多改 / 跨平台适配
        if re.search(r"一稿多改|改写.*多平台|抖音.*小红书.*B站.*版本|适配.*平台|改写成适合.*平台", t):
            fn, InCls = _MATRIX_SKILLS.get("generate_variations", (None, None))
            if fn and InCls:
                platforms_found = []
                for cn, en in {
                    "抖音": "douyin", "小红书": "xiaohongshu",
                    "B站": "bilibili", "bilibili": "bilibili",
                }.items():
                    if cn in t and en not in platforms_found:
                        platforms_found.append(en)
                if not platforms_found:
                    platforms_found = [platform]
                target_accounts = []
                niche = "general"
                for k in ["职场", "穿搭", "美食", "美妆", "健身"]:
                    if k in t:
                        niche = k
                        break
                for i, pf in enumerate(platforms_found):
                    target_accounts.append({
                        "type": ["细分领域", "场景化", "地域化"][i % 3],
                        "niche": f"{niche}_{pf}",
                        "platform": pf,
                    })
                result = await fn(
                    InCls(
                        master_content={"text": t, "type": "script"},
                        target_accounts=target_accounts,
                        variation_strategy="auto",
                        user_id=uid,
                    )
                )
                return _wrap(result, ["bulk_creative", "creative_studio"])

        # 4. 批量登录
        if re.search(r"批量登录.*账号|登录.*多个账号", t):
            fn, InCls = _MATRIX_SKILLS.get("batch_login", (None, None))
            if fn and InCls:
                pf = platform
                for cn, en in {"抖音": "douyin", "小红书": "xiaohongshu"}.items():
                    if cn in t:
                        pf = en
                        break
                accounts = [
                    {"id": f"account_{i+1}", "platform": pf, "credentials": {}}
                    for i in range(3)
                ]
                result = await fn(
                    InCls(
                        accounts=accounts,
                        platforms=[pf],
                        use_proxy=True,
                        headless=True,
                        user_id=uid,
                    )
                )
                return _wrap(result, ["account_keeper"])

        # 5. 批量健康检查
        if re.search(r"批量.*检查.*健康|检查.*所有账号.*健康|所有账号.*健康.*检查|账号.*健康.*批量", t):
            fn, _ = _MATRIX_SKILLS.get("check_account_health_batch", (None, None))
            if fn:
                pf = platform
                for cn, en in {"抖音": "douyin", "小红书": "xiaohongshu"}.items():
                    if cn in t:
                        pf = en
                        break
                account_ids = [f"account_{i+1}" for i in range(5)]
                result = await fn(account_ids=account_ids, platforms=[pf], user_id=uid)
                return _wrap(result, ["account_keeper"])

        # 6. 流量价值计算
        if re.search(r"计算.*(流量|互导).*价值|估算.*(流量|互导).*价值", t):
            fn, _ = _MATRIX_SKILLS.get("calculate_traffic_value", (None, None))
            if fn:
                result = await fn(
                    matrix_data={
                        "accounts": [
                            {"followers": 5000, "engagement": 300},
                            {"followers": 3000, "engagement": 200},
                            {"followers": 2000, "engagement": 150},
                        ]
                    },
                    user_id=uid,
                )
                return _wrap(result, ["traffic_broker"])

        return None

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
        import inspect

        platform = context.get("platform") or "xiaohongshu"
        dag = compile_methodology_dag(
            sop_id,
            platform,
            methodology_lib=self.methodology_lib,
            platform_lib=self.platform_lib,
        )
        results: Dict[str, Any] = {}
        ok_count = 0
        fail_count = 0
        partial_results: List[Dict[str, Any]] = []
        for node in dag:
            skill = node.get("skill")
            params = dict(node.get("params") or {})
            params.setdefault("user_id", context.get("user_id") or "anonymous")
            params.setdefault("platform", platform)
            nid = node.get("id") or skill

            # 参数过滤：只保留 Skill 函数签名中实际存在的参数，避免 compile_methodology_dag
            # 注入的 methodology_prompt_template / methodology_id 等导致 TypeError
            fn = self.skill_hub_client._registry.get(skill or "")
            if fn:
                sig = inspect.signature(fn)
                allowed = set(sig.parameters.keys())
                has_kwargs = any(
                    p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in sig.parameters.values()
                )
                if not has_kwargs:
                    params = {k: v for k, v in params.items() if k in allowed}

            out = await self.skill_hub_client.call(skill or "", params)
            results[nid] = out
            if out.get("ok"):
                ok_count += 1
                partial_results.append({"step": nid, "result": out.get("result")})
            else:
                fail_count += 1
        return {
            "dag": dag,
            "node_results": results,
            "ok_count": ok_count,
            "fail_count": fail_count,
            "partial_results": partial_results,
        }

    def _should_use_agent_team(self, kind: str, context: Dict[str, Any]) -> bool:
        """判断当前意图是否适合走 AgentTeam 多 Agent 协作
        
        只有在具备必要上下文时才走 AgentTeam，否则 fallback 到原有路径
        返回 clarification 引导用户补充信息。
        """
        if kind == "diagnosis":
            # 有账号信息时才走多 Agent 协作诊断
            return bool(context.get("account_url") or context.get("cookies"))
        if kind == "traffic":
            # 有真实数据时才走多 Agent 协作分析
            return _context_has_user_metrics(context)
        return kind in {"content", "script", "topic", "risk"}
    
    async def _run_agent_team(
        self,
        user_input: str,
        context: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        """通过 AgentOrchestrator 组建并执行 AgentTeam"""
        kind = intent.get("kind", "general")
        
        # MarketingOrchestra kind → AgentOrchestrator intent_key 映射
        kind_to_intent = {
            "diagnosis": "diagnosis",
            "traffic": "traffic_analysis",
            "content": "content_creation",
            "script": "script_creation",
            "topic": "topic_selection",
            "risk": "risk_check",
        }
        intent_key = kind_to_intent.get(kind, kind)
        
        # 组建 AgentTeam
        team = self.agent_orchestrator.orchestrate(
            intent_type=intent_key,
            intent_subtype=None,
            user_id=context.get("user_id", "anonymous"),
            context=context,
        )
        
        if not team.agents:
            return {"ok": False, "error": f"no_agents_for_intent:{kind}"}
        
        # 执行 AgentTeam
        result = await self.agent_orchestrator.execute_team(
            team=team,
            user_input=user_input,
            context=context,
        )
        
        # 提取主结果（兼容原有 API 契约）
        # 对于并行模式，取第一个成功的 Agent 的核心 result
        # 对于串行模式，取最后一个 Agent 的核心 result
        primary_result: Dict[str, Any] = {}
        for agent_id, output in result.agent_outputs.items():
            if isinstance(output, dict) and "results" in output:
                for skill_id, skill_res in output["results"].items():
                    if isinstance(skill_res, dict) and skill_res.get("ok") and skill_res.get("result"):
                        primary_result = dict(skill_res["result"])
                        break
        
        # 将聚合结果合并到主结果中，避免破坏原有字段
        merged_result = dict(result.results)
        if primary_result:
            # 主结果字段优先，聚合结果作为补充
            for k, v in primary_result.items():
                if k not in merged_result:
                    merged_result[k] = v
        
        return {
            "ok": result.success,
            "result": merged_result,
            "agent_outputs": result.agent_outputs,
            "errors": result.errors,
            "execution_time_ms": result.execution_time_ms,
            "agent_team": {
                "mode": team.mode.value,
                "agents": [a.id for a in team.agents],
            },
        }

    async def run_dynamic(
        self,
        user_input: str,
        context: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        uid = context.get("user_id") or "anonymous"
        platform = context.get("platform") or "xiaohongshu"
        kind = intent.get("kind")

        # ===== 新增：多 Agent 协作路径 =====
        if self._should_use_agent_team(kind, context):
            return await self._run_agent_team(user_input, context, intent)
        # ==================================

        # 矩阵/批量/导流意图优先于常规分类（避免被 traffic/script/diagnosis 等误拦截）
        matrix_result = await self._resolve_matrix_intent(user_input, platform, uid)
        if matrix_result is not None:
            return matrix_result

        if kind == "qr_login":
            platform = _extract_login_platform(user_input) or platform
            return await self._request_qr_code_login(platform, uid)

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
            
            print(f"[diagnosis] 初始URL: {url}, 用户输入: {user_input[:50]}...")
            
            # 检查是否已有保存的登录凭证
            if platform:
                try:
                    from rpa.qrcode_login import get_qr_login_manager
                    manager = get_qr_login_manager()
                    cred = await manager.get_user_credential(uid, platform)
                    
                    if cred:
                        print(f"[diagnosis] 找到已保存的登录凭证: {cred.account_name}")
                        # 已有凭证，直接进行诊断
                        return await self._do_diagnosis(
                            url=url,
                            platform=platform,
                            uid=uid,
                            account_name=extracted_account,
                            cookies=cred.cookies,
                        )
                    else:
                        print(f"[diagnosis] 未找到 {platform} 的登录凭证")
                except Exception as e:
                    print(f"[diagnosis] 检查凭证失败: {e}")
            
            # 如果 context 中没有有效的 account_url，尝试从用户输入中提取
            if _is_demo_account_url(url):
                print("[diagnosis] URL为空或无效，尝试从输入提取账号信息")
                extracted_platform, extracted_account = self._extract_account_info_from_input(user_input)
                print(f"[diagnosis] 提取结果: platform={extracted_platform}, account={extracted_account}")
                if extracted_platform and extracted_account:
                    url = f"https://{extracted_platform}/{extracted_account}"
                    platform = extracted_platform
            
            if _is_demo_account_url(url):
                # 没有URL，也没有登录凭证，先引导补充信息
                # 只有用户明确 prefer_qr_login 时才直接跳转二维码登录
                if platform and context.get("prefer_qr_login"):
                    return await self._request_qr_code_login(platform, uid)

                return {
                    "ok": True,
                    "result": {
                        "type": "clarification",
                        "reason": "no_account_url",
                        "missing": ["account_url", "platform"],
                        "reply": (
                            "要做**账号诊断**，需要先锁定是哪个账号：请发 **主页链接**，"
                            "或说明 **平台 + 可搜索到的昵称**。\n\n"
                            "您也可以：发送「登录抖音」或「登录小红书」，"
                            "我会提供二维码让您扫码登录，之后就能自动获取您的账号数据。"
                        ),
                    },
                }
            
            # 如果提取了新的平台信息，使用它
            if extracted_platform:
                platform = extracted_platform
            
            return await self._do_diagnosis(
                url=url,
                platform=platform,
                uid=uid,
                account_name=extracted_account,
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
        if kind == "general" and re.search(r"评论|回复|粉丝|社群|私域|互动|分层|画像", user_input):
            return {
                "ok": True,
                "result": {
                    "type": "community_guide",
                    "reply": (
                        "关于社群互动，这里有几个实用建议：\n"
                        "1）及时回复评论能显著提升账号活跃度和粉丝粘性；\n"
                        "2）对购买类评论（如'哪里买'），可引导到置顶链接或私信；\n"
                        "3）粉丝分层可按活跃度（潜水/互动/转化）制定不同触达策略。\n"
                        "如果你有具体的评论内容或粉丝数据，我可以帮你写更精准的回复或分层方案。"
                    ),
                },
            }

        if kind == "conversation":
            reply = await self._natural_conversation_reply(user_input, context, uid)
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

    async def _request_qr_code_login(self, platform: str, uid: str) -> Dict[str, Any]:
        """
        请求二维码登录
        
        生成二维码并返回给前端展示
        """
        try:
            from rpa.qrcode_login import get_qr_login_manager
            
            manager = get_qr_login_manager()
            result = await manager.check_and_refresh_login(uid, platform)
            
            if result["type"] == "already_logged_in":
                # 已有登录，直接诊断
                return await self._do_diagnosis(
                    url="",
                    platform=platform,
                    uid=uid,
                    account_name="",
                    cookies=result["credential"]["cookies"],
                )
            
            # 需要扫码登录
            session = result["session"]
            
            return {
                "ok": True,
                "result": {
                    "type": "qr_code_login",
                    "platform": platform,
                    "session_id": session["session_id"],
                    "qr_code_base64": session["qr_code"],
                    "expires_in": session["expires_in"],
                    "reply": f"请使用 {platform} APP 扫描下方二维码登录，登录后我就能获取您的账号数据进行诊断分析。",
                    "instructions": [
                        f"1. 打开 {platform} APP",
                        "2. 点击右上角扫一扫",
                        "3. 扫描下方二维码",
                        "4. 在手机上确认登录",
                    ],
                    "waiting_for": "login",
                },
            }
            
        except Exception as e:
            print(f"[_request_qr_code_login] 失败: {e}")
            # 失败时返回普通提示
            return {
                "ok": True,
                "result": {
                    "type": "clarification",
                    "reason": "login_failed",
                    "reply": f"登录 {platform} 失败，请直接提供您的账号主页链接进行分析。",
                },
            }

    async def _do_diagnosis(
        self,
        url: str,
        platform: str,
        uid: str,
        account_name: Optional[str] = None,
        cookies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        执行账号诊断
        
        如果有 cookies，使用 cookies 进行认证诊断
        如果需要登录，返回引导用户登录的响应
        """
        diagnose_params = {
            "account_url": url,
            "platform": platform,
            "user_id": uid,
            "account_name": account_name,
        }
        
        # 如果有 cookies，添加到参数中
        if cookies:
            diagnose_params["cookies"] = cookies
        
        result = await self.skill_hub_client.call(
            "diagnose_account",
            diagnose_params,
        )
        
        # 检查结果是否需要登录
        if isinstance(result, dict):
            result_data = result.get("result", result)
            if result_data.get("login_required") or result_data.get("data_source") == "login_required":
                # 需要登录，返回引导用户登录的响应
                return {
                    "ok": True,
                    "result": {
                        "type": "diagnosis",
                        "login_required": True,
                        "platform": platform,
                        **result_data,
                    },
                }
        
        return result

    async def _natural_conversation_reply(
        self, user_input: str, context: Dict[str, Any], user_id: str = ""
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
                return await client.complete(
                    prompt,
                    temperature=0.75,
                    max_tokens=512,
                    _usage_meta={"user_id": user_id, "skill_name": "orchestra_chat"} if user_id else None,
                )
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
        reply = await format_orchestra_reply(kind, dyn, user_input, user_id)
        
        # 判断是否走了 AgentTeam 路径
        is_agent_team = dyn.get("agent_team") is not None
        
        return {
            "layer": "orchestra",
            "mode": "agent_team" if is_agent_team else "dynamic",
            "intent": intent,
            "hub": dyn,
            "reply": reply,
            "agent_team": dyn.get("agent_team") if is_agent_team else None,
        }
