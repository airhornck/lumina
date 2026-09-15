"""Phase 0 TDD Harness：任务状态机 Red 状态测试。"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def manager():
    from orchestra.task_state import TaskStateManager

    return TaskStateManager(dsn=None)


async def test_create_account_growth_task(manager):
    state = await manager.get_or_create_task(
        user_id="test-user",
        conversation_id="test-conv",
        user_input="帮我运营账号",
        intent={"kind": "conversation"},
    )
    assert state is not None
    assert state.task_type == "account_growth"
    assert state.current_step == "diagnosis"
    assert len(state.steps) == 4


async def test_resume_existing_task(manager):
    await manager.get_or_create_task(
        user_id="test-user",
        conversation_id="test-conv",
        user_input="帮我运营账号",
        intent={"kind": "conversation"},
    )
    state = await manager.get_active_task("test-user", "test-conv")
    assert state is not None
    assert state.task_type == "account_growth"


async def test_skip_step(manager):
    await manager.get_or_create_task(
        user_id="test-user",
        conversation_id="test-conv",
        user_input="帮我运营账号",
        intent={"kind": "conversation"},
    )
    updated = await manager.advance_step(
        "test-user", "test-conv", action="skip"
    )
    assert updated.current_step == "positioning"
    assert any(s["id"] == "diagnosis" and s["status"] == "skipped" for s in updated.steps)


async def test_cancel_task(manager):
    await manager.get_or_create_task(
        user_id="test-user",
        conversation_id="test-conv",
        user_input="帮我运营账号",
        intent={"kind": "conversation"},
    )
    state = await manager.cancel_task("test-user", "test-conv")
    assert state.status == "cancelled"


async def test_complete_all_steps(manager):
    await manager.get_or_create_task(
        user_id="test-user",
        conversation_id="test-conv",
        user_input="帮我运营账号",
        intent={"kind": "conversation"},
    )
    for _ in range(4):
        await manager.advance_step("test-user", "test-conv", action="complete")
    state = await manager.get_active_task("test-user", "test-conv")
    assert state is None  # completed 不是 active
    final = await manager.get_task("test-user", "test-conv")
    assert final.status == "completed"


async def test_no_task_for_simple_intent(manager):
    state = await manager.get_or_create_task(
        user_id="test-user",
        conversation_id="test-conv-2",
        user_input="帮我写文案",
        intent={"kind": "content"},
    )
    assert state is None


async def test_disable_flag_returns_none():
    from orchestra.task_state import TaskStateManager

    manager = TaskStateManager(dsn=None, enabled=False)
    state = await manager.get_or_create_task(
        user_id="test-user",
        conversation_id="test-conv",
        user_input="帮我运营账号",
        intent={"kind": "conversation"},
    )
    assert state is None
