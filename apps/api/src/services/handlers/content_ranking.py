from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List

from services.memory_service import ServiceMemoryStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 Lumina「内容方向榜单」能力助手。
职责：帮助用户梳理、排序、对比可选的内容方向（主题赛道、系列栏目、内容支柱），输出可执行的「方向榜单」结构。
要求：
- 用中文回复；条理清晰，可用 Markdown 表格或分级列表。
- 结合用户行业/平台上下文，给出 TOP 方向、推荐理由、风险与优先级。
- 若信息不足，先列出假设并说明需要补充的数据。
- 不要编造具体平台内部数据；可给行业通用判断与框架。"""


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def handle_content_ranking_stream(
    user_id: str,
    conversation_id: str,
    message: str,
    platform: str | None,
    context: Dict[str, Any],
    store: ServiceMemoryStore,
) -> AsyncIterator[str]:
    service = "content-ranking"
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
        logger.exception("content_ranking stream failed")
        yield _sse({"type": "error", "message": str(e)[:800]})
        return

    text = "".join(full)
    await store.append(user_id, conversation_id, service, "assistant", text)
    yield _sse({"type": "done", "full_length": len(text)})
