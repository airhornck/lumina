"""
Lumina 统一 API：LLM Hub + Layer2 编排（/api/v1/marketing/hub）+ Layer3 MCP（/mcp）。
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


app = FastAPI(
    title="Lumina",
    description="编排层 + MCP Skill Hub + 双库（YAML）",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    from llm_hub import get_hub

    return {
        "status": "ok",
        "service": "lumina",
        "architecture": "openclaw -> marketing_intelligence_hub -> orchestra -> skill_hub",
        "llm_hub": get_hub() is not None,
        "mcp_skill_hub_mount": "/mcp",
    }


try:
    from skill_hub_app.factory import build_skill_hub_mcp

    _skill_mcp = build_skill_hub_mcp()
    app.mount("/mcp", _skill_mcp.http_app(path="", transport="streamable-http"))
    logger.info("FastMCP Skill Hub mounted at /mcp (streamable-http)")
except Exception:
    logger.exception("Failed to mount /mcp Skill Hub")


from orchestra.router import router as orchestra_router  # noqa: E402

app.include_router(orchestra_router)

from chat_debug.router import router as debug_chat_router  # noqa: E402

app.include_router(debug_chat_router)

from services.router import router as services_router  # noqa: E402

app.include_router(services_router)

# Phase 1-4: 新增 Intent 和 Skill 路由
try:
    from api.intent_router import router as intent_router
    app.include_router(intent_router)
    logger.info("Intent router mounted at /intent")
except Exception:
    logger.exception("Failed to mount Intent router")

try:
    from api.skill_router import router as skill_router
    app.include_router(skill_router)
    logger.info("Skill router mounted at /skill")
except Exception:
    logger.exception("Failed to mount Skill router")

_debug_static = _repo_root / "static" / "debug_chat"
if _debug_static.is_dir():
    app.mount(
        "/debug/chat",
        StaticFiles(directory=str(_debug_static), html=True),
        name="debug_chat_ui",
    )


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
