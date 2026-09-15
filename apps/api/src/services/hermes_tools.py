"""将 Lumina Skill 包装为 Hermes 工具。"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, Field
from services.hermes_markdown_skill import (
    ExecuteMethodologyInput,
    handle_lumina_execute_methodology,
)
from orchestra.skills import content_ranking_skill, positioning_matrix_skill, weekly_snapshot_skill

logger = logging.getLogger(__name__)

# 关键词直连触发（planner 之外的确定性入口）：命中即跳过 LLM 决策，
# 由 hermes_adapter 直接调用对应 skill。与旧链路关键词路由的本质区别：
# 用户原话作为 message 参数原样传入、平台上下文透传、回复照常写入记忆——
# 只确定“调哪个 skill”，不裁剪任何上下文。
KEYWORD_TOOL_TRIGGERS: List[Tuple[str, str]] = [
    ("查爆款榜单", "lumina_content_ranking"),
    ("内容定位矩阵", "lumina_positioning_matrix"),
    ("生成本周快报", "lumina_weekly_snapshot"),
]


def match_keyword_tool(message: str) -> str | None:
    """命中关键词时返回对应工具名，否则 None。"""
    for keyword, tool_name in KEYWORD_TOOL_TRIGGERS:
        if keyword in message:
            return tool_name
    return None

# 每轮对话的请求上下文（由 hermes_adapter 在 run_conversation 前设置，
# 工具 handler 与 run_conversation 同线程执行，threading.local 安全）
_request_ctx = threading.local()


def set_request_context(user_id: str, conversation_id: str, platform: str | None = None, user_message: str | None = None) -> None:
    _request_ctx.user_id = user_id
    _request_ctx.conversation_id = conversation_id
    _request_ctx.platform = platform
    _request_ctx.last_user_message = user_message


def _current_user_id() -> str:
    return getattr(_request_ctx, "user_id", None) or "anonymous"


def _current_conversation_id() -> str:
    return getattr(_request_ctx, "conversation_id", None) or ""


def _current_platform() -> str | None:
    """获取当前请求已解析的平台（由 hermes_adapter 在 run_conversation 前设置）。"""
    return getattr(_request_ctx, "platform", None)


class GenerateContentInput(BaseModel):
    topic: str = Field(..., description="内容主题或产品")
    platform: str = Field(
        ...,
        description="目标平台",
        examples=["xiaohongshu", "bilibili", "douyin", "wechat_official"],
    )
    style: str | None = Field(default=None, description="风格")
    target_audience: str | None = Field(default=None, description="目标人群")
    content_goal: str | None = Field(default=None, description="内容目标")


class DiagnoseAccountInput(BaseModel):
    platform: str = Field(..., description="平台：用户说抖音=douyin，小红书=xiaohongshu，必须从对话上下文抽取")
    account_url: str | None = Field(default=None, description="账号主页链接（无则可给 account_name）")
    account_name: str | None = Field(default=None, description="账号名称（用于搜索定位账号）")


class AnalyzeTrafficInput(BaseModel):
    metrics: Dict[str, Any] = Field(..., description="流量指标，如 {views, likes, shares}")
    platform: str = Field(..., description="平台：douyin/xiaohongshu，从对话上下文抽取")
    time_range: str = Field(default="7d", description="统计周期，如 7d/30d")


class DetectRiskInput(BaseModel):
    content_text: str = Field(..., description="待检测内容")
    platform: str = Field(..., description="平台：douyin/xiaohongshu，从对话上下文抽取")


class RecommendTopicsInput(BaseModel):
    platform: str = Field(..., description="平台：用户说抖音=douyin，小红书=xiaohongshu，必须从对话上下文抽取")
    niche: str | None = Field(default=None, description="领域/赛道，如 美妆/职场/美食")
    brief: str | None = Field(
        default=None,
        description="用户背景简述（年龄/身份/目标人群/诉求），从对话上下文总结，如「22岁个人创作者，目标受众年轻人」",
    )


class ContentRankingInput(BaseModel):
    message: str = Field(..., description="用户请求内容方向榜单的问题")
    platform: str | None = Field(default=None, description="平台")


class PositioningMatrixInput(BaseModel):
    message: str = Field(..., description="用户请求定位矩阵的问题")
    platform: str | None = Field(default=None, description="平台")
    mode: str | None = Field(default=None, description="子模式：case 或 matrix")


class WeeklySnapshotInput(BaseModel):
    message: str = Field(..., description="用户请求每周决策快照的问题")
    platform: str | None = Field(default=None, description="平台")


LUMINA_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lumina_generate_content",
            "description": "生成小红书/抖音等平台适配的营销文案并产出可访问的内容页面 URL。当用户要求写笔记/文案/脚本/种草内容时必须调用本工具，不要直接凭空写全文。",
            "parameters": GenerateContentInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lumina_diagnose_account",
            "description": "对小红书/抖音等账号进行诊断分析（粉丝画像/内容表现/优化建议）。当用户要求诊断/分析自己或他人的账号时调用；缺少账号链接或名称时先向用户索取。",
            "parameters": DiagnoseAccountInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lumina_analyze_traffic",
            "description": "分析账号流量数据（曝光/互动/转化漏斗）并给出优化建议。当用户提供具体流量数据（播放量/点赞/分享等）并要求分析时调用。",
            "parameters": AnalyzeTrafficInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lumina_detect_risk",
            "description": "检测内容是否存在违规风险（敏感词/极限词/平台规则）。当用户要求检查文案是否违规、是否能过审时调用。",
            "parameters": DetectRiskInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lumina_recommend_topics",
            "description": "推荐热点选题：结合行业动态、营销方法论（AIDA/PAS等）与内容日历生成选题推荐。当用户要求选题/方向/热点/内容规划推荐时必须调用本工具获取结构化推荐，不要仅凭经验直接回答。",
            "parameters": RecommendTopicsInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lumina_execute_methodology",
            "description": "执行 Lumina 营销方法论（定位、钩子故事Offer、AIDA、PAS）",
            "parameters": ExecuteMethodologyInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lumina_content_ranking",
            "description": "生成内容方向榜单，帮助用户梳理、排序、对比可选的内容方向",
            "parameters": ContentRankingInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lumina_positioning_matrix",
            "description": "生成定位矩阵或定位决策案例库，帮助用户梳理内容定位",
            "parameters": PositioningMatrixInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lumina_weekly_snapshot",
            "description": "整理每周决策快照，汇总本周内容/增长决策",
            "parameters": WeeklySnapshotInput.model_json_schema(),
        },
    },
]


def get_lumina_tools() -> List[Dict[str, Any]]:
    """获取所有 Lumina 工具定义。"""
    return list(LUMINA_TOOLS)


async def handle_lumina_generate_content(
    args: Dict[str, Any],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """处理内容生成工具调用。

    Args:
        args: 工具参数。
        user_id: 用户唯一标识；优先于 threading.local() 中的上下文。
        conversation_id: 会话唯一标识；优先于 threading.local() 中的上下文。
    """
    try:
        input_data = GenerateContentInput(**args)
        from services.content_engine.cross_platform_engine import CrossPlatformEngine

        engine = CrossPlatformEngine()
        result = await engine.generate_sync(
            user_id=user_id or _current_user_id(),
            conversation_id=conversation_id or _current_conversation_id(),
            message=input_data.topic,
            target_platforms=[input_data.platform],
            context={
                "platform": input_data.platform,
                "style": input_data.style,
                "target_audience": input_data.target_audience,
                "content_goal": input_data.content_goal,
            },
            session_history=[],
            request_id=uuid.uuid4().hex[:12],
        )
        payload = result.__dict__
        return json.dumps(
            {
                "ok": True,
                "result": payload,
                # 顶层业务数据：adapter 从 tool_complete 结果中提取后发
                # export_link / compliance_report SSE 事件（spec §4.4）
                "export_urls": payload.get("export_urls", []),
                "compliance": payload.get("compliance", {}),
            },
            ensure_ascii=False,
            default=str,
        )
    except Exception as e:
        logger.exception("lumina_generate_content failed: %s", e)
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


async def _call_skill_hub(skill: str, params: Dict[str, Any]) -> Dict[str, Any]:
    from skill_hub_client.client import SkillHubClient

    return await SkillHubClient().call(skill, params)


async def handle_lumina_diagnose_account(
    args: Dict[str, Any],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """处理账号诊断工具调用（无凭证时 skill 层返回结构化引导，不伪造数据）。"""
    try:
        input_data = DiagnoseAccountInput(**args)
        resp = await _call_skill_hub(
            "diagnose_account",
            {
                "account_url": input_data.account_url or "",
                "platform": input_data.platform,
                "user_id": user_id or _current_user_id(),
                "account_name": input_data.account_name,
            },
        )
        return json.dumps(resp, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning("lumina_diagnose_account failed: %s", e)
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


async def handle_lumina_analyze_traffic(
    args: Dict[str, Any],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """处理流量分析工具调用。"""
    try:
        input_data = AnalyzeTrafficInput(**args)
        resp = await _call_skill_hub(
            "analyze_traffic",
            {
                "metrics": input_data.metrics,
                "user_id": user_id or _current_user_id(),
                "platform": input_data.platform,
                "time_range": input_data.time_range,
            },
        )
        return json.dumps(resp, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning("lumina_analyze_traffic failed: %s", e)
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


async def handle_lumina_detect_risk(
    args: Dict[str, Any],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """处理合规检测工具调用（结果映射为 compliance，供 adapter 发 compliance_report）。"""
    try:
        input_data = DetectRiskInput(**args)
        resp = await _call_skill_hub(
            "detect_risk",
            {
                "content_text": input_data.content_text,
                "platform": input_data.platform,
            },
        )
        result = resp.get("result", {}) if isinstance(resp, dict) else {}
        compliance = {
            "risk_level": result.get("risk_level", "low"),
            "risk_categories": result.get("risk_categories", ["none"]),
            "violations": result.get("flagged_terms", []),
            "suggestion": "；".join(result.get("suggestions", [])),
            "report_md": "",
        }
        return json.dumps(
            {"ok": resp.get("ok", True), "result": result, "compliance": compliance},
            ensure_ascii=False,
            default=str,
        )
    except Exception as e:
        logger.warning("lumina_detect_risk failed: %s", e)
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


async def handle_lumina_recommend_topics(
    args: Dict[str, Any],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """处理选题推荐工具调用（brief/platform 由 LLM 从对话上下文抽取）。"""
    try:
        input_data = RecommendTopicsInput(**args)
        resp = await _call_skill_hub(
            "select_topic",
            {
                "industry": input_data.niche or "general",
                "user_id": user_id or _current_user_id(),
                "platform": input_data.platform,
                "brief": input_data.brief,
            },
        )
        return json.dumps(resp, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning("lumina_recommend_topics failed: %s", e)
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


async def handle_lumina_content_ranking(
    args: Dict[str, Any],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """处理内容方向榜单工具调用。"""
    try:
        input_data = ContentRankingInput(**args)
        result = await content_ranking_skill.run(
            message=input_data.message,
            platform=input_data.platform,
            context={},
            history=[],
        )
        return json.dumps({"ok": True, "result": {"reply": result}})
    except Exception as e:
        logger.warning("lumina_content_ranking failed: %s", e)
        return json.dumps({"ok": False, "error": str(e)})


async def handle_lumina_positioning_matrix(
    args: Dict[str, Any],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """处理定位矩阵工具调用。"""
    try:
        input_data = PositioningMatrixInput(**args)
        result = await positioning_matrix_skill.run(
            message=input_data.message,
            platform=input_data.platform,
            context={},
            history=[],
            mode=input_data.mode,
        )
        return json.dumps({"ok": True, "result": {"reply": result}})
    except Exception as e:
        logger.warning("lumina_positioning_matrix failed: %s", e)
        return json.dumps({"ok": False, "error": str(e)})


async def handle_lumina_weekly_snapshot(
    args: Dict[str, Any],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """处理每周决策快照工具调用。"""
    try:
        input_data = WeeklySnapshotInput(**args)
        result = await weekly_snapshot_skill.run(
            message=input_data.message,
            platform=input_data.platform,
            context={},
            history=[],
        )
        return json.dumps({"ok": True, "result": {"reply": result}})
    except Exception as e:
        logger.warning("lumina_weekly_snapshot failed: %s", e)
        return json.dumps({"ok": False, "error": str(e)})


_TOOL_HANDLERS = {
    "lumina_generate_content": handle_lumina_generate_content,
    "lumina_diagnose_account": handle_lumina_diagnose_account,
    "lumina_analyze_traffic": handle_lumina_analyze_traffic,
    "lumina_detect_risk": handle_lumina_detect_risk,
    "lumina_recommend_topics": handle_lumina_recommend_topics,
    "lumina_execute_methodology": handle_lumina_execute_methodology,
    "lumina_content_ranking": handle_lumina_content_ranking,
    "lumina_positioning_matrix": handle_lumina_positioning_matrix,
    "lumina_weekly_snapshot": handle_lumina_weekly_snapshot,
}


async def handle_tool_call(
    tool_name: str,
    args: Dict[str, Any],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
    platform: str | None = None,
    user_message: str | None = None,
) -> str:
    """分发 Hermes 工具调用。

    阶段二 P0-10 / 阶段三 P1-1：
    在调用工具前，如果调用方显式传入了已解析的平台，且 args 中的 platform
    与已解析平台不一致，自动统一为已解析平台（除非是多平台对比场景）。

    注意：Hermes 会并发调用多个工具，这些调用都在同一个主事件循环线程中执行。
    为避免 threading.local() 的请求上下文在并发协程间互相覆盖，本函数优先使用
    调用方显式传入的 user_id/conversation_id/platform，并把它们透传给 handler。
    """
    # 尽量使用显式传入的上下文；未传入时回退到 threading.local()（兼容旧路径）
    effective_user_id: str = (
        user_id or getattr(_request_ctx, "user_id", None) or "anonymous"
    )
    effective_conversation_id: str = (
        conversation_id or getattr(_request_ctx, "conversation_id", None) or ""
    )
    effective_platform = platform if platform is not None else _current_platform()
    effective_user_message = user_message or getattr(
        _request_ctx, "last_user_message", None
    )

    # 同步设置线程局部上下文，供尚未改造的内部函数临时使用
    set_request_context(
        effective_user_id,
        effective_conversation_id,
        effective_platform,
        effective_user_message,
    )

    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return json.dumps({"ok": False, "error": f"Unknown tool: {tool_name}"})

    # 平台一致性校验：已解析平台优先于 LLM 传入的平台
    if isinstance(args, dict) and "platform" in args:
        from services.platform_utils import normalize_platform, detect_multi_platform_intent

        raw_platform = args.get("platform")
        normalized = normalize_platform(raw_platform)
        is_multi_platform = detect_multi_platform_intent(effective_user_message or "")

        if effective_platform and not is_multi_platform:
            # 已解析出单平台：把 LLM 传入的平台归一化为英文 ID，
            # 若归一化失败则强制回退到已解析平台。
            target_platform = normalized or effective_platform
            if target_platform != effective_platform and not is_multi_platform:
                target_platform = effective_platform
                logger.info(
                    "Platform aligned for tool=%s: %s -> %s (resolved=%s)",
                    tool_name, raw_platform, effective_platform, effective_platform,
                )
            if target_platform != raw_platform:
                args = dict(args)
                args["platform"] = target_platform
        elif normalized:
            # 未解析出 effective_platform 但 LLM 传了可识别别名：统一归一化
            if normalized != raw_platform:
                args = dict(args)
                args["platform"] = normalized

    return await handler(
        args,
        user_id=effective_user_id,
        conversation_id=effective_conversation_id,
    )
