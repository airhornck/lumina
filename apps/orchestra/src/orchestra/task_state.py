"""任务状态机：跟踪复杂多轮任务的进度。"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# 任务类型定义：触发条件 -> 默认步骤
TASK_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "account_growth": {
        "patterns": r"运营账号|涨粉|帮我运营|整体运营",
        "steps": [
            {"id": "diagnosis", "label": "账号诊断", "status": "pending"},
            {"id": "positioning", "label": "定位优化", "status": "pending"},
            {"id": "topic", "label": "选题推荐", "status": "pending"},
            {"id": "content", "label": "内容生成", "status": "pending"},
        ],
    },
    "content_planning": {
        "patterns": r"一周规划|内容日历|内容规划|选题日历|排期",
        "steps": [
            {"id": "topic", "label": "选题推荐", "status": "pending"},
            {"id": "content", "label": "内容生成", "status": "pending"},
            {"id": "schedule", "label": "发布排期", "status": "pending"},
        ],
    },
    "traffic_optimization": {
        "patterns": r"流量下降|流量不好|提升流量|优化流量|曝光低",
        "steps": [
            {"id": "data_collection", "label": "数据收集", "status": "pending"},
            {"id": "diagnosis", "label": "流量诊断", "status": "pending"},
            {"id": "optimization", "label": "优化建议", "status": "pending"},
        ],
    },
    "brand_positioning": {
        "patterns": r"定位|人设|赛道|IP打造|账号方向",
        "steps": [
            {"id": "positioning", "label": "定位优化", "status": "pending"},
            {"id": "topic", "label": "选题推荐", "status": "pending"},
            {"id": "content", "label": "内容生成", "status": "pending"},
        ],
    },
}


@dataclass
class TaskState:
    """任务状态对象。"""

    task_id: str
    task_type: str
    status: str
    current_step: str
    steps: List[Dict[str, Any]]
    collected_info: Dict[str, Any] = field(default_factory=dict)
    next_action: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS task_states (
    id BIGSERIAL PRIMARY KEY,
    task_id UUID NOT NULL UNIQUE,
    user_id VARCHAR(128) NOT NULL,
    conversation_id VARCHAR(128) NOT NULL,
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    current_step VARCHAR(64) NOT NULL,
    steps JSONB NOT NULL,
    collected_info JSONB NOT NULL DEFAULT '{}',
    next_action VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_states_user_conv_active
    ON task_states (user_id, conversation_id, status)
    WHERE status IN ('pending', 'in_progress');
"""


