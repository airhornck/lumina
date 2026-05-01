"""
跨平台内容生成 SSE Handler

直接编排 LLM + PlatformRegistry + MethodologyRegistry
不依赖 skill-bulk-creative（独立 MCP Server，未被主 API 真实调用）

事件流：
  start → platform_chunk (per platform) → [warning] → [error per platform] → done
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

from services.memory_service import ServiceMemoryStore

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _load_prompt_template(name: str) -> str:
    """加载 Prompt 模板文件"""
    path = _PROMPTS_DIR / f"{name}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _extract_platforms_from_message(message: str) -> List[str]:
    """从用户消息中提取目标平台"""
    platforms: List[str] = []
    msg_lower = message.lower()
    platform_map = {
        "小红书": "xiaohongshu",
        "xiaohongshu": "xiaohongshu",
        "抖音": "douyin",
        "douyin": "douyin",
        "b站": "bilibili",
        "bilibili": "bilibili",
        "哔哩哔哩": "bilibili",
    }
    for keyword, platform_id in platform_map.items():
        if keyword in msg_lower and platform_id not in platforms:
            platforms.append(platform_id)
    if not platforms:
        platforms = ["xiaohongshu", "douyin", "bilibili"]
    return platforms


def _is_revision_request(message: str) -> bool:
    """检测用户消息是否为修稿请求"""
    revision_keywords = [
        "改", "调整", "再", "修", "软一点", "硬一点", "短一点",
        "长一点", "换", "重写", "优化", "润色", "改一下",
        "不够", "太", "稍微", "稍微", "能不能", "可以",
    ]
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in revision_keywords)


def _build_platform_prompt(
    master_content: Dict[str, Any],
    platform: str,
    spec: Any,
    methodology: Any,
    seed_topic: Dict[str, Any] | None,
    user_position: Dict[str, Any] | None,
    content_type: str = "图文",
) -> str:
    """构建平台适配 Prompt，注入 DNA + 审核规则 + 格式约束 + 方法论"""

    # 平台 DNA
    dna_lines: List[str] = []
    if spec and hasattr(spec, "content_dna") and spec.content_dna:
        for item in spec.content_dna:
            if isinstance(item, dict):
                element = item.get("element", "")
                value = item.get("value", "")
            else:
                element = getattr(item, "element", "")
                value = getattr(item, "value", "")
            if element:
                dna_lines.append(f"{element}: {value}")

    # 审核规则
    audit_lines: List[str] = []
    if spec and hasattr(spec, "audit_rules") and spec.audit_rules:
        for rule in spec.audit_rules:
            if isinstance(rule, dict):
                category = rule.get("category", "")
                forbidden = rule.get("forbidden_terms", [])
                if category and forbidden:
                    audit_lines.append(f"{category}类禁用词: {', '.join(forbidden)}")

    # 格式约束
    format_constraints: List[str] = []
    if spec and hasattr(spec, "content_formats") and spec.content_formats:
        for fmt_name, fmt_cfg in spec.content_formats.items():
            if isinstance(fmt_cfg, dict) and not fmt_cfg.get("note"):
                format_constraints.append(f"{fmt_name}: {fmt_cfg}")

    # 方法论引导
    meth_guide = ""
    if methodology:
        name = ""
        steps: List[Any] = []
        if hasattr(methodology, "name"):
            name = methodology.name or ""
        if hasattr(methodology, "steps"):
            steps = methodology.steps or []
        if not name and hasattr(methodology, "raw"):
            name = methodology.raw.get("name", "")
            steps = methodology.raw.get("steps", [])
        if name:
            meth_guide = f"内容方法论：{name}\n"
            if steps:
                meth_guide += f"步骤框架：{steps}\n"

    # 选题种子
    seed_info = ""
    if seed_topic:
        seed_info = f"""选题信息：
- 名称：{seed_topic.get('name', '')}
- 切入角度：{', '.join(seed_topic.get('angles', []))}
- 推荐标题模板：{seed_topic.get('title_templates', [])}
"""

    # 用户定位
    position_info = ""
    if user_position:
        position_info = f"""用户定位：
