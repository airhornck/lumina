"""Phase 0 TDD Harness：任务状态机 PostgreSQL 路径 mock 测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


pytestmark = pytest.mark.asyncio


class _FakeRow:
    def __init__(self, **kwargs):
        self._data = kwargs

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key):
        return self._data.get(key)


def _make_pool(active_row=None):
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=active_row)

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


def _active_task_row():
    return _FakeRow(
        task_id="task-1",
        task_type="account_growth",
        status="in_progress",
        current_step="diagnosis",
        steps=[
            {"id": "diagnosis", "label": "账号诊断", "status": "in_progress"},
            {"id": "positioning", "label": "定位优化", "status": "pending"},
        ],
        collected_info={"platform": "xiaohongshu"},
        next_action="do_diagnosis",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


async def test_task_manager_get_active_task_from_postgres():
    from orchestra.task_state import TaskStateManager

    pool, conn = _make_pool(active_row=_active_task_row())
    manager = TaskStateManager(pool=pool)

    state = await manager.get_active_task("u1", "c1")
    assert state is not None
    assert state.task_type == "account_growth"
    assert state.current_step == "diagnosis"
    assert conn.fetchrow.called


async def test_task_manager_create_task_saves_to_postgres():
    from orchestra.task_state import TaskStateManager

    pool, conn = _make_pool()
    manager = TaskStateManager(pool=pool)

    state = await manager.get_or_create_task(
        user_id="u1",
        conversation_id="c1",
        user_input="帮我运营账号",
        intent={"kind": "conversation"},
    )
    assert state is not None
    assert state.task_type == "account_growth"
    assert conn.execute.called


async def test_task_manager_advance_step_updates_postgres():
    from orchestra.task_state import TaskStateManager

    pool, conn = _make_pool(active_row=_active_task_row())
    manager = TaskStateManager(pool=pool)

    await manager.get_active_task("u1", "c1")
    updated = await manager.advance_step("u1", "c1", action="complete")
    assert updated.current_step == "positioning"
    assert conn.execute.called


async def test_task_manager_cancel_updates_postgres():
    from orchestra.task_state import TaskStateManager

    pool, conn = _make_pool(active_row=_active_task_row())
    manager = TaskStateManager(pool=pool)

    state = await manager.cancel_task("u1", "c1")
    assert state.status == "cancelled"
    assert conn.execute.called


async def test_task_manager_get_completed_task():
    from orchestra.task_state import TaskStateManager

    completed_row = _FakeRow(
        task_id="task-1",
        task_type="account_growth",
        status="completed",
        current_step="",
        steps=[],
        collected_info={},
        next_action=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pool, conn = _make_pool(active_row=None)
    conn.fetchrow = AsyncMock(side_effect=[completed_row])
    manager = TaskStateManager(pool=pool)

    state = await manager.get_task("u1", "c1")
    assert state is not None
    assert state.status == "completed"
