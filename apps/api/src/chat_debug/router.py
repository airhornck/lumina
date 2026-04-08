from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from chat_debug.memory import get_memory_store
from chat_debug.prompts import CAPABILITIES, system_prompt_for

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/debug", tags=["debug-chat"])

SYSTEM_CHAT_ID = "system_chat"
STREAM_CHUNK = 96


class ChatStreamBody(BaseModel):
    capability: str = Field(
        ...,
        description="system_chat | content_direction_ranking | ...",
    )
    user_id: str = Field(default="debug-user", min_length=1, max_length=128)
    conversation_id: str = Field(default="debug-conv", min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=32000)
    platform: Optional[str] = Field(default=None, description="可选：xiaohongshu / douyin 等")
    hub_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="与 POST /api/v1/marketing/hub 的 context 一致，传入 MarketingOrchestra（仅 system_chat 使用）",
    )


ALLOWED_CAPS = frozenset(CAPABILITIES.keys())


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _memory_rows_to_session(rows: List[dict[str, Any]], limit: int = 24) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        if r.get("role") not in ("user", "assistant"):
            continue
        c = r.get("content")
        if not isinstance(c, str):
            continue
        out.append({"role": r["role"], "content": c})
    return out[-limit:]


@router.get("/chat/capabilities")
async def list_capabilities() -> dict[str, Any]:
    # 系统对话放首位，便于调试主流程
    ordered = [SYSTEM_CHAT_ID] + [k for k in CAPABILITIES if k != SYSTEM_CHAT_ID]
    return {
        "capabilities": [
            {"id": k, "label": CAPABILITIES[k]["label"]} for k in ordered
        ]
    }


@router.get("/chat/memory")
async def get_memory(
    user_id: str = Query(..., min_length=1),
    conversation_id: str = Query(..., min_length=1),
) -> dict[str, Any]:
    store = get_memory_store()
    messages = await store.list_messages(user_id, conversation_id)
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "count": len(messages),
        "messages": messages,
    }


@router.delete("/chat/memory")
async def delete_memory(
    user_id: str = Query(..., min_length=1),
    conversation_id: str = Query(..., min_length=1),
) -> dict[str, Any]:
    store = get_memory_store()
    await store.clear(user_id, conversation_id)
    return {"ok": True, "cleared": True}


async def _stream_orchestra_result(text: str) -> AsyncIterator[str]:
    for i in range(0, len(text), STREAM_CHUNK):
        yield text[i : i + STREAM_CHUNK]
        await asyncio.sleep(0)


@router.post("/chat/stream")
async def chat_stream(body: ChatStreamBody) -> StreamingResponse:
    if body.capability not in ALLOWED_CAPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid capability. Allowed: {sorted(ALLOWED_CAPS)}",
        )

    store = get_memory_store()
    history_before = await store.list_messages(body.user_id, body.conversation_id)
    await store.append(
        body.user_id,
        body.conversation_id,
        "user",
        body.message,
        capability=body.capability,
    )

    if body.capability == SYSTEM_CHAT_ID:
        hist_rows = [
            r
            for r in history_before
            if r.get("role") in ("user", "assistant")
            and isinstance(r.get("content"), str)
        ]
        session_history = _memory_rows_to_session(hist_rows)

        async def orchestra_gen() -> AsyncIterator[str]:
            yield _sse({"type": "start", "capability": SYSTEM_CHAT_ID, "via": "marketing_orchestra"})
            try:
                from orchestra.core import MarketingOrchestra

                orch = MarketingOrchestra()
                result = await orch.process(
                    body.message,
                    body.user_id,
                    session_history,
                    body.platform,
                    body.hub_context,
                )
                payload = {"ok": True, **result}
                text = json.dumps(payload, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.exception("system_chat orchestra failed")
                yield _sse({"type": "error", "message": str(e)[:800]})
                return
            full_chunks: list[str] = []
            try:
                async for piece in _stream_orchestra_result(text):
                    full_chunks.append(piece)
                    yield _sse({"type": "delta", "text": piece})
            except Exception as e:
                logger.exception("system_chat stream chunk failed")
                yield _sse({"type": "error", "message": str(e)[:800]})
                return
            full = "".join(full_chunks)
            await store.append(
                body.user_id,
                body.conversation_id,
                "assistant",
                full,
                capability=body.capability,
            )
            yield _sse({"type": "done", "full_length": len(full)})

        return StreamingResponse(orchestra_gen(), media_type="text/event-stream")

    from llm_hub import get_client, get_hub

    hub = get_hub()
    if not hub:
        async def err_no_hub() -> AsyncIterator[str]:
            yield _sse(
                {
                    "type": "error",
                    "message": "LLM Hub 未初始化。请检查服务启动日志，确保 infra/config/llm.yaml 存在且格式正确。",
                }
            )
        return StreamingResponse(err_no_hub(), media_type="text/event-stream")

    client = get_client(skill_name="debug_chat")
    if not client:
        async def err_no_client() -> AsyncIterator[str]:
            yield _sse(
                {
                    "type": "error",
                    "message": f"无法获取 debug_chat 客户端。请检查 llm.yaml 中的 skill_config 是否包含 debug_chat 配置。当前 skill_config: {list(hub.config.skill_config.keys())}",
                }
            )
        return StreamingResponse(err_no_client(), media_type="text/event-stream")
    
    if not client.config.api_key:
        async def err_no_key() -> AsyncIterator[str]:
            yield _sse(
                {
                    "type": "error",
                    "message": f"debug_chat 客户端缺少 API Key。当前配置: name={client.config.name}, provider={client.config.provider}, api_base={client.config.api_base}。请在 .env 中设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY。",
                }
            )
        return StreamingResponse(err_no_key(), media_type="text/event-stream")

    system = system_prompt_for(body.capability)
    if body.platform:
        system += f"\n\n【当前平台上下文】{body.platform}"

    hist_rows = [
        r
        for r in history_before
        if r.get("role") in ("user", "assistant")
        and isinstance(r.get("content"), str)
    ]
    hist_rows = hist_rows[-34:]
    conv_messages: List[dict[str, str]] = [{"role": "system", "content": system}]
    for row in hist_rows:
        conv_messages.append(
            {"role": str(row["role"]), "content": str(row["content"])}
        )
    conv_messages.append({"role": "user", "content": body.message})

    async def llm_gen() -> AsyncIterator[str]:
        yield _sse({"type": "start", "capability": body.capability})
        full: list[str] = []
        try:
            async for piece in client.stream_completion(conv_messages):
                full.append(piece)
                yield _sse({"type": "delta", "text": piece})
        except Exception as e:
            logger.exception("debug chat stream failed")
            yield _sse({"type": "error", "message": str(e)[:800]})
            return
        text = "".join(full)
        await store.append(
            body.user_id,
            body.conversation_id,
            "assistant",
            text,
            capability=body.capability,
        )
        yield _sse({"type": "done", "full_length": len(text)})

    return StreamingResponse(llm_gen(), media_type="text/event-stream")
