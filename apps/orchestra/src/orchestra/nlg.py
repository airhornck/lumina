"""编排层 NLG：把 Skill 结构化结果转成用户可读说明（保留 hub 原始数据）。"""

from __future__ import annotations

import json
from typing import Any, Dict


def _truncate(s: str, n: int = 7000) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


async def format_sop_summary(sop_out: Dict[str, Any], user_input: str) -> str:
    """SOP 模式：简要说明执行到哪一步，失败时给出原因。"""
    dag = sop_out.get("dag") or []
    nodes = sop_out.get("node_results") or {}
    ok_count = sop_out.get("ok_count", 0)
    fail_count = sop_out.get("fail_count", 0)
    if not dag:
        return "已尝试执行 SOP，但未生成执行步骤（请检查方法论 YAML 是否存在）。"
    lines = [
        f"**进度**：已按方法论 SOP 顺序跑完 **{len(dag)}** 个节点。",
        f"（你的输入摘要：{(user_input or '')[:120]}）",
        "",
        "**各步状态**：",
    ]
    for step in dag:
        sid = step.get("id") or "?"
        sk = step.get("skill") or "?"
        raw = nodes.get(sid) or {}
        ok = raw.get("ok")
        if ok:
            lines.append(f"- `{sid}` → 工具 `{sk}`：✓ 已返回")
        else:
            err = raw.get("error", "未知错误")[:100]
            lines.append(f"- `{sid}` → 工具 `{sk}`：✗ 未完成（原因：{err}）")
    lines.append("")
    if ok_count > 0 and fail_count > 0:
        lines.append(
            f"其中 **{ok_count}** 个步骤已完成，**{fail_count}** 个步骤因缺少数据或配置未完成。"
            "你可以补充信息后重试，或说「跳过未完成步骤直接总结」。"
        )
    elif fail_count > 0:
        lines.append(
            "所有步骤均未能完成，常见原因是缺少 LLM 配置或所需数据（如账号链接、metrics）。"
            "请检查配置或补充信息后重试。"
        )
    else:
        lines.append("所有步骤均已成功返回。需要口语解读可再说「用一段话总结上面结果」。")
    return "\n".join(lines)


async def format_orchestra_reply(
    intent_kind: str,
    hub: Dict[str, Any],
    user_input: str,
) -> str:
    """根据意图与 hub 包装生成自然语言；无 LLM 时用模板兜底。"""
    if not hub.get("ok"):
        err = hub.get("error")
        return f"这一步没有成功完成。{err or '请稍后重试或检查配置。'}"

    result = hub.get("result")
    if isinstance(result, dict) and result.get("type") == "clarification":
        r = (result.get("reply") or "").strip()
        return r if r else "请先补充本步所需信息（见上文说明）后再试。"

    if intent_kind == "conversation" and isinstance(result, dict):
        return (result.get("reply") or "").strip() or "（空回复）"

    if not isinstance(result, dict):
        return str(result)[:4000]

    # 对于需要登录的情况，直接使用模板回复（不走 LLM，确保提示清晰一致）
    if result.get("login_required") or result.get("data_source") == "login_required":
        return _template_reply(intent_kind, user_input, result)

    try:
        from llm_hub import get_client

        client = get_client(skill_name="orchestra_nlg")
        if client and client.config.api_key:
            return await _llm_format(client, intent_kind, user_input, result)
    except Exception:
        pass

    return _template_reply(intent_kind, user_input, result)


async def _llm_format(client: Any, kind: str, user_input: str, result: dict) -> str:
    payload = _truncate(json.dumps(result, ensure_ascii=False))
    prompt = (
        "你是 Lumina 营销助手，正在向用户说明系统刚执行完的一步分析结果。\n"
        f"用户原话：{user_input.strip()[:2000]}\n"
        f"本轮意图类型（内部）：{kind}\n"
        f"结构化结果（JSON）：\n{payload}\n\n"
        "请用中文写 4～8 句给用户看：\n"
        "1）先用一句话说明「已经为你做了什么」；\n"
        "2）概括关键结论（数字/要点用口语转述）；\n"
        "3）直接回应用户问题里最关心的点（例如流量、转化、内容）；\n"
        "4）给 1～3 条可执行的下一步。\n"
        "不要输出 JSON 或代码块；不要编造未出现在结构化结果里的具体平台数据。"
    )
    text = await client.complete(prompt, temperature=0.5, max_tokens=900)
    return (text or "").strip() or _template_reply(kind, user_input, result)


