"""
Demo 工作台集成测试

验证三个核心接口：
1. GET /api/v1/demo/position-matrix
2. GET /api/v1/demo/weekly-rankings
3. POST /api/v1/services/cross-platform-content/stream
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 设置路径
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root / "apps" / "api" / "src"))
sys.path.insert(0, str(_repo_root / "packages" / "lumina-skills" / "src"))
sys.path.insert(0, str(_repo_root / "packages" / "llm-hub" / "src"))
sys.path.insert(0, str(_repo_root / "packages" / "knowledge-base" / "src"))
sys.path.insert(0, str(_repo_root / "apps" / "rpa" / "src"))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.main import app
    return TestClient(app)


class TestDemoRouter:
    """测试 Demo REST 接口"""

    def test_position_matrix_endpoint_exists(self, client):
        """P1-2: 定位矩阵接口可访问"""
        response = client.get("/api/v1/demo/position-matrix?industry=教育&stage=起步")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data

    def test_position_matrix_response_format(self, client):
        """P1-4: 统一返回格式 {code, message, data}"""
        response = client.get("/api/v1/demo/position-matrix")
        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert "message" in data
        assert "data" in data

    def test_position_matrix_empty_state(self, client):
        """P1-6: 空态处理"""
        response = client.get("/api/v1/demo/position-matrix")
        assert response.status_code == 200
        data = response.json()
        # 无 LLM 配置时返回 data: null
        assert data["code"] == 0

    def test_weekly_rankings_endpoint_exists(self, client):
        """P1-3: 榜单接口可访问"""
        response = client.get("/api/v1/demo/weekly-rankings?sort_by=fit_score&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data

    def test_weekly_rankings_response_format(self, client):
        """P1-4: 统一返回格式"""
        response = client.get("/api/v1/demo/weekly-rankings")
        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert "message" in data
        assert "data" in data

    def test_weekly_rankings_data_source_field(self, client):
        """P1-5: data_source 字段标识"""
        response = client.get("/api/v1/demo/weekly-rankings")
        assert response.status_code == 200
        data = response.json()
        inner = data.get("data", {})
        assert "data_source" in inner
        assert inner["data_source"] in ("rpa+llm", "llm_only")

    def test_weekly_rankings_pagination_params(self, client):
        """P3-2: limit/offset 分页参数支持"""
        response = client.get("/api/v1/demo/weekly-rankings?limit=5&offset=0")
        assert response.status_code == 200

    def test_weekly_rankings_sort_param(self, client):
        """P3-1: sort_by 参数支持"""
        response = client.get("/api/v1/demo/weekly-rankings?sort_by=heat")
        assert response.status_code == 200


class TestCrossPlatformContent:
    """测试跨平台内容生成 SSE 接口"""

    def test_service_registered(self, client):
        """P1-11: cross-platform-content 已注册到 ALLOWED_SERVICES"""
        response = client.post(
            "/api/v1/services/unknown-service/stream",
            json={
                "user_id": "u1",
                "conversation_id": "c1",
                "message": "test",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "cross-platform-content" in str(data.get("detail", ""))

    def test_cross_platform_stream_events(self, client):
        """P1-7: SSE 流事件类型正确"""
        response = client.post(
            "/api/v1/services/cross-platform-content/stream",
            json={
                "user_id": "u1",
                "conversation_id": "c1",
                "message": "生成职场穿搭内容",
                "context": {
                    "target_platforms": ["xiaohongshu", "douyin"],
                },
            },
        )
        assert response.status_code == 200
        # SSE 流即使 LLM 未配置也会返回 error 事件
        content = response.text
        assert "data:" in content


class TestPromptTemplates:
    """测试 Prompt 模板文件"""

    def test_template_files_exist(self):
        """P3-3: Prompt 模板文件存在"""
        prompts_dir = _repo_root / "apps" / "api" / "src" / "prompts"
        assert (prompts_dir / "position_matrix.txt").exists()
        assert (prompts_dir / "weekly_rankings.txt").exists()
        assert (prompts_dir / "platform_adapt.txt").exists()
        assert (prompts_dir / "master_content.txt").exists()
        assert (prompts_dir / "revision.txt").exists()

    def test_templates_not_empty(self):
        """P3-3: 模板文件非空"""
        prompts_dir = _repo_root / "apps" / "api" / "src" / "prompts"
        for name in [
            "position_matrix",
            "weekly_rankings",
            "platform_adapt",
            "master_content",
            "revision",
        ]:
            content = (prompts_dir / f"{name}.txt").read_text(encoding="utf-8")
            assert len(content) > 50


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