class TaskStateManager:
    """任务状态管理器。"""

    def __init__(
        self,
        dsn: str | None = None,
        pool: Any | None = None,
        enabled: bool | None = None,
    ) -> None:
        if enabled is None:
            enabled = os.environ.get("LUMINA_ENABLE_TASK_STATE", "true").lower() in (
                "true",
                "1",
                "yes",
            )
        self._enabled = enabled
        self._dsn = dsn
        self._pool = pool
        self._initialized = False
        self._memory_states: Dict[tuple[str, str], TaskState] = {}

    def _get_pool(self) -> Any | None:
        if self._pool is not None:
            return self._pool
        from infra.db import get_pool

        return get_pool()

    async def _ensure_schema(self) -> bool:
        if self._initialized:
            return True
        pool = self._get_pool()
        if pool is None:
            return False
        try:
            async with pool.acquire() as conn:
                await conn.execute(_CREATE_TABLE_SQL)
            self._initialized = True
            return True
        except Exception as e:
            logger.warning("Failed to ensure task_states schema: %s", e)
            return False

    def _detect_task_type(
        self, user_input: str, intent: Dict[str, Any]
    ) -> str | None:
        """根据用户输入和意图检测任务类型。"""
        import re

        text = (user_input or "").strip()
        kind = intent.get("kind", "")

        # 基于关键词匹配
        for task_type, definition in TASK_DEFINITIONS.items():
            if re.search(definition["patterns"], text, re.I):
                return task_type

        # 基于意图 + 特定关键词
        if kind == "topic" and re.search(r"规划|日历|一周|排期", text, re.I):
            return "content_planning"

        if kind == "diagnosis" and re.search(r"全面|整体|系统", text, re.I):
            return "account_growth"

        return None

    def _build_initial_state(
        self, user_id: str, conversation_id: str, task_type: str
    ) -> TaskState:
        steps = [
            {**step, "status": "pending"}
            for step in TASK_DEFINITIONS[task_type]["steps"]
        ]
        if steps:
            steps[0]["status"] = "in_progress"
        first_step = steps[0]["id"] if steps else ""
        return TaskState(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            status="in_progress",
            current_step=first_step,
            steps=steps,
            next_action=f"do_{first_step}" if first_step else None,
        )

    async def get_active_task(
        self, user_id: str, conversation_id: str
    ) -> TaskState | None:
        if not self._enabled:
            return None

        # 内存优先
        key = (user_id, conversation_id)
        mem_state = self._memory_states.get(key)
        if mem_state and mem_state.status in ("pending", "in_progress"):
            return mem_state

        # 数据库
        if not await self._ensure_schema():
            return mem_state if mem_state and mem_state.status in ("pending", "in_progress") else None

        pool = self._get_pool()
        if pool is None:
            return mem_state if mem_state and mem_state.status in ("pending", "in_progress") else None

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT task_id, task_type, status, current_step, steps,
                           collected_info, next_action, created_at, updated_at
                    FROM task_states
                    WHERE user_id = $1 AND conversation_id = $2
                      AND status IN ('pending', 'in_progress')
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    user_id,
                    conversation_id,
                )
                if row:
                    state = TaskState(
                        task_id=str(row["task_id"]),
                        task_type=row["task_type"],
                        status=row["status"],
                        current_step=row["current_step"],
                        steps=row["steps"],
                        collected_info=row["collected_info"] or {},
                        next_action=row["next_action"],
                        created_at=row["created_at"].isoformat() if row["created_at"] else "",
                        updated_at=row["updated_at"].isoformat() if row["updated_at"] else "",
                    )
                    self._memory_states[key] = state
                    return state
        except Exception as e:
            logger.warning("Failed to get active task from postgres: %s", e)

        return None

    async def get_task(self, user_id: str, conversation_id: str) -> TaskState | None:
        """获取任意状态的任务（包括 completed/cancelled）。"""
        key = (user_id, conversation_id)
        mem_state = self._memory_states.get(key)
        if mem_state:
            return mem_state

        if not await self._ensure_schema():
            return None

        pool = self._get_pool()
        if pool is None:
            return None

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT task_id, task_type, status, current_step, steps,
                           collected_info, next_action, created_at, updated_at
                    FROM task_states
                    WHERE user_id = $1 AND conversation_id = $2
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    user_id,
                    conversation_id,
                )
                if row:
                    return TaskState(
                        task_id=str(row["task_id"]),
                        task_type=row["task_type"],
                        status=row["status"],
                        current_step=row["current_step"],
                        steps=row["steps"],
                        collected_info=row["collected_info"] or {},
                        next_action=row["next_action"],
                        created_at=row["created_at"].isoformat() if row["created_at"] else "",
                        updated_at=row["updated_at"].isoformat() if row["updated_at"] else "",
                    )
        except Exception as e:
            logger.warning("Failed to get task from postgres: %s", e)

        return None

    async def get_or_create_task(
        self,
        user_id: str,
        conversation_id: str,
        user_input: str,
        intent: Dict[str, Any],
    ) -> TaskState | None:
        if not self._enabled:
            return None

        # 检查是否有进行中的任务
        existing = await self.get_active_task(user_id, conversation_id)
        if existing:
            return existing

        # 检测是否需要新建任务
        task_type = self._detect_task_type(user_input, intent)
        if task_type is None:
            return None

        state = self._build_initial_state(user_id, conversation_id, task_type)
        key = (user_id, conversation_id)
        self._memory_states[key] = state

        if await self._ensure_schema():
            pool = self._get_pool()
            if pool is not None:
                try:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO task_states
                            (task_id, user_id, conversation_id, task_type, status,
                             current_step, steps, collected_info, next_action)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            """,
                            state.task_id,
                            user_id,
                            conversation_id,
                            state.task_type,
                            state.status,
                            state.current_step,
                            state.steps,
                            state.collected_info,
                            state.next_action,
                        )
                except Exception as e:
                    logger.warning("Failed to create task in postgres: %s", e)

        return state

    async def _save_state(self, state: TaskState, user_id: str, conversation_id: str) -> None:
        state.updated_at = datetime.now(timezone.utc).isoformat()
        key = (user_id, conversation_id)
        self._memory_states[key] = state

        if not await self._ensure_schema():
            return

        pool = self._get_pool()
        if pool is None:
            return

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE task_states
                    SET status = $1,
                        current_step = $2,
                        steps = $3,
                        collected_info = $4,
                        next_action = $5,
                        updated_at = NOW()
                    WHERE task_id = $6
                    """,
                    state.status,
                    state.current_step,
                    state.steps,
                    state.collected_info,
                    state.next_action,
                    state.task_id,
                )
        except Exception as e:
            logger.warning("Failed to update task in postgres: %s", e)

    async def advance_step(
        self,
        user_id: str,
        conversation_id: str,
        action: str = "complete",
        collected_info: Dict[str, Any] | None = None,
    ) -> TaskState:
        """推进任务步骤。

        Args:
            action: complete / skip / pause / cancel
        """
        state = await self.get_active_task(user_id, conversation_id)
        if state is None:
            raise ValueError("No active task found")

        if collected_info:
            state.collected_info.update(collected_info)

        if action == "cancel":
            state.status = "cancelled"
            await self._save_state(state, user_id, conversation_id)
            return state

        if action == "pause":
            state.status = "paused"
            await self._save_state(state, user_id, conversation_id)
            return state

        # 标记当前步骤
        for step in state.steps:
            if step["id"] == state.current_step:
                step["status"] = "completed" if action == "complete" else "skipped"
                break

        # 找下一个 pending 步骤
        next_step = None
        found_current = False
        for step in state.steps:
            if step["id"] == state.current_step:
                found_current = True
                continue
            if found_current and step["status"] == "pending":
                next_step = step["id"]
                break

        # 如果没有找到，从头找 pending
        if next_step is None:
            for step in state.steps:
                if step["status"] == "pending":
                    next_step = step["id"]
                    break

        if next_step is None:
            state.status = "completed"
            state.current_step = ""
            state.next_action = None
        else:
            state.current_step = next_step
            state.next_action = f"do_{next_step}"
            for step in state.steps:
                if step["id"] == next_step:
                    step["status"] = "in_progress"
                    break

        await self._save_state(state, user_id, conversation_id)
        return state

    async def cancel_task(self, user_id: str, conversation_id: str) -> TaskState:
        return await self.advance_step(user_id, conversation_id, action="cancel")
