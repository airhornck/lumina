"""编排层 HTTP：供 OpenClaw `marketing_intelligence_hub` 调用。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from orchestra.core import MarketingOrchestra

router = APIRouter(prefix="/api/v1/marketing", tags=["marketing-hub"])

_orch: MarketingOrchestra | None = None


def get_orchestra() -> MarketingOrchestra:
    global _orch
    if _orch is None:
        _orch = MarketingOrchestra()
    return _orch


class MarketingHubBody(BaseModel):
    user_input: str = Field(..., min_length=1)
    user_id: str = Field(default="anonymous")
    session_history: List[Dict[str, Any]] = Field(default_factory=list)
    platform: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


@router.post("/hub")
async def marketing_intelligence_hub(body: MarketingHubBody) -> Dict[str, Any]:
    orch = get_orchestra()
    out = await orch.process(
        body.user_input,
        body.user_id,
        body.session_history,
        body.platform,
        body.context,
    )
    return {"ok": True, **out}
