from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List

from fastapi import HTTPException

from services.memory_service import ServiceMemoryStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    "case": """你是 Lumina「定位决策案例库」能力助手。
职责：用案例化方式帮助用户做定位决策：人设/品类/差异化表达/目标受众，引用或类比「类案例」结构（可虚构合理匿名案例，但须标注为示例）。
要求：
- 用中文；输出：可选定位方案对比、适用场景、反例与踩坑。
- 强调可落地的 Slogan/一句话定位与内容调性建议。
- 明确区分事实与推断；缺信息时提问清单。""",
    "matrix": """你是 Lumina「内容定位矩阵」能力助手。
职责：用矩阵思维组织内容定位：例如「受众 × 痛点 × 形式 × 转化路径」或「价值主张 × 证据 × 渠道」。
要求：
- 用中文；优先输出 Markdown 表格或二维矩阵 + 解读。
- 给出每个象限/格子的内容策略与反例。
- 可请求用户补充维度权重或业务目标。""",
}


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def handle_positioning_stream(
    user_id: str,
    conversation_id: str,
    message: str,
    platform: str | None,
    context: Dict[str, Any],
    mode: str | None,
    store: ServiceMemoryStore,
) -> AsyncIterator[str]:
    service = "positioning"
    mode = (mode or "case").lower()
    if mode not in SYSTEM_PROMPTS:
        raise HTTPException(status_code=400, detail=f"Invalid mode for positioning. Allowed: {list(SYSTEM_PROMPTS.keys())}")

    history_before = await store.list_messages(user_id, conversation_id, service)
    await store.append(user_id, conversation_id, service, "user", message)

    yield _sse({"type": "start", "service": service, "mode": mode})

    from llm_hub import get_client, get_hub

    hub = get_hub()
    if not hub:
        yield _sse({"type": "error", "message": "LLM Hub 未初始化。请检查服务启动日志，确保 infra/config/llm.yaml 存在且格式正确。"})
        return

    client = get_client(skill_name="debug_chat")
    if not client:
        yield _sse({"type": "error", "message": f"无法获取 debug_chat 客户端。请检查 llm.yaml 中的 skill_config 是否包含 debug_chat 配置。当前 skill_config: {list(hub.config.skill_config.keys())}"})
        return

    if not client.config.api_key:
        yield _sse({"type": "error", "message": f"debug_chat 客户端缺少 API Key。当前配置: name={client.config.name}, provider={client.config.provider}, api_base={client.config.api_base}。请在 .env 中设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY。"})
        return

    system = SYSTEM_PROMPTS[mode]
    if platform:
        system += f"\n\n【当前平台上下文】{platform}"

    hist_rows = [
        r
        for r in history_before
        if r.get("role") in ("user", "assistant") and isinstance(r.get("content"), str)
    ]
    hist_rows = hist_rows[-34:]
    conv_messages: List[dict[str, str]] = [{"role": "system", "content": system}]
    for row in hist_rows:
        conv_messages.append({"role": str(row["role"]), "content": str(row["content"])})
    conv_messages.append({"role": "user", "content": message})

    full: list[str] = []
    try:
        async for piece in client.stream_completion(conv_messages):
            full.append(piece)
            yield _sse({"type": "delta", "text": piece})
    except Exception as e:
        logger.exception("positioning stream failed")
        yield _sse({"type": "error", "message": str(e)[:800]})
        return

    text = "".join(full)
    await store.append(user_id, conversation_id, service, "assistant", text)
    yield _sse({"type": "done", "full_length": len(text)})
