from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.models import ServiceStreamRequest
from services.memory_service import get_service_memory_store
from services.stream_format import effective_stream_format
from services.handlers.system_chat import handle_system_chat_stream
from services.handlers.cross_platform_content import handle_cross_platform_content_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/services", tags=["services"])

# 对外统一入口：system-chat；cross-platform-content 保留但非服务流核心。
ALLOWED_SERVICES = frozenset({"system-chat", "cross-platform-content"})
# 已下线独立服务流接口，按业务真源 v1.2 统一收敛到 system-chat。
DEPRECATED_SERVICES = frozenset({"content-ranking", "positioning", "weekly-snapshot"})

_GONE_DETAIL = (
    "This endpoint is deprecated. Please use POST /api/v1/services/system-chat/stream "
    "with natural language intent."
)


class MemoryMessage(BaseModel):
    role: str = Field(..., description="消息角色")
    content: Any = Field(..., description="消息内容")
    created_at: Optional[str] = Field(None, description="创建时间")


class MemoryResponse(BaseModel):
    user_id: str = Field(..., description="用户唯一标识")
    conversation_id: str = Field(..., description="对话唯一标识")
    service: str = Field(..., description="服务名称")
    count: int = Field(..., description="本次返回的消息条数")
    messages: list[Any] = Field(..., description="消息列表")
    total: int = Field(..., description="该会话消息总数")
    has_more: bool = Field(..., description="是否还有更早的消息")


class DeleteMemoryResponse(BaseModel):
    ok: bool = Field(..., description="操作是否成功")
    cleared: bool = Field(..., description="是否已清除")
    service: str = Field(..., description="服务名称")


def _raise_if_deprecated(service: str) -> None:
    if service in DEPRECATED_SERVICES:
        raise HTTPException(status_code=410, detail=_GONE_DETAIL)


@router.post(
    "/{service}/stream",
    summary="服务流式对话",
    response_class=StreamingResponse,
)
async def service_stream(service: str, body: ServiceStreamRequest, request: Request) -> StreamingResponse:
    """按服务进行 SSE 流式对话。"""
    _raise_if_deprecated(service)
    if service not in ALLOWED_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service. Allowed: {sorted(ALLOWED_SERVICES)}",
        )

    store = get_service_memory_store()
    sf = effective_stream_format(body.stream_format, request.headers)

    if service == "system-chat":
        gen = handle_system_chat_stream(
            body.user_id,
            body.conversation_id,
            body.message,
            body.platform,
            body.context,
            store,
            stream_format=sf,
        )
    else:  # cross-platform-content
        gen = handle_cross_platform_content_stream(
            body.user_id,
            body.conversation_id,
            body.message,
            body.platform,
            body.context,
            store,
        )

    return StreamingResponse(gen, media_type="text/event-stream")


@router.get("/{service}/memory", response_model=MemoryResponse, summary="查询服务对话记忆")
async def get_memory(
    service: str,
    user_id: str = Query(..., min_length=1, description="用户唯一标识"),
    conversation_id: str = Query(..., min_length=1, description="对话唯一标识"),
    limit: Optional[int] = Query(default=None, ge=1, le=1000, description="取最新 N 条；不传返回全部"),
    offset: int = Query(default=0, ge=0, description="跳过最新 N 条（向更早翻页）"),
    order: str = Query(default="asc", pattern="^(asc|desc)$", description="返回顺序 asc/desc"),
) -> dict[str, Any]:
    """查询指定服务的对话记忆列表，支持“最新优先”分页。"""
    _raise_if_deprecated(service)
    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service. Allowed: {sorted(ALLOWED_SERVICES)}")
    store = get_service_memory_store()
    messages = await store.list_messages(
        user_id, conversation_id, service, limit=limit, offset=offset, order=order
    )
    total = await store.count_messages(user_id, conversation_id, service)
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "service": service,
        "count": len(messages),
        "messages": messages,
        "total": total,
        "has_more": (offset + len(messages)) < total,
    }


@router.delete("/{service}/memory", response_model=DeleteMemoryResponse, summary="清除服务对话记忆")
async def delete_memory(
    service: str,
    user_id: str = Query(..., min_length=1, description="用户唯一标识"),
    conversation_id: str = Query(..., min_length=1, description="对话唯一标识"),
) -> dict[str, Any]:
    """清除指定服务的对话记忆。"""
    _raise_if_deprecated(service)
    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service. Allowed: {sorted(ALLOWED_SERVICES)}")
    store = get_service_memory_store()
    await store.clear(user_id, conversation_id, service)
    return {"ok": True, "cleared": True, "service": service}
