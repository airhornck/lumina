"""Hermes 引擎适配器：将 Hermes 包装为 Lumina SSE 流。

Phase 4 P0 重写（docs/specs/phase4_unified_planner_deprecation_spec.md）：
- G2 多轮历史真实注入 run_conversation(conversation_history=...)
- G3 真流式 stream_delta_callback + thinking/tool 事件桥接（禁止假流式）
- G4 persona（data/hermes/personas/lumina-marketing.md）与 LuminaMemoryProvider 注入
- 接口兼容：start/assistant_delta/export_link/compliance_report/done 事件序列与
  字段保持 SSE v2 契约（spec §4.4），thinking_delta/tool_start/tool_complete 仅追加
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_HERMES_VENDOR_DIR = _PROJECT_ROOT / "vendor" / "hermes-agent"
_HERMES_HOME = _PROJECT_ROOT / "data" / "hermes"
_PERSONA_PATH = _HERMES_HOME / "personas" / "lumina-marketing.md"

_PERSONA_CACHE: Optional[str] = None


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _ensure_hermes_importable() -> None:
    """将 vendor/hermes-agent 追加到 sys.path 末尾（不遮蔽 Lumina 顶层包）。"""
    p = str(_HERMES_VENDOR_DIR)
    if _HERMES_VENDOR_DIR.is_dir() and p not in sys.path:
        sys.path.append(p)


def _load_persona() -> Optional[str]:
    """加载 Lumina 营销助手人设（缓存）；文件缺失时返回 None。"""
    global _PERSONA_CACHE
    if _PERSONA_CACHE is not None:
        return _PERSONA_CACHE or None
    try:
        _PERSONA_CACHE = _PERSONA_PATH.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning("Failed to load Hermes persona %s: %s", _PERSONA_PATH, e)
        _PERSONA_CACHE = ""
    return _PERSONA_CACHE or None


def _load_fallback_api_key() -> str:
    """DEEPSEEK_API_KEY 缺省时，从 data/hermes/config.yaml 的
    lumina.fallback_api_key 读取（镜像内置私有部署场景）。"""
    try:
        cfg = _HERMES_HOME / "config.yaml"
        for line in cfg.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("fallback_api_key:"):
                return s.split(":", 1)[1].strip().strip('"').strip("'")
    except Exception as e:
        logger.warning("Failed to read fallback api key from %s: %s", _HERMES_HOME, e)
    return ""


async def _stream_text_chunks(text: str, chunk_size: int = 96) -> AsyncIterator[str]:
    """仅供 mock 路径使用（真实路径禁止假流式）。"""
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
        await asyncio.sleep(0)


def _json_safe(obj: Any, limit: int = 2000) -> Any:
    """将工具参数/结果裁剪为可 JSON 序列化且体积可控的结构。"""
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    if len(s) > limit:
        s = s[:limit] + "…"
    try:
        return json.loads(s) if not s.endswith("…") else s
    except Exception:
        return s


# 模型偶尔会模仿 hermes 约定，在正文中输出 <think>/<lumina_think>/<REASONING_SCRATCHPAD>
# 等内部思考块；hermes 只在最终文本中清洗，流式 delta 会漏给用户，需在适配层过滤。
_THINK_TAG_NAMES = {"think", "thinking", "reasoning", "lumina_think", "reasoning_scratchpad"}


class _StreamThinkFilter:
    """增量过滤流式文本中的思考标签块（标签可跨 delta 拆分）。"""

    def __init__(self) -> None:
        self._buf = ""
        self._in_think = False

    def feed(self, text: str) -> str:
        self._buf += text
        out: list[str] = []
        while self._buf:
            if self._in_think:
                close_idx = self._buf.find("</")
                if close_idx == -1:
                    # 保留可能是不完整关闭标签的尾部
                    self._buf = self._buf[-1:] if self._buf.endswith("<") else ""
                    break
                end = self._buf.find(">", close_idx)
                if end == -1:
                    self._buf = self._buf[close_idx:]
                    break
                name = self._buf[close_idx + 2 : end].strip().lower().rstrip("/").strip()
                self._buf = self._buf[end + 1 :]
                if name in _THINK_TAG_NAMES:
                    self._in_think = False
                continue
            lt = self._buf.find("<")
            if lt == -1:
                # 无 '<'，全量输出
                out.append(self._buf)
                self._buf = ""
                break
            out.append(self._buf[:lt])
            self._buf = self._buf[lt:]
            gt = self._buf.find(">")
            if gt == -1:
                # 标签未完整，等待下一个 delta（限制缓冲防爆）
                if len(self._buf) > 256:
                    out.append(self._buf)
                    self._buf = ""
                break
            raw = self._buf[1:gt]
            is_close = raw.strip().startswith("/")
            name = raw.strip().lstrip("/").strip().lower()
            self._buf = self._buf[gt + 1 :]
            if name in _THINK_TAG_NAMES and not is_close:
                self._in_think = True
            elif name in _THINK_TAG_NAMES and is_close:
                pass  # 无匹配的关闭标签，丢弃
            else:
                out.append(f"<{raw}>")
        return "".join(out)

    def flush(self) -> str:
        """流结束时冲刷残余缓冲。"""
        if self._in_think:
            self._buf = ""
            return ""
        rest = self._buf
        self._buf = ""
        return rest


class _EventBridge:
    """把 Hermes 工作线程中的同步回调桥接为 asyncio.Queue 事件。"""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self.queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._tool_start_times: Dict[str, float] = {}
        self.received_deltas = False
        self._think_filter = _StreamThinkFilter()
        # 工具结果中收集的业务数据（spec §4.4 export_link/compliance_report）
        self.export_urls: List[Dict[str, Any]] = []
        self.compliance: Optional[Dict[str, Any]] = None

    def _push(self, obj: Dict[str, Any]) -> None:
        try:
            self._loop.call_soon_threadsafe(self.queue.put_nowait, obj)
        except RuntimeError:  # loop 已关闭（客户端断连等）
            pass

    # ---- Hermes 回调（签名对齐 agent/tool_executor.py 与 chat_completion_helpers.py）----

    def on_stream_delta(self, text: Optional[str]) -> None:
        if not text:
            return
        clean = self._think_filter.feed(text)
        if clean:
            self.received_deltas = True
            self._push({"type": "assistant_delta", "text": clean})

    def flush_think_filter(self) -> Optional[str]:
        """流末尾冲刷思考过滤器残余（返回的文本应作为最后一个 delta 下发）。"""
        rest = self._think_filter.flush()
        return rest or None

    def on_reasoning(self, text: Optional[str]) -> None:
        if text:
            self._push({"type": "thinking_delta", "text": text})

    def on_thinking(self, text: Optional[str]) -> None:
        if text:
            self._push({"type": "thinking_delta", "text": text})

    def on_tool_start(self, call_id: str, name: str, args: Any) -> None:
        self._tool_start_times[call_id] = time.monotonic()
        self._push({"type": "tool_start", "tool": name, "args": _json_safe(args)})

    def on_tool_complete(self, call_id: str, name: str, args: Any, result: Any) -> None:
        started = self._tool_start_times.pop(call_id, None)
        elapsed_ms = int((time.monotonic() - started) * 1000) if started else 0
        ok = True
        if isinstance(result, str) and '"ok": false' in result.lower():
            ok = False
        # 从工具结果中提取业务数据（export_urls / compliance），
        # 由 chat_stream 在回复文本后转换为 SSE 业务事件
        data: Any = None
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except Exception:
                data = None
        elif isinstance(result, dict):
            data = result
        if isinstance(data, dict):
            urls = data.get("export_urls")
            if isinstance(urls, list):
                self.export_urls.extend(u for u in urls if isinstance(u, dict))
            comp = data.get("compliance")
            if isinstance(comp, dict) and comp:
                self.compliance = comp
        self._push(
            {
                "type": "tool_complete",
                "tool": name,
                "ok": ok,
                "elapsed_ms": elapsed_ms,
            }
        )


class _LuminaMemoryFacade:
    """将 async 的 LuminaMemoryProvider 包装为 hermes MemoryManager 期望的同步接口。

    hermes MemoryProvider ABC 中 sync_turn/handle_tool_call 均为同步方法，
    MemoryManager.sync_all/handle_tool_call 不会 await，直接传入 async 实现会
    产生 never-awaited 协程。门面在此做同步桥接；写库仍由 router/adapter 负责，
    sync_turn 一律 no-op。
    """

    def __init__(self, provider: Any) -> None:
        self._p = provider

    @property
    def name(self) -> str:
        return self._p.name

    def is_available(self) -> bool:
        return self._p.is_available()

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        return self._p.initialize(session_id, **kwargs)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return self._p.get_tool_schemas()

    def system_prompt_block(self) -> str:
        return ""

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        return ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        return None

    def sync_turn(self, *args: Any, **kwargs: Any) -> None:
        return None

    def on_turn_start(self, *args: Any, **kwargs: Any) -> None:
        return None

    def on_session_end(self, *args: Any, **kwargs: Any) -> None:
        return None

    def shutdown(self) -> None:
        return None

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs: Any) -> str:
        coro = self._p.handle_tool_call(tool_name, args, **kwargs)
        loop = HermesEngineAdapter._main_loop
        if loop is not None and loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=60)
        return asyncio.run(coro)


class HermesEngineAdapter:
    """Hermes Agent 引擎适配器。"""

    # 进程级共享：agent 按 conversation_id 复用，工具全局注册一次
    _agents: Dict[str, Any] = {}
    _agents_lock = threading.Lock()
    _tools_registered = False
    _tools_lock = threading.Lock()
    _main_loop: Optional[asyncio.AbstractEventLoop] = None

    def __init__(
        self,
        use_hermes: bool | None = None,
        mock_import_error: bool = False,
        mock_exception: bool = False,
        mock_response: str | None = None,
        append_assistant: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> None:
        # Hermes 已是唯一执行引擎；use_hermes 仅保留给测试显式构造降级场景。
        if use_hermes is None:
            use_hermes = True
        self._use_hermes = use_hermes
        self._mock_import_error = mock_import_error
        self._mock_exception = mock_exception
        self._mock_response = mock_response
        # assistant 轮写库回调：缺省写 chat_debug 记忆库，services 入口可注入自有存储。
        self._append_assistant = append_assistant

    # ------------------------------------------------------------------ #
    # Agent 生命周期                                                      #
    # ------------------------------------------------------------------ #

    @classmethod
    def _register_lumina_tools(cls) -> None:
        """向 Hermes 全局 registry 注册 Lumina 工具（进程内一次）。"""
        with cls._tools_lock:
            if cls._tools_registered:
                return
            from tools.registry import registry  # type: ignore[import-not-found]
            from services.hermes_tools import handle_tool_call

            def _make_handler(tool_name: str):
                def _handler(args: Dict[str, Any], **_dispatch_kwargs: Any) -> str:
                    # hermes registry.dispatch 会附带 task_id 等 kwargs，必须接收
                    # 工具实际协程在主事件循环线程执行，而请求上下文保存在 worker 线程的
                    # threading.local 中，因此在此处捕获并显式透传。
                    # 由于并发 tool call 都会被提交到同一个主事件循环线程，
                    # 必须避免在 handler 内部再次读取 threading.local()，否则会被覆盖。
                    from services.hermes_tools import (
                        _current_user_id,
                        _current_conversation_id,
                        _current_platform,
                        _request_ctx,
                    )

                    captured_user = _current_user_id()
                    captured_conv = _current_conversation_id()
                    captured_platform = _current_platform()
                    captured_user_message = getattr(
                        _request_ctx, "last_user_message", None
                    )
                    loop = cls._main_loop
                    if loop is not None and loop.is_running():
                        future = asyncio.run_coroutine_threadsafe(
                            handle_tool_call(
                                tool_name,
                                args,
                                user_id=captured_user,
                                conversation_id=captured_conv,
                                platform=captured_platform,
                                user_message=captured_user_message,
                            ),
                            loop,
                        )
                        return future.result(timeout=180)
                    return asyncio.run(
                        handle_tool_call(
                            tool_name,
                            args,
                            user_id=captured_user,
                            conversation_id=captured_conv,
                            platform=captured_platform,
                            user_message=captured_user_message,
                        )
                    )

                return _handler

            from services.hermes_tools import get_lumina_tools
            from toolsets import create_custom_toolset

            lumina_tool_names: List[str] = []
            for tool in get_lumina_tools():
                name = tool["function"]["name"]
                lumina_tool_names.append(name)
                try:
                    registry.register(
                        name=name,
                        toolset="lumina_marketing",
                        schema=tool["function"],
                        handler=_make_handler(name),
                    )
                except Exception as e:
                    logger.warning("Failed to register Lumina tool %s: %s", name, e)
            # Hermes 的 toolset 解析只识别静态 TOOLSETS；动态注册的工具集必须显式创建，
            # 否则 enabled_toolsets=["lumina_marketing"] 会被 validate 但 resolve 为空。
            try:
                create_custom_toolset(
                    "lumina_marketing",
                    description="Lumina 营销内容生成、账号诊断、选题推荐等专用工具",
                    tools=lumina_tool_names,
                )
            except Exception as e:
                logger.warning("Failed to create lumina_marketing toolset: %s", e)
            cls._tools_registered = True

    def _wire_memory_provider(self, agent: Any, session_id: str, user_id: str) -> None:
        """注入 LuminaMemoryProvider（best-effort，失败不影响主链路）。

        sync_writes=False：写库仍由 router（user 轮）与适配器（assistant 轮）负责，
        provider 仅提供 lumina_search_memory 工具，避免重复写入。
        """
        try:
            from agent.memory_manager import MemoryManager  # type: ignore[import-not-found]
            from services.hermes_memory_provider import LuminaMemoryProvider

            if getattr(agent, "_memory_manager", None) is None:
                agent._memory_manager = MemoryManager()
            provider = LuminaMemoryProvider(sync_writes=False)
            provider.initialize(session_id=session_id, user_id=user_id)
            agent._memory_manager.add_provider(_LuminaMemoryFacade(provider))
        except Exception as e:
            logger.warning("Failed to wire LuminaMemoryProvider: %s", e)

    @staticmethod
    def _agent_cache_key(user_id: str, conversation_id: str) -> str:
        """agent 缓存键：必须按 (user_id, conversation_id) 隔离。

        仅用 conversation_id 会导致不同用户共用会话 ID 时共享同一个 AIAgent
        （hermes 内部 session 状态 + 记忆 provider 均随实例泄漏给先创建者）。
        分隔符用 "--"：session_id 会进 hermes 会话文件路径，避免 Windows 非法字符。
        """
        if conversation_id:
            return f"{user_id}--{conversation_id}"
        return f"anon-{user_id}"

    def _get_or_create_agent(self, conversation_id: str, user_id: str) -> Any:
        if self._mock_import_error:
            raise ImportError("Hermes not installed")

        _ensure_hermes_importable()
        os.environ.setdefault("HERMES_HOME", str(_HERMES_HOME))

        key = self._agent_cache_key(user_id, conversation_id)
        with self._agents_lock:
            agent = self._agents.get(key)
            if agent is not None:
                return agent

            from run_agent import AIAgent  # type: ignore[import-not-found]
            from services.hermes_security import build_safe_hermes_config

            # 必须先注册工具再构造 agent：AIAgent 在构造期快照可用工具列表，
            # 后注册的工具对该 agent 不可见（曾导致进程中首个 agent 无工具可调）
            self._register_lumina_tools()

            config = build_safe_hermes_config()
            provider = os.environ.get("LUMINA_HERMES_PROVIDER", "deepseek").strip() or "deepseek"
            model = os.environ.get("LUMINA_HERMES_MODEL", "deepseek-chat").strip() or "deepseek-chat"
            api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip() or _load_fallback_api_key()
            base_url = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com").strip()

            session_id = f"lumina-{key}"
            agent = AIAgent(
                model=model,
                provider=provider,
                api_key=api_key,
                base_url=base_url,
                enabled_toolsets=config["enabled_toolsets"],
                disabled_toolsets=config["disabled_toolsets"],
                max_iterations=config["max_iterations"],
                skip_memory=config["skip_memory"],
                skip_context_files=config["skip_context_files"],
                quiet_mode=config["quiet_mode"],
                session_id=session_id,
                user_id=user_id,
                platform="lumina",
            )
            agent._turn_lock = threading.Lock()
            self._wire_memory_provider(agent, session_id, user_id)
            self._agents[key] = agent
            return agent

    # ------------------------------------------------------------------ #
    # 主流程                                                              #
    # ------------------------------------------------------------------ #

    async def chat_stream(
        self,
        user_message: str,
        user_id: str,
        conversation_id: str,
        session_history: List[Dict[str, Any]],
        platform: str | None = None,
        context: Dict[str, Any] | None = None,
        platform_source: str = "none",
        conversation_profile: Any = None,
        session_round: int = 0,
        intent_completed: bool = False,
    ) -> AsyncIterator[str]:
        """生成 Lumina SSE 格式的流（事件契约见 spec §4.4）。

        conversation_profile: ConversationProfile 对象，用于回写画像到 system prompt
        session_round: 当前会话轮数（用于日志增强 P2-3）
        intent_completed: 是否经过意图补全（阶段五 P1-8）
        """
        from services.conversation_profile_service import ConversationProfile as _ConvProfile

        service = "system-chat"
        request_id = str(uuid.uuid4())
        t0 = time.perf_counter()

        if not self._use_hermes:
            raise RuntimeError("Hermes engine is disabled")

        yield _sse(
            {
                "type": "start",
                "service": service,
                "stream_format": 2,
                "request_id": request_id,
            }
        )

        final_response = ""
        usage: Optional[Dict[str, int]] = None
        bridge: Optional[_EventBridge] = None

        # 对话日志采集（services.conversation_log）：本轮的意图识别与工具调用证据
        # 支持由调用方传入 session_round，兼容性保留自动计算
        effective_round = session_round if session_round > 0 else (len(session_history) // 2) + 1
        rec: Dict[str, Any] = {
            "request_id": request_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "platform": platform,
            "platform_source": platform_source,
            "session_round": effective_round,
            "user_message": user_message[:2000],
            "history_len": len(session_history),
            "path": "planner",
            "tools": [],
            "thinking_preview": "",
            # 增强日志字段（阶段六 P2-3）
            "context_hit": bool(session_history),
            "tool_platform_aligned": True,  # 结束时验证
            "intent_completion": intent_completed,
        }

        def _capture(evt: Dict[str, Any]) -> None:
            etype = evt.get("type")
            if etype == "tool_start":
                rec["tools"].append(
                    {"name": evt.get("tool"), "args": evt.get("args"), "ok": None}
                )
            elif etype == "tool_complete":
                for tool in reversed(rec["tools"]):
                    if tool["name"] == evt.get("tool") and tool["ok"] is None:
                        tool["ok"] = evt.get("ok")
                        tool["elapsed_ms"] = evt.get("elapsed_ms")
                        break
                else:
                    rec["tools"].append(
                        {
                            "name": evt.get("tool"),
                            "ok": evt.get("ok"),
                            "elapsed_ms": evt.get("elapsed_ms"),
                        }
                    )
            elif etype == "thinking_delta" and len(rec["thinking_preview"]) < 500:
                rec["thinking_preview"] += str(evt.get("text") or "")

        # 关键词直连（hermes_tools.KEYWORD_TOOL_TRIGGERS）：命中即跳过 planner
        # 直接调用对应 skill，skill 内部前置自查（is_enabled/无数据澄清）照常执行。
        # 上下文不丢弃：原话与平台透传为工具参数，回复走共享记忆同步与 done 事件。
        keyword_tool: Optional[str] = None
        if not (self._mock_import_error or self._mock_exception or self._mock_response):
            from services.hermes_tools import match_keyword_tool

            keyword_tool = match_keyword_tool(user_message)

        # 平台一致性注入：在 system_message 中明确告知模型应使用哪个平台
        platform_block = ""
        if platform:
            platform_block = (
                f"\n\n【当前平台上下文】用户当前聚焦的平台是：{platform}。"
                f"除非用户明确要求切换或对比其他平台，否则所有涉及平台的工具调用（如选题推荐、内容生成、账号诊断等）"
                f"都必须使用平台 '{platform}'，不要自行推断为小红书/抖音等其他平台。"
            )

        # 画像回写（阶段二 P0-10 / 阶段四 P1-6）：将用户画像注入 system prompt
        profile_block = ""
        if conversation_profile is not None and isinstance(conversation_profile, _ConvProfile):
            profile_text = conversation_profile.format_for_prompt()
            if profile_text:
                profile_block = (
                    f"\n\n{profile_text}。"
                    "请优先使用画像中的平台信息，不要推断为其他平台。"
                )

        try:
            try:
                if self._mock_exception:
                    raise RuntimeError("Mock Hermes exception")

                if self._mock_response is not None:
                    rec["path"] = "mock"
                    final_response = self._mock_response
                    async for piece in _stream_text_chunks(final_response):
                        yield _sse({"type": "assistant_delta", "text": piece})
                elif keyword_tool is not None:
                    rec["path"] = "keyword"
                    kw_args: Dict[str, Any] = {"message": user_message}
                    if platform:
                        kw_args["platform"] = platform
                    _capture({"type": "tool_start", "tool": keyword_tool, "args": _json_safe(kw_args)})
                    yield _sse(
                        {
                            "type": "tool_start",
                            "tool": keyword_tool,
                            "args": _json_safe(kw_args),
                        }
                    )
                    t_tool = time.monotonic()
                    from services.hermes_tools import handle_tool_call

                    raw_result = await handle_tool_call(
                        keyword_tool,
                        kw_args,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        platform=platform,
                        user_message=user_message,
                    )
                    elapsed_ms = int((time.monotonic() - t_tool) * 1000)
                    tool_ok = True
                    reply_text = ""
                    try:
                        data = json.loads(raw_result)
                        tool_ok = bool(data.get("ok", True))
                        reply_text = str((data.get("result") or {}).get("reply") or "")
                    except Exception:
                        tool_ok = False
                    if not reply_text:
                        # spec §十 护栏2：失败降级为自然语言致歉，不再降级执行其他工具
                        tool_ok = False
                        reply_text = "抱歉，该功能暂时不可用，请稍后再试。"
                    _capture(
                        {
                            "type": "tool_complete",
                            "tool": keyword_tool,
                            "ok": tool_ok,
                            "elapsed_ms": elapsed_ms,
                        }
                    )
                    yield _sse(
                        {
                            "type": "tool_complete",
                            "tool": keyword_tool,
                            "ok": tool_ok,
                            "elapsed_ms": elapsed_ms,
                        }
                    )
                    final_response = reply_text
                    async for piece in _stream_text_chunks(reply_text):
                        yield _sse({"type": "assistant_delta", "text": piece})
                else:
                    agent = self._get_or_create_agent(conversation_id, user_id)

                    # 多轮历史真实注入（G2）
                    conversation_history = []
                    for msg in session_history:
                        role = msg.get("role")
                        content = msg.get("content")
                        if role in ("user", "assistant") and isinstance(content, str):
                            conversation_history.append({"role": role, "content": content})

                    loop = asyncio.get_running_loop()
                    HermesEngineAdapter._main_loop = loop
                    bridge = _EventBridge(loop)
                    persona = _load_persona()

                    def _usage_snapshot() -> Dict[str, int]:
                        return {
                            "prompt_tokens": int(getattr(agent, "session_prompt_tokens", 0) or 0),
                            "completion_tokens": int(
                                getattr(agent, "session_completion_tokens", 0) or 0
                            ),
                            "total_tokens": int(getattr(agent, "session_total_tokens", 0) or 0),
                        }

                    def _run() -> Dict[str, Any]:
                        from services.hermes_tools import set_request_context

                        # 组装注入模型的 system prompt：人设 + 平台上下文 + 画像回写 + 指代消解提示
                        effective_system = persona or ""
                        effective_system += platform_block
                        effective_system += profile_block
                        # 强制工具调用：内容生成类需求必须走 lumina_generate_content，避免模型直接回复
                        effective_system += (
                            "\n\n【工具调用强制规则】当用户要求你生成/写作/创作任何平台内容"
                            "（如笔记、文案、脚本、种草内容、标题等）时，"
                            "你必须直接调用 lumina_generate_content 工具完成，"
                            "不要先向用户提问，也不要仅凭自身知识直接输出全文。"
                        )
                        if session_history:
                            effective_system += (
                                "\n\n【对话连续性提示】当前对话已有历史上下文。"
                                "用户可能会使用省略表达或指代前文（如「那么图文的呢」「接上一个问题」「刚才那个」等）。"
                                "请结合完整对话历史理解用户意图，不要当作新话题处理。"
                                "如果你不确定用户指代的内容，请礼貌地确认，不要编造。"
                            )

                        with agent._turn_lock:
                            set_request_context(user_id, conversation_id, platform, user_message)
                            agent.stream_delta_callback = bridge.on_stream_delta
                            agent.reasoning_callback = bridge.on_reasoning
                            agent.thinking_callback = bridge.on_thinking
                            agent.tool_start_callback = bridge.on_tool_start
                            agent.tool_complete_callback = bridge.on_tool_complete
                            try:
                                return agent.run_conversation(
                                    user_message,
                                    system_message=effective_system,
                                    conversation_history=conversation_history,
                                )
                            finally:
                                agent.stream_delta_callback = None
                                agent.reasoning_callback = None
                                agent.thinking_callback = None
                                agent.tool_start_callback = None
                                agent.tool_complete_callback = None

                    usage_before = _usage_snapshot()
                    future = loop.run_in_executor(None, _run)

                    # 真流式：桥接事件即时下发（G3）
                    while True:
                        try:
                            evt = await asyncio.wait_for(bridge.queue.get(), timeout=0.05)
                        except asyncio.TimeoutError:
                            if future.done():
                                while not bridge.queue.empty():
                                    drained = bridge.queue.get_nowait()
                                    _capture(drained)
                                    yield _sse(drained)
                                break
                            continue
                        _capture(evt)
                        yield _sse(evt)

                    result = future.result()
                    if not isinstance(result, dict):
                        result = {"final_response": str(result)}

                    # 冲刷思考过滤器残余文本
                    rest = bridge.flush_think_filter()
                    if rest:
                        yield _sse({"type": "assistant_delta", "text": rest})

                    final_response = result.get("final_response") or ""
                    usage_after = _usage_snapshot()
                    usage = {
                        k: max(0, usage_after[k] - usage_before[k])
                        for k in usage_after
                    }

                    # 非流式 provider 兜底：未收到任何 delta 时一次性下发最终文本
                    if final_response and not bridge.received_deltas:
                        yield _sse({"type": "assistant_delta", "text": final_response})

                # 同步到 Lumina 记忆（user 轮已由 router 写入，这里只写 assistant）
                if final_response:
                    try:
                        if self._append_assistant is not None:
                            await self._append_assistant(final_response)
                        else:
                            from chat_debug.memory import get_memory_store

                            store = get_memory_store()
                            await store.append(
                                user_id,
                                conversation_id,
                                "assistant",
                                final_response,
                                capability="system_chat",
                            )
                    except Exception as e:
                        logger.warning(
                            "Failed to sync Hermes assistant turn to Lumina memory: %s", e
                        )

            except Exception as e:
                logger.exception("Hermes chat failed")
                rec["error"] = str(e)[:500]
                yield _sse(
                    {
                        "type": "error",
                        "service": service,
                        "request_id": request_id,
                        "message": f"Hermes engine error: {str(e)[:200]}",
                    }
                )
                return

            # 业务事件：export_link* → compliance_report（spec §4.4，不存入记忆）
            export_urls = bridge.export_urls if bridge else []
            compliance = bridge.compliance if bridge else None
            for url_info in export_urls:
                yield _sse(
                    {
                        "type": "export_link",
                        "format": "html",
                        "url": url_info.get("url", ""),
                        "platform": url_info.get("platform", ""),
                        "variant": url_info.get("variant", ""),
                        "title": url_info.get("title", ""),
                        "summary": url_info.get("summary", ""),
                        "platform_required_content": url_info.get(
                            "platform_required_content"
                        ),
                    }
                )
            if compliance:
                yield _sse(
                    {
                        "type": "compliance_report",
                        "risk_level": compliance.get("risk_level", "low"),
                        "risk_categories": compliance.get("risk_categories", ["none"]),
                        "violations": compliance.get("violations", []),
                        "suggestion": compliance.get("suggestion", ""),
                        "format": "markdown",
                        "report_md": compliance.get("report_md", ""),
                    }
                )

            reply_ms = int((time.perf_counter() - t0) * 1000)
            payload: Dict[str, Any] = {}
            if export_urls or compliance:
                payload["has_content"] = bool(export_urls)
                payload["content_urls"] = export_urls
                if compliance:
                    payload["compliance"] = compliance
            yield _sse(
                {
                    "type": "done",
                    "service": service,
                    "request_id": request_id,
                    "full_length": len(final_response),
                    "conversation_id": conversation_id,
                    "usage": usage,
                    "reply_ms": reply_ms,
                    "payload": payload,
                }
            )

        finally:
            # 验证工具平台一致性：同一请求内所有工具 platform 是否一致（阶段三 P1-1）
            # 注意：rec["tools"] 是在 _capture 中收集的，此时已完整
            if rec.get("tools"):
                platforms_in_tools = set()
                for tool_info in rec["tools"]:
                    args = tool_info.get("args") or {}
                    if isinstance(args, dict):
                        p = args.get("platform")
                        if p:
                            platforms_in_tools.add(p)
                rec["tool_platform_aligned"] = len(platforms_in_tools) <= 1

            # 对话日志：每轮落一条 JSONL（best-effort，不影响主链路）
            rec["reply"] = final_response[:4000]
            rec["reply_len"] = len(final_response)
            rec["usage"] = usage
            rec["reply_ms"] = int((time.perf_counter() - t0) * 1000)
            if bridge is not None:
                rec["export_urls"] = len(bridge.export_urls)
                if bridge.compliance:
                    rec["compliance_risk"] = bridge.compliance.get("risk_level")
            from services.conversation_log import log_turn

            log_turn(rec)