def _template_reply(kind: str, user_input: str, result: dict) -> str:
    uid = (user_input or "").strip()[:80]
    if kind == "diagnosis":
        # 检查是否需要登录
        if result.get("login_required") or result.get("data_source") == "login_required":
            platform = result.get("platform", "")
            platform_name = "抖音" if platform == "douyin" else ("小红书" if platform == "xiaohongshu" else platform)
            suggestions = result.get("suggestions", [])
            
            reply_lines = [
                f"要分析 {platform_name} 账号「{uid}」，我需要先获取您的账号数据。",
                "",
                "**您可以选择以下方式：**",
                "",
            ]
            
            for i, suggestion in enumerate(suggestions, 1):
                reply_lines.append(f"{i}. {suggestion}")
            
            reply_lines.extend([
                "",
                f"💡 **推荐方式**：直接说「**登录{platform_name}**」，我会生成二维码，您用 {platform_name} APP 扫码授权后，我就能自动获取您的账号数据进行专业分析。",
            ])
            
            if result.get("error_detail"):
                reply_lines.extend(["", f"（错误详情：{result['error_detail'][:100]}）"])
            
            return "\n".join(reply_lines)
        
        # 正常诊断结果
        score = result.get("health_score")
        issues = result.get("key_issues") or []
        sug = result.get("improvement_suggestions") or []
        meth = result.get("recommended_methodology", "")
        tips = []
        for s in sug[:3]:
            if isinstance(s, dict):
                tips.append(str(s.get("tip") or s))
            else:
                tips.append(str(s))
        iss_txt = "；".join(issues) if issues else "暂无"
        tip_txt = "；".join(tips) if tips else "保持内容节奏与封面钩子优化"
        return (
            f"**进度**：已跑完一轮账号基因诊断（Skill 侧仍为示意逻辑；真实结论需结合你的内容与数据）。\n"
            f"**结论**：健康度约 **{score} / 100**。主要问题：{iss_txt}。\n"
            f"**和流量相关**：互动与「前 3 秒钩子」偏弱时，常会导致推荐与流量下滑，建议优先改封面/开头与更新节奏。\n"
            f"**建议尝试**：{tip_txt}。\n"
            f"（系统推荐方法论：`{meth}`，需要可再说「走一遍 SOP」）"
        )

    if kind == "traffic":
        funnel = result.get("funnel_analysis") or {}
        insights = result.get("actionable_insights") or []
        trend = result.get("trend", "")
        ins = "；".join(insights) if insights else "结合曝光→互动→转化逐步排查"
        return (
            "**进度**：已根据你提供的指标做了流量结构分析（Skill 侧为规则化摘要，非平台实时后台）。\n"
            f"**漏斗摘要**：{json.dumps(funnel, ensure_ascii=False)[:500]}\n"
            f"**趋势**：{trend}。**建议**：{ins}。"
        )

    if kind == "risk":
        lvl = result.get("risk_level", "")
        cats = result.get("risk_categories") or []
        sug = result.get("suggestions") or []
        flagged = result.get("flagged_terms") or []
        flagged_txt = ", ".join([f"{f.get('term')}({f.get('category')})" for f in flagged[:5]]) if flagged else "无"
        return (
            "**进度**：已完成内容风险扫描。\n"
            f"**风险等级**：{lvl}；涉及：{'、'.join(cats) if cats else '无'}\n"
            f"**命中词**：{flagged_txt}\n"
            f"**修改建议**：{'；'.join(sug[:5]) if sug else '保持表述合规、避免绝对化用语。'}"
        )

    if kind == "qr_login":
        platform = result.get("platform", "")
        platform_name = "抖音" if platform == "douyin" else ("小红书" if platform == "xiaohongshu" else platform)
        return (
            f"请使用 {platform_name} APP 扫描下方二维码完成登录授权。\n"
            "扫描后我就能获取您的账号数据，继续为您分析。"
        )

    if kind == "general" and result.get("type") == "community_guide":
        return result.get("reply", "")

    if kind == "general" and result.get("methodology_id"):
        name = result.get("name", "")
        steps = result.get("steps") or []
        return (
            "**进度**：已从方法论库匹配到一套可参考框架。\n"
            f"**方法论**：{name}（`{result.get('methodology_id')}`），共 {len(steps)} 个步骤。\n"
            "如需按步骤带你执行，可以说「按这个方法论一步步来」或指定平台与目标。"
        )

    if kind == "content" and (result.get("title") or result.get("content")):
        return (
            "**进度**：已生成一版文案草稿。\n"
            f"**标题**：{result.get('title', '')}\n"
            f"**正文摘要**：{(result.get('content') or '')[:400]}…"
        )

    if kind == "topic" and result.get("recommended_topics"):
        topics = result.get("recommended_topics") or []
        calendar = result.get("content_calendar") or []
        first = topics[0] if topics else {}
        lines = [
            "**进度**：已结合热点与阶段给出选题方向。",
            f"**首推**：{first.get('topic', '')} — {first.get('reason', '')}",
        ]
        if calendar:
            lines.append("**近期日历**（示例）：")
            for i, day in enumerate(calendar[:7], 1):
                lines.append(f"第{i}天：{day.get('topic', '')}")
        return "\n".join(lines)

    if kind == "cases" and result.get("matched_cases"):
        cases = result.get("matched_cases") or []
        first = cases[0] if cases else {}
        return (
            "**进度**：已匹配到一些可参考案例。\n"
            f"**最相关案例**：{first.get('title', '')}（相似度 {first.get('similarity_score', 0)}）。\n"
            f"**关键成功因素**：{', '.join(first.get('key_success_factors', []))}\n"
            "你可以告诉我具体想深入拆解哪个案例。"
        )

    return (
        f"**进度**：已处理你的请求（类型：{kind}）。\n"
        f"**摘要**：{_truncate(json.dumps(result, ensure_ascii=False), 1200)}"
    )
