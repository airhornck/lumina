"""渐进式内容生成检查入口。"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from orchestra.required_fields import (
    DEFAULT_CONTENT_CONFIG,
    ContentGenerationIntent,
    ProgressiveCheckResult,
    build_clarification_reply,
    get_missing_fields,
    infer_collected_info,
)


class ProgressiveGenerationGuard:
    """内容生成前的信息完整性检查器。"""

    def __init__(
        self,
        enabled: bool | None = None,
        max_clarification_rounds: int = 2,
        required_fields: Optional[List[str]] = None,
    ) -> None:
        if enabled is None:
            enabled = os.environ.get(
                "LUMINA_ENABLE_PROGRESSIVE_GENERATION", "true"
            ).lower() in ("true", "1", "yes")
        self._enabled = enabled
        self._max_clarification_rounds = max_clarification_rounds
        self._required_fields = required_fields or [
            "topic",
            "platform",
            "style",
            "target_audience",
            "content_goal",
        ]

    async def check(
        self,
        user_input: str,
        intent: ContentGenerationIntent,
        session_history: Optional[List[Dict[str, Any]]] = None,
        clarification_count: int = 0,
    ) -> ProgressiveCheckResult:
        """检查内容生成意图是否具备足够信息。

        Args:
            user_input: 用户当前输入
            intent: 内容生成意图
            session_history: 历史对话
            clarification_count: 本轮已追问次数

        Returns:
            ProgressiveCheckResult: 检查结果
        """
        if not self._enabled:
            return ProgressiveCheckResult(is_complete=True)

        # 合并 intent 中已提供的字段
        collected: Dict[str, Any] = {
            k: v
            for k, v in intent.__dict__.items()
            if k in self._required_fields and v is not None
        }

        # 从输入和历史中推断
        inferred = infer_collected_info(user_input, session_history or [])
        for k, v in inferred.items():
            if k not in collected or collected[k] is None:
                collected[k] = v

        missing = get_missing_fields(collected, self._required_fields)

        # 如果追问次数已达上限，使用默认值完成
        if clarification_count >= self._max_clarification_rounds:
            for field in missing:
                collected[field] = DEFAULT_CONTENT_CONFIG.get(field)
            return ProgressiveCheckResult(
                is_complete=True,
                collected=collected,
                missing=[],
                reply="",
                use_defaults=True,
            )

        if missing:
            return ProgressiveCheckResult(
                is_complete=False,
                collected=collected,
                missing=missing,
                reply=build_clarification_reply(missing),
            )

        return ProgressiveCheckResult(
            is_complete=True,
            collected=collected,
            missing=[],
            reply="",
        )
