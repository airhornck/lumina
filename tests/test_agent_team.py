"""
测试 AgentOrchestrator 与 MarketingOrchestra 的协作机制。
"""

from __future__ import annotations

import sys
from pathlib import Path

for p in (
    Path(__file__).resolve().parents[1] / "apps" / "orchestra" / "src",
    Path(__file__).resolve().parents[1] / "packages" / "skill-hub-client" / "src",
    Path(__file__).resolve().parents[1] / "packages" / "knowledge-base" / "src",
    Path(__file__).resolve().parents[1] / "packages" / "lumina-skills" / "src",
    Path(__file__).resolve().parents[1] / "packages" / "llm-hub" / "src",
    Path(__file__).resolve().parents[1] / "packages" / "sop-engine" / "src",
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pytest
from orchestra.agent_orchestrator import AgentOrchestrator, ExecutionMode, AgentMode
from orchestra.core import MarketingOrchestra


class TestAgentOrchestrator:
    """AgentOrchestrator 单元测试。"""

    @pytest.fixture
    def orchestrator(self):
        return AgentOrchestrator()

    def test_orchestrate_diagnosis(self, orchestrator):
        team = orchestrator.orchestrate(
            intent_type="diagnosis",
            intent_subtype=None,
            user_id="u_test",
        )
        assert len(team.agents) == 2
        assert team.agents[0].id == "data_analyst"
        assert team.agents[1].id == "content_strategist"
        assert team.mode == ExecutionMode.PARALLEL

    def test_orchestrate_traffic(self, orchestrator):
        team = orchestrator.orchestrate(
            intent_type="traffic_analysis",
            intent_subtype=None,
            user_id="u_test",
        )
        assert len(team.agents) == 2
        assert team.mode == ExecutionMode.PARALLEL

    def test_orchestrate_content(self, orchestrator):
        team = orchestrator.orchestrate(
            intent_type="content_creation",
            intent_subtype=None,
            user_id="u_test",
        )
        assert len(team.agents) == 2
        assert team.mode == ExecutionMode.SERIAL

    def test_orchestrate_script(self, orchestrator):
        team = orchestrator.orchestrate(
            intent_type="script_creation",
            intent_subtype=None,
            user_id="u_test",
        )
        assert len(team.agents) == 1
        assert team.agents[0].id == "creative_studio"
        assert team.mode == ExecutionMode.SERIAL

    def test_orchestrate_unknown_intent_fallback(self, orchestrator):
        team = orchestrator.orchestrate(
            intent_type="nonexistent_intent",
            intent_subtype=None,
            user_id="u_test",
            mode=AgentMode.SINGLE,
        )
        assert len(team.agents) >= 1
        assert team.agents[0].id == "content_strategist"

    def test_load_config_from_yaml(self):
        from pathlib import Path
        config_path = Path(__file__).resolve().parents[1] / "config" / "agents.yaml"
        if config_path.is_file():
            orch = AgentOrchestrator(config_path=str(config_path))
            assert "knowledge_miner" in orch.agents
            assert "sop_evolver" in orch.agents
            assert "rpa_executor" in orch.agents


class TestAgentTeamExecution:
    """AgentTeam 执行测试。"""

    @pytest.fixture
    def orchestrator(self):
        return AgentOrchestrator()

    async def test_execute_team_parallel(self, orchestrator):
        team = orchestrator.orchestrate(
            intent_type="diagnosis",
            intent_subtype=None,
            user_id="u_test",
            context={"account_url": "https://example.com/user/test"},
        )
        result = await orchestrator.execute_team(
            team=team,
            user_input="帮我诊断一下账号",
            context={"account_url": "https://example.com/user/test", "user_id": "u_test", "platform": "xiaohongshu"},
        )
        assert result.success is True
        assert "data_analyst" in result.agent_outputs
        assert "content_strategist" in result.agent_outputs
        assert result.execution_time_ms >= 0

    async def test_execute_team_serial(self, orchestrator):
        team = orchestrator.orchestrate(
            intent_type="content_creation",
            intent_subtype=None,
            user_id="u_test",
        )
        result = await orchestrator.execute_team(
            team=team,
            user_input="帮我写一篇种草文案",
            context={"user_id": "u_test", "platform": "xiaohongshu"},
        )
        assert result.success is True
        assert "creative_studio" in result.agent_outputs
        assert "compliance_officer" in result.agent_outputs


class TestMarketingOrchestraAgentTeam:
    """MarketingOrchestra 与 AgentOrchestrator 集成测试。"""

    @pytest.fixture
    def orchestra(self):
        return MarketingOrchestra()

    async def test_diagnosis_with_url_uses_agent_team(self, orchestra):
        result = await orchestra.process(
            user_input="帮我诊断一下账号",
            user_id="u_diag",
            platform="xiaohongshu",
            extra_context={"account_url": "https://xiaohongshu.com/user/test123"},
        )
        assert result["mode"] == "agent_team"
        assert result["agent_team"] is not None
        assert "data_analyst" in result["agent_team"]["agents"]
        assert result["agent_team"]["mode"] == "parallel"
        # 兼容原有 API 契约
        hub = result["hub"]
        assert hub["ok"] is True
        assert "result" in hub

    async def test_traffic_with_metrics_uses_agent_team(self, orchestra):
        result = await orchestra.process(
            user_input="帮我分析一下流量",
            user_id="u_traffic",
            platform="xiaohongshu",
            extra_context={"metrics": {"views": 8000, "likes": 120, "shares": 5}},
        )
        assert result["mode"] == "agent_team"
        assert result["agent_team"] is not None
        assert "data_analyst" in result["agent_team"]["agents"]
        assert "growth_hacker" in result["agent_team"]["agents"]
        assert result["agent_team"]["mode"] == "parallel"
        # 兼容原有 API 契约
        hub = result["hub"]
        assert hub["ok"] is True
        assert "funnel_analysis" in hub.get("result", {})

    async def test_diagnosis_without_url_fallback(self, orchestra):
        result = await orchestra.process(
            user_input="帮我诊断一下账号",
            user_id="u_diag2",
            platform="xiaohongshu",
        )
        # 缺少 account_url，不走 AgentTeam，返回 clarification
        assert result["mode"] == "dynamic"
        hub = result["hub"]
        assert hub["ok"] is True
        assert hub.get("result", {}).get("type") == "clarification"

    async def test_traffic_without_metrics_fallback(self, orchestra):
        result = await orchestra.process(
            user_input="帮我分析一下流量",
            user_id="u_traffic2",
            platform="xiaohongshu",
        )
        # 缺少 metrics，不走 AgentTeam，返回 clarification
        assert result["mode"] == "dynamic"
        hub = result["hub"]
        assert hub["ok"] is True
        assert hub.get("result", {}).get("type") == "clarification"

    async def test_content_creation_uses_agent_team(self, orchestra):
        result = await orchestra.process(
            user_input="帮我写一篇小红书种草文案",
            user_id="u_content",
            platform="xiaohongshu",
        )
        assert result["mode"] == "agent_team"
        assert result["agent_team"] is not None
        assert "creative_studio" in result["agent_team"]["agents"]
        assert "compliance_officer" in result["agent_team"]["agents"]
        assert result["agent_team"]["mode"] == "serial"
