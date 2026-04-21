from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from services.models import ServiceStreamRequest
from services.memory_service import get_service_memory_store
from services.handlers.system_chat import handle_system_chat_stream
from services.handlers.content_ranking import handle_content_ranking_stream
from services.handlers.positioning import handle_positioning_stream
from services.handlers.weekly_snapshot import handle_weekly_snapshot_stream
from services.handlers.cross_platform_content import handle_cross_platform_content_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/services", tags=["services"])

ALLOWED_SERVICES = frozenset({"system-chat", "content-ranking", "positioning", "weekly-snapshot", "cross-platform-content"})


@router.post("/{service}/stream")
async def service_stream(service: str, body: ServiceStreamRequest) -> StreamingResponse:
    if service not in ALLOWED_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service. Allowed: {sorted(ALLOWED_SERVICES)}",
        )

    store = get_service_memory_store()

    if service == "system-chat":
        gen = handle_system_chat_stream(
            body.user_id,
            body.conversation_id,
            body.message,
            body.platform,
            body.context,
            store,
        )
    elif service == "content-ranking":
        gen = handle_content_ranking_stream(
            body.user_id,
            body.conversation_id,
            body.message,
            body.platform,
            body.context,
            store,
        )
    elif service == "positioning":
        gen = handle_positioning_stream(
            body.user_id,
            body.conversation_id,
            body.message,
            body.platform,
            body.context,
            body.mode,
            store,
        )
    elif service == "weekly-snapshot":
        gen = handle_weekly_snapshot_stream(
            body.user_id,
            body.conversation_id,
            body.message,
            body.platform,
            body.context,
            store,
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


@router.get("/{service}/memory")
async def get_memory(
    service: str,
    user_id: str = Query(..., min_length=1),
    conversation_id: str = Query(..., min_length=1),
) -> dict[str, Any]:
    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service. Allowed: {sorted(ALLOWED_SERVICES)}")
    store = get_service_memory_store()
    messages = await store.list_messages(user_id, conversation_id, service)
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "service": service,
        "count": len(messages),
        "messages": messages,
    }


@router.delete("/{service}/memory")
async def delete_memory(
    service: str,
    user_id: str = Query(..., min_length=1),
    conversation_id: str = Query(..., min_length=1),
) -> dict[str, Any]:
    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service. Allowed: {sorted(ALLOWED_SERVICES)}")
    store = get_service_memory_store()
    await store.clear(user_id, conversation_id, service)
    return {"ok": True, "cleared": True, "service": service}
