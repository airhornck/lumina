from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List

from services.memory_service import ServiceMemoryStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 Lumina「每周决策快照」能力助手。
职责：把用户本周（或指定期）在内容/增长上的决策整理成「快照」：目标、实验、数据假设、本周行动项、风险与复盘问题。
要求：
- 用中文；结构包含：摘要、本周 TOP 3 决策/实验、指标、下一步、需要数据。
- 语气像周报 + 决策日志；可适度追问以补全快照。"""


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def handle_weekly_snapshot_stream(
    user_id: str,
    conversation_id: str,
    message: str,
    platform: str | None,
    context: Dict[str, Any],
    store: ServiceMemoryStore,
) -> AsyncIterator[str]:
    service = "weekly-snapshot"
    history_before = await store.list_messages(user_id, conversation_id, service)
    await store.append(user_id, conversation_id, service, "user", message)

    yield _sse({"type": "start", "service": service})

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

    system = SYSTEM_PROMPT
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
        logger.exception("weekly_snapshot stream failed")
        yield _sse({"type": "error", "message": str(e)[:800]})
        return

    text = "".join(full)
    await store.append(user_id, conversation_id, service, "assistant", text)
    yield _sse({"type": "done", "full_length": len(text)})
