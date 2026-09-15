"""Phase 3 TDD Harness：原独立端点已下线，统一收敛到 system-chat。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.main import app
    return TestClient(app)


@pytest.mark.parametrize("endpoint", ["content-ranking", "positioning", "weekly-snapshot"])
def test_legacy_endpoint_returns_gone(client, endpoint):
    response = client.post(
        f"/api/v1/services/{endpoint}/stream",
        json={
            "user_id": "u1",
            "conversation_id": "c1",
            "message": "test",
        },
    )
    assert response.status_code == 410
    assert "system-chat/stream" in response.text


@pytest.mark.parametrize("endpoint", ["content-ranking", "positioning", "weekly-snapshot"])
def test_legacy_memory_endpoint_returns_gone(client, endpoint):
    response = client.get(
        f"/api/v1/services/{endpoint}/memory",
        params={"user_id": "u1", "conversation_id": "c1"},
    )
    assert response.status_code == 410


@pytest.mark.parametrize("endpoint", ["content-ranking", "positioning", "weekly-snapshot"])
def test_legacy_memory_delete_endpoint_returns_gone(client, endpoint):
    response = client.delete(
        f"/api/v1/services/{endpoint}/memory",
        params={"user_id": "u1", "conversation_id": "c1"},
    )
    assert response.status_code == 410
