from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ServiceStreamRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128, description="用户唯一标识")
    conversation_id: str = Field(..., min_length=1, max_length=128, description="对话唯一标识")
    message: str = Field(..., min_length=1, max_length=32000, description="用户当前输入")
    platform: Optional[str] = Field(default=None, description="可选平台上下文，如 xiaohongshu / douyin")
    context: Dict[str, Any] = Field(default_factory=dict, description="业务上下文（行业、指标、DNA 等）")
    mode: Optional[str] = Field(default=None, description="子模式，仅定位服务使用：case / matrix")
