"""system-chat 统一入口：Hermes 引擎唯一链路。

SSE 事件契约（v2）由 `services.hermes_adapter.HermesEngineAdapter` 产出：
start → thinking_delta*/tool_start*/tool_complete*/assistant_delta*
      → export_link*/compliance_report? → done(usage/reply_ms/payload)

改造计划：
- 阶段一 P0-2: 根据 conversation_id 查询历史 ✅（已实现）
- 阶段一 P0-3: 历史消息拼入 LLM prompt ✅（已实现）
- 阶段二 P0-9: 画像更新策略
- 阶段二 P0-12: 平台变更检测
- 阶段五 P1-8/P1-9: 短消息意图补全
- 阶段六 P2-3: 日志增强字段（session_round, platform_source 等）
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List

from services.memory_service import ServiceMemoryStore
from services.platform_utils import resolve_platform_for_request, detect_platform_change_in_message
from services.conversation_profile_service import (
    ConversationProfile,
    get_profile_service,
)
from services.intent_completion import (
    complete_intent,
    needs_confirmation,
    is_likely_referencing,
)

logger = logging.getLogger(__name__)


def _memory_rows_to_session(rows: List[dict[str, Any]], limit: int = 24) -> List[Dict[str, Any]]:
    """将数据库行转换为 session history 格式（取最近 limit 条）。"""
    out: List[Dict[str, Any]] = []
    for r in rows:
        if r.get("role") not in ("user", "assistant"):
            continue
        c = r.get("content")
        if not isinstance(c, str):
            continue
        out.append({"role": r["role"], "content": c})
    return out[-limit:]


async def handle_system_chat_stream(
    user_id: str,
    conversation_id: str,
    message: str,
    platform: str | None,
    context: Dict[str, Any],
    store: ServiceMemoryStore,
    stream_format: int = 2,
) -> AsyncIterator[str]:
    """system-chat SSE 流：记忆读写 + 画像管理 + 委托 Hermes 适配器。

    stream_format 仅保留签名兼容；v2 为唯一产出格式。
    """
    service = "system-chat"
    # 只取最近 24 条注入 LLM（下方 _memory_rows_to_session 同值），读取量与历史总量脱钩
    history_before = await store.list_messages(user_id, conversation_id, service, limit=24)
    await store.append(user_id, conversation_id, service, "user", message)

    hist_rows = [
        r
        for r in history_before
        if r.get("role") in ("user", "assistant") and isinstance(r.get("content"), str)
    ]
    session_history = _memory_rows_to_session(hist_rows)

    # 会话轮数（用于日志增强 P2-3）
    total_count = await store.count_messages(user_id, conversation_id, service)
    session_round = (total_count + 1) // 2  # user + assistant 为 1 轮

    # ---------------------------------------------------------------
    # 阶段五 P1-8/P1-9: 短消息意图补全
    # ---------------------------------------------------------------
    intent_completed = False
    if session_history and is_likely_referencing(message):
        completion = complete_intent(message, session_history)
        if completion:
            logger.info(
                "Intent completed for user=%s: message=%r -> %r",
                user_id, message[:50], completion[:80],
            )
            # 补全后的内容作为系统提示的一部分传给模型
            message = completion
            intent_completed = True
        elif needs_confirmation(message, ""):
            # 低置信度，但继续走正常流程，system prompt 中有指代消解提示
            pass

    # ---------------------------------------------------------------
    # 阶段二 P0-9/P0-12: 画像持久化 + 平台变更检测
    # ---------------------------------------------------------------
    profile_service = get_profile_service()

    # 1. 先从当前消息提取平台并更新画像（让画像信息立即可用）
    extracted_platform = await profile_service.extract_and_update_from_message(
        user_id, conversation_id, message
    )

    # 2. 读取已有画像
    profile = await profile_service.get_profile(user_id, conversation_id)

    # 3. 平台解析：画像 > 显式传入 > 当前消息 > 历史
    #    resolve_platform_for_request 的优先级已经覆盖了 explicit/current_message/history/inferred
    #    这里把画像中的 platform 作为最高优先级传入
    profile_platform = profile.platform if profile else None

    # 如果用户消息明确提到了新平台，检测平台变更
    platform_changed = False
    old_platform = None
    if extracted_platform and profile_platform and extracted_platform != profile_platform:
        old_platform = profile_platform
        platform_changed = True
        logger.info(
            "Platform change detected for user=%s conv=%s: %s -> %s",
            user_id, conversation_id, old_platform, extracted_platform,
        )

    # 平台解析优先级：画像平台（非用户切换时）> explicit > current_message > history > inferred
    # 只有用户明确切换时用 extracted_platform，否则用画像平台
    if profile_platform and not platform_changed:
        # 画像已有平台，且用户没有声明新平台 → 用画像平台
        resolved_platform = profile_platform
        platform_source = "profile"
    else:
        # 走原逻辑
        resolved_platform, platform_source = resolve_platform_for_request(
            message, session_history, platform
        )
        # 如果从 current_message 提取到了平台，也更新画像
        if platform_source == "current_message" and resolved_platform:
            await profile_service.upsert_profile(
                user_id, conversation_id, platform=resolved_platform
            )
        elif platform_source == "history" and resolved_platform:
            await profile_service.upsert_profile(
                user_id, conversation_id, platform=resolved_platform
            )

    # 4. 记录平台来源（日志增强 P2-3）
    if profile and profile.platform and not platform_changed:
        platform_source = "profile"

    async def _append_assistant(content: str) -> None:
        await store.append(user_id, conversation_id, service, "assistant", content)

    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(append_assistant=_append_assistant)
    async for line in adapter.chat_stream(
        user_message=message,
        user_id=user_id,
        conversation_id=conversation_id,
        session_history=session_history,
        platform=resolved_platform,
        context=context,
        platform_source=platform_source,
        conversation_profile=profile,
        session_round=session_round,
        intent_completed=intent_completed,
    ):
        yield line

    # ---------------------------------------------------------------
    # 流结束后：根据实际工具调用情况更新画像
    # 注：工具调用信息在 hermes_adapter 的 _EventBridge 中捕获，
    # 但为了不侵入适配器架构，画像的细粒度更新在对话日志层面完成。
    # ---------------------------------------------------------------