- 专业独特性：{user_position.get('x', 50)}/100
- 市场需求度：{user_position.get('y', 50)}/100
- 定位反馈：{user_position.get('feedback', '')}
"""

    platform_names = {
        "xiaohongshu": "小红书",
        "douyin": "抖音",
        "bilibili": "B站",
    }
    platform_cn = platform_names.get(platform, platform)

    template = _load_prompt_template("platform_adapt")
    if template:
        return template.format(
            platform=platform_cn,
            content_type=content_type,
            dna=chr(10).join(dna_lines) if dna_lines else "（无特定 DNA 约束）",
            audit=chr(10).join(audit_lines) if audit_lines else "（无特定审核规则）",
            formats=chr(10).join(format_constraints)
            if format_constraints
            else "（无特定格式约束）",
            methodology=meth_guide,
            seed=seed_info,
            position=position_info,
            title=master_content.get("title", ""),
            content=master_content.get("content", ""),
        )

    # fallback
    return f"""请将以下内容改写为适合 **{platform_cn}** 平台的版本。

【内容类型】{content_type}

【平台 DNA】
{chr(10).join(dna_lines) if dna_lines else "（无特定 DNA 约束）"}

【审核规则】
{chr(10).join(audit_lines) if audit_lines else "（无特定审核规则）"}

【格式约束】
{chr(10).join(format_constraints) if format_constraints else "（无特定格式约束）"}

{meth_guide}
{seed_info}
{position_info}

【原始内容】
标题：{master_content.get('title', '')}
正文：{master_content.get('content', '')}

【输出要求】
请输出严格符合以下 JSON 格式的内容：
{{
  "title": "平台适配后的标题（符合平台长度限制）",
  "body": "平台适配后的正文内容（符合平台风格）",
  "hashtags": ["标签1", "标签2", "标签3"],
  "hook": "如果是视频平台，写出黄金3秒钩子；图文平台可留空",
  "best_time": "建议发布时间",
  "compliance_warnings": ["如有合规风险请列出，无则留空数组"]
}}
"""


async def _generate_master_content(
    message: str,
    seed_topic: Dict[str, Any] | None,
    user_position: Dict[str, Any] | None,
    client: Any,
) -> Dict[str, Any]:
    """基于用户消息或选题种子生成核心内容"""

    template = _load_prompt_template("master_content")

    if seed_topic:
        input_str = f"""选题：{seed_topic.get('name', '')}
切入角度：{', '.join(seed_topic.get('angles', []))}"""
        if template:
            prompt = template.format(source="选题种子", input=input_str)
        else:
            prompt = f"""基于以下选题种子，生成一篇核心内容（标题 + 正文）。

{input_str}

要求：
- 标题吸引人但不做标题党
- 正文 300-800 字，信息密度高
- 输出严格 JSON 格式，不要任何额外文字

{{
  "title": "标题",
  "content": "正文内容",
  "topic": "核心主题"
}}
"""
    else:
        if template:
            prompt = template.format(
                source="用户请求", input=f"请求：{message}"
            )
        else:
            prompt = f"""基于以下用户请求，生成一篇核心内容（标题 + 正文）。

请求：{message}

要求：
- 标题吸引人但不做标题党
- 正文 300-800 字，信息密度高
- 输出严格 JSON 格式，不要任何额外文字

{{
  "title": "标题",
  "content": "正文内容",
  "topic": "核心主题"
}}
"""

    response = await client.complete(
        prompt=prompt,
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=4096,
        _usage_meta={"user_id": user_id, "skill_name": "cross_platform_content"},
    )

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        logger.warning("Failed to parse master content JSON: %s", response[:200])
        return {
            "title": message[:50] if message else "未命名内容",
            "content": message if message else "",
            "topic": message[:30] if message else "通用",
        }


async def _revise_platform_content(
    previous_content: Dict[str, Any],
    revision_request: str,
    platform: str,
    client: Any,
) -> Dict[str, Any]:
    """基于上一轮内容和修稿要求，重新生成平台内容"""

    template = _load_prompt_template("revision")
    platform_names = {
        "xiaohongshu": "小红书",
        "douyin": "抖音",
        "bilibili": "B站",
    }
    platform_cn = platform_names.get(platform, platform)

    prev_text = json.dumps(previous_content, ensure_ascii=False)

    if template:
        prompt = template.format(
            previous_content=prev_text,
            revision_request=revision_request,
            platform=platform_cn,
        )
    else:
        prompt = f"""你是 Lumina「跨平台内容修稿」助手。

