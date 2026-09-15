"""Phase 1：GET /api/v1/services/{service}/memory 分页接口测试。

通过注入内存 backend 隔离数据库依赖；种子数据直接写 backend._data（同步操作，
避免跨事件循环使用 asyncio.Lock）。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_and_backend():
    import services.memory_service as ms
    from chat_debug.memory import ChatMemoryStore
    from api.main import app

    backend = ChatMemoryStore()
    ms._mem_store = ms.ServiceMemoryStore(backend=backend)
    return TestClient(app), backend


def _seed(backend, n, uid="u1", conv="c1", service="system-chat"):
    # 与 ServiceMemoryStore 保持一致：直接使用 bare conversation_id
    key = (uid, conv)
    backend._data[key] = [
        {"role": "user", "content": f"msg-{i}", "ts": f"2026-07-16T00:00:{i:02d}+00:00"}
        for i in range(n)
    ]


def _get(client, **params):
    base = {"user_id": "u1", "conversation_id": "c1"}
    base.update(params)
    return client.get("/api/v1/services/system-chat/memory", params=base)


def test_memory_default_returns_all(client_and_backend):
    client, backend = client_and_backend
    _seed(backend, 10)

    r = _get(client)
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 10
    assert data["total"] == 10
    assert data["has_more"] is False
    assert [m["content"] for m in data["messages"]] == [f"msg-{i}" for i in range(10)]


def test_memory_limit_returns_latest_n(client_and_backend):
    client, backend = client_and_backend
    _seed(backend, 10)

    data = _get(client, limit=4).json()
    assert data["count"] == 4
    assert [m["content"] for m in data["messages"]] == ["msg-6", "msg-7", "msg-8", "msg-9"]
    assert data["total"] == 10
    assert data["has_more"] is True


def test_memory_offset_pages_earlier(client_and_backend):
    client, backend = client_and_backend
    _seed(backend, 10)

    data = _get(client, limit=4, offset=4).json()
    assert [m["content"] for m in data["messages"]] == ["msg-2", "msg-3", "msg-4", "msg-5"]
    assert data["has_more"] is True


def test_memory_offset_last_page_has_more_false(client_and_backend):
    client, backend = client_and_backend
    _seed(backend, 10)

    data = _get(client, limit=4, offset=8).json()
    assert [m["content"] for m in data["messages"]] == ["msg-0", "msg-1"]
    assert data["total"] == 10
    assert data["has_more"] is False


def test_memory_order_desc(client_and_backend):
    client, backend = client_and_backend
    _seed(backend, 5)

    data = _get(client, limit=3, order="desc").json()
    assert [m["content"] for m in data["messages"]] == ["msg-4", "msg-3", "msg-2"]


def test_memory_empty_conversation(client_and_backend):
    client, _ = client_and_backend

    data = _get(client, limit=50).json()
    assert data["count"] == 0
    assert data["messages"] == []
    assert data["total"] == 0
    assert data["has_more"] is False


def test_memory_invalid_order_rejected(client_and_backend):
    client, backend = client_and_backend
    _seed(backend, 3)

    r = _get(client, order="sideways")
    assert r.status_code == 422


def test_memory_invalid_limit_rejected(client_and_backend):
    client, backend = client_and_backend
    _seed(backend, 3)

    assert _get(client, limit=0).status_code == 422
    assert _get(client, limit=1001).status_code == 422
