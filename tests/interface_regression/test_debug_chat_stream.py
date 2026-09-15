"""Phase 0 TDD Harness：调试聊天 SSE 接口回归测试。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.main import app

    return TestClient(app)


def _parse_sse(response_text: str):
    events = []
    for line in response_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            data = line[6:]
            if data:
                events.append(json.loads(data))
    return events


def test_debug_chat_stream_v2_sse_format(client):
    response = client.post(
        "/api/v1/debug/chat/stream",
        json={
            "capability": "system_chat",
            "user_id": "regression-user",
            "conversation_id": "regression-conv",
            "message": "你好",
        },
        headers={"X-Lumina-Stream-Format": "2"},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"


def test_debug_chat_stream_v1_format(client):
    response = client.post(
        "/api/v1/debug/chat/stream",
        json={
            "capability": "system_chat",
            "user_id": "regression-user",
            "conversation_id": "regression-conv-v1",
            "message": "你好",
        },
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "done"


def test_debug_chat_memory_response_format(client):
    response = client.get(
        "/api/v1/debug/chat/memory",
        params={
            "user_id": "regression-user",
            "conversation_id": "regression-conv",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "conversation_id" in data
    assert "count" in data
    assert "messages" in data


def test_debug_chat_memory_delete_response_format(client):
    response = client.delete(
        "/api/v1/debug/chat/memory",
        params={
            "user_id": "regression-user",
            "conversation_id": "regression-conv",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True
    assert data.get("cleared") is True
