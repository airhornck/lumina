"""
Lumina 统一 API：LLM Hub + Hermes Agent 引擎（system-chat）+ Layer3 MCP（/mcp）。
对齐 Development_plan_v2 四层架构中的 Python 宿主进程。
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

_repo_root = Path(__file__).resolve().parents[4]
load_dotenv(_repo_root / ".env")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_llm_yaml = Path(
    os.environ.get("LLM_CONFIG_PATH", str(_repo_root / "infra" / "config" / "llm.yaml"))
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 初始化数据库连接池
    try:
        from infra.db import init_db_pool

        pool = await init_db_pool()
        if pool:
            logger.info("Database pool initialized")
        else:
            logger.warning("DATABASE_URL not set, running without DB persistence")
    except Exception:
        logger.exception("Database pool init failed; usage tracking disabled")

    # 2. 注册 LLM 用量上报回调
    try:
        from llm_hub.usage_reporter import set_usage_reporter
        from services.usage_service import record_usage

        async def _reporter(user_id, model, pt, ct, tt, skill_name):
            await record_usage(user_id, model, pt, ct, skill_name)

        set_usage_reporter(_reporter)
        logger.info("LLM usage reporter registered")
    except Exception:
        logger.exception("Failed to register LLM usage reporter")

    # 3. 加载 LLM Hub
    if _llm_yaml.is_file():
        try:
            from llm_hub import init_default_hub

            init_default_hub(str(_llm_yaml))
            logger.info("LLM Hub loaded from %s", _llm_yaml)
        except Exception:
            logger.exception("LLM Hub load failed; skills run without LLM")
    else:
        logger.warning("No LLM config at %s", _llm_yaml)

    yield

    # 关闭数据库连接池
    try:
        from infra.db import close_db_pool

        await close_db_pool()
        logger.info("Database pool closed")
    except Exception:
        logger.exception("Database pool close failed")


app = FastAPI(
    title="Lumina API",
    description="Lumina 营销智能助手统一 API。以 Hermes Agent 为唯一执行引擎，涵盖 Skill 调用、Token 用量查询、Demo 工作台等能力层接口。",
    version="0.4.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"], summary="健康检查", response_model=dict)
async def health():
    from llm_hub import get_hub
    from infra.db import get_pool

    return {
        "status": "ok",
        "service": "lumina",
        "architecture": "fastapi -> hermes_adapter -> hermes_agent -> lumina_tools",
        "llm_hub": get_hub() is not None,
        "mcp_skill_hub_mount": "/mcp",
        "db_pool": get_pool() is not None,
    }


try:
    from skill_hub_app.factory import build_skill_hub_mcp

    _skill_mcp = build_skill_hub_mcp()
    _mcp_http_app = _skill_mcp.http_app(path="/", transport="streamable-http")
    app.mount("/mcp", _mcp_http_app)

    # Starlette 不会运行被挂载子应用的 lifespan，而 fastmcp>=3.4 的
    # streamable-http 会话管理依赖其 lifespan 初始化 task group，需并入父应用。
    _parent_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def _combined_lifespan(_app: FastAPI):
        async with _mcp_http_app.lifespan(_mcp_http_app):
            async with _parent_lifespan(_app) as _state:
                yield _state

    app.router.lifespan_context = _combined_lifespan
    logger.info("FastMCP Skill Hub mounted at /mcp (streamable-http)")
except Exception:
    logger.exception("Failed to mount /mcp Skill Hub")


from chat_debug.router import router as debug_chat_router  # noqa: E402

app.include_router(debug_chat_router)

from services.router import router as services_router  # noqa: E402

app.include_router(services_router)

# Phase 1-4: 新增 Skill 路由
try:
    from api.skill_router import router as skill_router
    app.include_router(skill_router)
    logger.info("Skill router mounted at /skill")
except Exception:
    logger.exception("Failed to mount Skill router")

try:
    from api.demo_router import router as demo_router
    app.include_router(demo_router)
    logger.info("Demo router mounted at /api/v1/demo")
except Exception:
    logger.exception("Failed to mount Demo router")

# Token 用量查询路由
try:
    from api.usage_router import router as usage_router
    app.include_router(usage_router)
    logger.info("Usage router mounted at /api/v1/usage")
except Exception:
    logger.exception("Failed to mount Usage router")

_debug_static = _repo_root / "static" / "debug_chat"
if _debug_static.is_dir():
    app.mount(
        "/debug/chat",
        StaticFiles(directory=str(_debug_static), html=True),
        name="debug_chat_ui",
    )

# 前端 SDK 静态目录（luminaChatClient.js），供调试页与外部前端引入
_sdk_static = _repo_root / "static" / "sdk"
if _sdk_static.is_dir():
    app.mount(
        "/sdk",
        StaticFiles(directory=str(_sdk_static)),
        name="sdk_static",
    )

# v2.0: 内容导出 StaticFiles 挂载
_content_static = _repo_root / "static" / "content"
_content_static.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/content",
    StaticFiles(directory=str(_content_static)),
    name="content_exports",
)

# v2.0: 导出下载路由
try:
    from api.export_router import router as export_router
    app.include_router(export_router)
except Exception:
    logger.exception("Failed to mount Export router")


def main() -> None:
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=True,
        app_dir=str(Path(__file__).resolve().parent.parent),
    )


if __name__ == "__main__":
    main()
