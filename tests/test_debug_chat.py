import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
for p in (
    ROOT / "apps" / "api" / "src",
    ROOT / "apps" / "orchestra" / "src",
    ROOT / "apps" / "skill-hub" / "src",
    ROOT / "packages" / "llm-hub" / "src",
    ROOT / "packages" / "knowledge-base" / "src",
    ROOT / "packages" / "lumina-skills" / "src",
    ROOT / "packages" / "skill-hub-client" / "src",
    ROOT / "packages" / "sop-engine" / "src",
    ROOT / "packages" / "agent-core" / "src",
):
    sys.path.insert(0, str(p))

from api.main import app

client = TestClient(app)


def test_debug_capabilities():
    r = client.get("/api/v1/debug/chat/capabilities")
    assert r.status_code == 200
    caps = r.json().get("capabilities") or []
    assert len(caps) == 5
    assert caps[0]["id"] == "system_chat"
    ids = {c["id"] for c in caps}
    assert "content_direction_ranking" in ids
    assert "weekly_decision_snapshot" in ids


def test_debug_memory_crud():
    uid, cid = "test_u", "test_c"
    client.delete(f"/api/v1/debug/chat/memory?user_id={uid}&conversation_id={cid}")
    r = client.get(f"/api/v1/debug/chat/memory?user_id={uid}&conversation_id={cid}")
    assert r.status_code == 200
    assert r.json().get("count") == 0


def test_system_chat_stream_uses_orchestra():
    r = client.post(
        "/api/v1/debug/chat/stream",
        json={
            "capability": "system_chat",
            "user_id": "u_orch",
            "conversation_id": "c_orch",
            "message": "账号诊断",
            "platform": "xiaohongshu",
            "hub_context": {"industry": "beauty"},
        },
    )
    assert r.status_code == 200
    assert "text/event-stream" in (r.headers.get("content-type") or "")
    assert "marketing_orchestra" in r.text
    assert "layer" in r.text


def test_debug_stream_returns_event_stream():
    r = client.post(
        "/api/v1/debug/chat/stream",
        json={
            "capability": "content_direction_ranking",
            "user_id": "u_sse",
            "conversation_id": "c_sse",
            "message": "hello",
        },
    )
    assert r.status_code == 200
    ct = r.headers.get("content-type") or ""
    assert "text/event-stream" in ct
    assert "data:" in r.text


def test_debug_static_mounted():
    r = client.get("/debug/chat/index.html")
    assert r.status_code == 200
    assert b"Lumina" in r.content
