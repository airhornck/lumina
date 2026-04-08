"""编排层 NLG：把 Skill 结构化结果转成用户可读说明（保留 hub 原始数据）。"""

from __future__ import annotations

import json
from typing import Any, Dict


def _truncate(s: str, n: int = 7000) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


async def format_sop_summary(sop_out: Dict[str, Any], user_input: str) -> str:
    """SOP 模式：简要说明执行到哪一步。"""
    dag = sop_out.get("dag") or []
    nodes = sop_out.get("node_results") or {}
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
        lines.append(f"- `{sid}` → 工具 `{sk}`：{'✓ 已返回' if ok else '✗ 未完成'}")
    lines.append("")
    lines.append("详细 JSON 见 `sop.node_results`；需要口语解读可再说「用一段话总结上面结果」。")
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
        return (
            "**进度**：已完成内容风险扫描。\n"
            f"**风险等级**：{lvl}；涉及：{'、'.join(cats) if cats else '无'}\n"
            f"**修改建议**：{'；'.join(sug[:5]) if sug else '保持表述合规、避免绝对化用语。'}"
        )

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
        first = topics[0] if topics else {}
        return (
            "**进度**：已结合热点与阶段给出选题方向。\n"
            f"**首推**：{first.get('topic', '')} — {first.get('reason', '')}"
        )

    return (
        f"**进度**：已处理你的请求（类型：{kind}）。\n"
        f"**摘要**：{_truncate(json.dumps(result, ensure_ascii=False), 1200)}"
    )
