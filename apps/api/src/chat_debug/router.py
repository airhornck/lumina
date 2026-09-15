from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from chat_debug.memory import get_memory_store
from chat_debug.prompts import CAPABILITIES, system_prompt_for

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/debug", tags=["debug-chat"])

SYSTEM_CHAT_ID = "system_chat"


class ChatStreamBody(BaseModel):
    capability: str = Field(
        ...,
        description="system_chat | content_direction_ranking | ...",
    )
    user_id: str = Field(default="debug-user", min_length=1, max_length=128, description="用户唯一标识")
    conversation_id: str = Field(default="debug-conv", min_length=1, max_length=128, description="对话唯一标识")
    message: str = Field(..., min_length=1, max_length=32000, description="用户当前输入")
    platform: Optional[str] = Field(default=None, description="可选：xiaohongshu / douyin 等")
    hub_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="附加业务上下文，透传至 Hermes 引擎与工具层（仅 system_chat 使用）",
    )
    stream_format: Optional[int] = Field(
        default=None,
        description="1=v1 SSE；2=v2（仅 system_chat）。缺省可读 X-Lumina-Stream-Format",
    )

    @field_validator("stream_format")
    @classmethod
    def _validate_stream_format(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v not in (1, 2):
            raise ValueError("stream_format must be 1 or 2")
        return v


class CapabilityItem(BaseModel):
    id: str = Field(..., description="能力标识")
    label: str = Field(..., description="能力名称")


class CapabilitiesResponse(BaseModel):
    capabilities: list[CapabilityItem] = Field(..., description="可用能力列表")


class MemoryResponse(BaseModel):
    user_id: str = Field(..., description="用户唯一标识")
    conversation_id: str = Field(..., description="对话唯一标识")
    count: int = Field(..., description="消息数量")
    messages: list[Any] = Field(..., description="消息列表")


class DeleteMemoryResponse(BaseModel):
    ok: bool = Field(..., description="操作是否成功")
    cleared: bool = Field(..., description="是否已清除")


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


@router.get("/chat/capabilities", response_model=CapabilitiesResponse, summary="列出调试可用的 capabilities")
async def list_capabilities() -> dict[str, Any]:
    """列出 debug chat 支持的所有 capability 类型。"""
    # 系统对话放首位，便于调试主流程
    ordered = [SYSTEM_CHAT_ID] + [k for k in CAPABILITIES if k != SYSTEM_CHAT_ID]
    return {
        "capabilities": [
            {"id": k, "label": CAPABILITIES[k]["label"]} for k in ordered
        ]
    }


@router.get("/chat/memory", response_model=MemoryResponse, summary="查询 debug 对话记忆")
async def get_memory(
    user_id: str = Query(..., min_length=1, description="用户唯一标识"),
    conversation_id: str = Query(..., min_length=1, description="对话唯一标识"),
) -> dict[str, Any]:
    """查询指定 debug 对话的记忆列表。"""
    store = get_memory_store()
    messages = await store.list_messages(user_id, conversation_id)
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "count": len(messages),
        "messages": messages,
    }


@router.delete("/chat/memory", response_model=DeleteMemoryResponse, summary="清除 debug 对话记忆")
async def delete_memory(
    user_id: str = Query(..., min_length=1, description="用户唯一标识"),
    conversation_id: str = Query(..., min_length=1, description="对话唯一标识"),
) -> dict[str, Any]:
    """清除指定 debug 对话的全部记忆。"""
    store = get_memory_store()
    await store.clear(user_id, conversation_id)
    return {"ok": True, "cleared": True}


@router.get("/chat-logs", summary="查询对话日志（意图/工具调用排查）")
async def get_chat_logs(
    date: Optional[str] = Query(default=None, description="日期 YYYY-MM-DD，缺省今天"),
    user_id: Optional[str] = Query(default=None, description="按用户过滤"),
    conversation_id: Optional[str] = Query(default=None, description="按会话过滤"),
    limit: int = Query(default=200, ge=1, le=1000, description="返回最近 N 条"),
) -> dict[str, Any]:
    """查询 data/logs/chat/ 下的对话日志（每轮一条：路径/工具调用/thinking/回复/用量）。"""
    from services.conversation_log import query_logs

    records = query_logs(
        date=date, user_id=user_id, conversation_id=conversation_id, limit=limit
    )
    return {"count": len(records), "records": records}


@router.post(
    "/chat/stream",
    summary="Debug Chat 流式对话",
    response_class=StreamingResponse,
)
async def chat_stream(body: ChatStreamBody) -> StreamingResponse:
    """Debug Chat SSE 流式对话入口，system_chat 走 Hermes 引擎。"""
    if body.capability not in ALLOWED_CAPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid capability. Allowed: {sorted(ALLOWED_CAPS)}",
        )

    store = get_memory_store()
    # 只取最近 34 条（system_chat 切 24、其余 capability 切 34，取大者覆盖），读取量与历史总量脱钩
    history_before = await store.list_messages(body.user_id, body.conversation_id, limit=34)
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

        # Hermes Agent 为唯一执行引擎
        from services.hermes_adapter import HermesEngineAdapter

        async def hermes_gen() -> AsyncIterator[str]:
            adapter = HermesEngineAdapter()
            async for line in adapter.chat_stream(
                user_message=body.message,
                user_id=body.user_id,
                conversation_id=body.conversation_id,
                session_history=session_history,
                platform=body.platform,
                context=body.hub_context,
            ):
                yield line

        return StreamingResponse(hermes_gen(), media_type="text/event-stream")

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