用户要求对上一轮生成的内容进行修改：

【上一轮内容】
{prev_text}

【修改要求】
{revision_request}

【目标平台】
{platform_cn}

请根据修改要求，重新生成适合该平台的版本。保持原有核心信息不变，只做风格/语气/结构的调整。

输出严格 JSON 格式：
{{
  "title": "修改后的标题",
  "body": "修改后的正文",
  "hashtags": ["标签1", "标签2"],
  "hook": "钩子（如有）",
  "best_time": "建议发布时间",
  "compliance_warnings": []
}}
"""

    response = await client.complete(
        prompt=prompt,
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=4096,
        _usage_meta={"user_id": user_id, "skill_name": "cross_platform_content"},
    )

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        logger.warning("Failed to parse revision JSON: %s", response[:200])
        return previous_content


def _scan_compliance(text: str, audit_rules: List[Dict[str, Any]]) -> List[str]:
    """基于 audit_rules 做简单的合规扫描"""
    warnings: List[str] = []
    if not audit_rules:
        return warnings
    for rule in audit_rules:
        if not isinstance(rule, dict):
            continue
        category = rule.get("category", "")
        forbidden = rule.get("forbidden_terms", [])
        for term in forbidden:
            if term in text:
                warnings.append(f"命中{category}类禁用词：{term}")
    return warnings


async def handle_cross_platform_content_stream(
    user_id: str,
    conversation_id: str,
    message: str,
    platform: str | None,
    context: Dict[str, Any],
    store: ServiceMemoryStore,
) -> AsyncIterator[str]:
    """
    跨平台内容生成 SSE Handler

    1. 提取参数（target_platforms / seed_topic / user_position / master_content）
    2. 若未提供核心内容，由 LLM 生成 master content
    3. 检测是否为多轮修稿请求，若是则基于历史重新生成
    4. 匹配最佳方法论（MethodologyRegistry）
    5. 逐平台适配：读取 PlatformSpec → 构建 Prompt → LLM 生成 → 合规扫描 → SSE 推送
    6. 保存完整结果到 ServiceMemoryStore
    """
    service = "cross-platform-content"

    # 1. 提取参数
    target_platforms = (
        context.get("target_platforms")
        or _extract_platforms_from_message(message)
    )
    if not target_platforms:
        target_platforms = ["xiaohongshu", "douyin", "bilibili"]

    seed_topic = context.get("seed_topic")
    user_position = context.get("user_position")
    master = context.get("master_content")
    content_type = context.get("content_type", "图文")

    # 2. 记忆处理
    history_before = await store.list_messages(user_id, conversation_id, service)
    await store.append(user_id, conversation_id, service, "user", message)

    yield _sse(
        {"type": "start", "service": service, "platforms": target_platforms}
    )

    # 3. 初始化 LLM
    from llm_hub import get_client, get_hub

    hub = get_hub()
    if not hub:
        yield _sse(
            {
                "type": "error",
                "message": "LLM Hub 未初始化。请检查服务启动日志。",
            }
        )
        return

    client = get_client(skill_name="cross_platform_content")
    if not client:
        client = get_client()
    if not client:
        yield _sse(
            {
                "type": "error",
                "message": "无法获取 LLM 客户端。请检查 llm.yaml 配置。",
            }
        )
        return

    if not client.config.api_key:
        yield _sse({"type": "error", "message": "LLM 客户端缺少 API Key。"})
        return

    # 4. 检测是否为修稿请求
    is_revision = _is_revision_request(message)
    previous_contents: Dict[str, Dict[str, Any]] = {}
    if is_revision and history_before:
        # 从历史消息中提取上一轮 assistant 的 JSON 内容
        for row in reversed(history_before):
            if row.get("role") == "assistant" and isinstance(row.get("content"), str):
                try:
                    prev = json.loads(row["content"])
                    if isinstance(prev, dict) and "platform" in prev:
                        previous_contents[prev["platform"]] = prev
                except json.JSONDecodeError:
                    continue
                break

    # 5. 若用户未提供核心内容且不是修稿，由 LLM 生成
    if not master and not is_revision:
        try:
            master = await _generate_master_content(
                message, seed_topic, user_position, client
            )
        except Exception as e:
            logger.exception("Failed to generate master content")
            yield _sse(
                {
                    "type": "error",
                    "message": f"生成核心内容失败: {str(e)[:500]}",
                }
            )
            return

    # 6. 匹配最佳方法论
    methodology = None
    try:
        from knowledge_base.methodology_registry import MethodologyRegistry

        query_topic = master.get("topic", "") if master else message[:50]
        methodology = MethodologyRegistry().find_best_match(
            query=query_topic,
            industry=context.get("industry", ""),
            goal=context.get("optimization_goal", ""),
        )
    except Exception as e:
        logger.warning("Methodology matching failed: %s", e)

    # 7. 逐平台适配
    full_responses: List[str] = []

    for pf in target_platforms:
        try:
            from knowledge_base.platform_registry import PlatformRegistry

            spec = PlatformRegistry().load(pf)

            if is_revision and pf in previous_contents:
                # 修稿模式：基于上一轮内容重新生成
                content = await _revise_platform_content(
                    previous_contents[pf],
                    message,
                    pf,
                    client,
                )
            else:
                # 正常生成模式
                prompt = _build_platform_prompt(
                    master_content=master or {"title": message[:50], "content": message},
                    platform=pf,
                    spec=spec,
                    methodology=methodology,
                    seed_topic=seed_topic,
                    user_position=user_position,
                    content_type=content_type,
                )

                response = await client.complete(
                    prompt=prompt,
                    response_format={"type": "json_object"},
                    temperature=0.7,
                    max_tokens=4096,
                    _usage_meta={"user_id": user_id, "skill_name": "cross_platform_content"},
                )

                try:
                    content = json.loads(response)
                except json.JSONDecodeError:
                    content = {
                        "title": (master or {}).get("title", ""),
                        "body": response[:2000],
                        "hashtags": [],
                        "hook": "",
                        "best_time": "",
                        "compliance_warnings": ["JSON 解析失败，返回原始文本"],
                    }

            # 合规扫描
            audit_rules = []
            if spec and hasattr(spec, "audit_rules"):
                audit_rules = spec.audit_rules or []
            full_text = content.get("title", "") + content.get("body", "")
            warnings = _scan_compliance(full_text, audit_rules)
            if warnings:
                content["compliance_warnings"] = warnings
                yield _sse(
                    {
                        "type": "warning",
                        "platform": pf,
                        "warnings": warnings,
                    }
                )

            # 补充平台特定字段（差异化内容类型）
            if pf == "xiaohongshu":
                content["pic_count_tip"] = "6-9 张"
                content["pic_ratio"] = "3:4"
                if content_type == "视频":
                    content["format"] = "视频"
                    content["video_duration_tip"] = "15-60 秒"
                else:
                    content["format"] = content_type
            elif pf == "douyin":
                content["duration_tip"] = "15-60 秒"
                content["format"] = "视频"
                if content_type == "仅文字":
                    content["format"] = "图文"
            elif pf == "bilibili":
                content["danmu_prompt"] = "在关键转折点设置弹幕互动引导"
                content["format"] = "视频"
                if content_type == "图文":
                    content["format"] = "图文"
                    content["pic_count_tip"] = "3-6 张"

            content["platform"] = pf

            yield _sse(
                {"type": "platform_chunk", "platform": pf, "content": content}
            )
            full_responses.append(json.dumps(content, ensure_ascii=False))

        except Exception as e:
            logger.exception("Platform %s generation failed", pf)
            yield _sse(
                {
                    "type": "error",
                    "platform": pf,
                    "message": f"生成失败: {str(e)[:500]}",
                }
            )
            continue

    # 8. 保存到记忆
    full_text = "\n\n".join(full_responses)
    if full_text:
        await store.append(
            user_id, conversation_id, service, "assistant", full_text
        )

    yield _sse(
        {
            "type": "done",
            "total_platforms": len(target_platforms),
            "full_length": len(full_text),
        }
    )
