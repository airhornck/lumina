from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class ServiceStreamRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128, description="用户唯一标识")
    conversation_id: str = Field(..., min_length=1, max_length=128, description="对话唯一标识")
    message: str = Field(..., min_length=1, max_length=32000, description="用户当前输入")
    platform: Optional[str] = Field(default=None, description="可选平台上下文，如 xiaohongshu / douyin")
    context: Dict[str, Any] = Field(default_factory=dict, description="业务上下文（行业、指标、DNA 等）")
    mode: Optional[str] = Field(default=None, description="子模式，仅定位服务使用：case / matrix")
    stream_format: Optional[int] = Field(
        default=None,
        description="1=v1 SSE；2=v2（仅 system-chat 生效）。缺省时可读 X-Lumina-Stream-Format；均未指定则 1",
    )

    @field_validator("stream_format")
    @classmethod
    def _validate_stream_format(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v not in (1, 2):
            raise ValueError("stream_format must be 1 or 2")
        return v
