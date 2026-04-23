"""
端到端集成测试：AgentOrchestrator → AgentTeam → SkillHubClient → Skill → LLM

模拟真实用户请求，验证完整调用链路：
1. MarketingOrchestra 识别意图并决定走 AgentTeam 路径
2. AgentOrchestrator 组建正确的 AgentTeam（PARALLEL/SERIAL/MIXED）
3. execute_team 正确分发到各 Agent
4. 每个 Agent 的 _execute_agent 调用正确的 Skill（通过 SkillHubClient）
5. Skill 内部调用 LLM（mock）生成结果
6. 最终结果结构正确，兼容原有 API 契约
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project paths are available
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
for _p in [
    str(_PROJECT_ROOT / "apps" / "orchestra" / "src"),
    str(_PROJECT_ROOT / "packages" / "skill-hub-client" / "src"),
    str(_PROJECT_ROOT / "packages" / "lumina-skills" / "src"),
    str(_PROJECT_ROOT / "packages" / "llm-hub" / "src"),
    str(_PROJECT_ROOT / "packages" / "knowledge-base" / "src"),
    str(_PROJECT_ROOT / "apps" / "rpa" / "src"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ============ Mock LLM Client ============

class MockLLMConfig:
    api_key = "test-api-key"
    provider = "openai"
    model = "gpt-4"
    temperature = 0.7
    max_tokens = 2000
    timeout = 30


class MockLLMClient:
    """智能 Mock LLM Client，根据 prompt 内容返回不同的预设响应"""
    
    def __init__(self):
        self.config = MockLLMConfig()
        self.call_history: list[dict] = []
    
    async def complete(self, prompt: str, **kwargs) -> str:
        self.call_history.append({"prompt": prompt[:200], "kwargs": kwargs})
        
        # 选题推荐
        if "选题" in prompt or "recommend" in prompt.lower():
            return json.dumps({
                "recommendations": [
                    {
                        "topic": "春季护肤新品测评",
                        "score": 0.88,
                        "reason": "春季换季护肤需求上升，结合新品测评可吸引精准流量",
                        "methodology": "aida_advanced"
                    },
                    {
                        "topic": "学生党平价好物分享",
                        "score": 0.82,
                        "reason": "学生群体活跃度高，平价好物容易引发互动",
                        "methodology": "trend_ride"
                    }
                ]
            }, ensure_ascii=False)
        
        # 文案生成
        if "文案" in prompt or "title" in prompt.lower() or "content" in prompt.lower():
            return json.dumps({
                "title": "🔥这个平价好物让我省了300块！学生党必看",
                "content": "姐妹们！最近挖到一个宝藏好物...",
                "hashtags": ["平价好物", "学生党", "省钱攻略", "种草"]
            }, ensure_ascii=False)
        
        # 脚本生成
        if "脚本" in prompt or "分镜" in prompt or "shot_list" in prompt.lower():
            return json.dumps({
                "hook_script": "你知道吗？90%的人护肤都做错了一步！",
                "full_script": "哈喽姐妹们！今天来聊一个很多人忽略的护肤细节...",
                "shot_list": [
                    {"timestamp": "0-3s", "visual": "特写博主惊讶表情", "audio": "悬疑音效", "text": "90%的人都做错了！"},
                    {"timestamp": "3-15s", "visual": "产品展示", "audio": "轻快节奏", "text": "关键步骤"},
                    {"timestamp": "15-30s", "visual": "使用演示", "audio": "解说", "text": "正确方法"},
                    {"timestamp": "30-60s", "visual": "效果对比", "audio": "渐强", "text": "效果展示"}
                ],
                "bgm_suggestion": "轻快电子乐，节奏感强，适合种草类内容",
                "caption_highlights": ["关键步骤", "正确方法", "效果对比"]
            }, ensure_ascii=False)
        
        # 案例匹配
        if "案例" in prompt or "case" in prompt.lower():
            return json.dumps({
                "cases": [
                    {
                        "case_id": "case_001",
                        "title": "小红书美妆博主3个月涨粉10万",
                        "similarity_score": 0.92,
                        "key_success_factors": ["强钩子开头", "真实测评", "高频互动"]
                    }
                ],
                "pattern_analysis": "强钩子+真实体验+高频互动是核心模式",
                "actionable_takeaways": ["优化前3秒钩子", "增加真实使用场景", "及时回复评论"]
            }, ensure_ascii=False)
        
        # 知识问答
        if "知识" in prompt or "answer" in prompt.lower():
            return json.dumps({
                "answer": "AIDA模型是营销经典框架，包含注意(Attention)、兴趣(Interest)、欲望(Desire)、行动(Action)四个阶段。",
                "sources": ["营销方法论库"],
                "confidence": 0.92,
                "related_methodologies": ["aida_advanced", "pas_framework"]
            }, ensure_ascii=False)
        
        # NLG 格式化
        if "Lumina 营销助手" in prompt or "说明系统刚执行完" in prompt:
            return "已为您完成分析，以下是关键结果摘要..."
        
        # 默认响应
        return json.dumps({"result": "mock_llm_response"}, ensure_ascii=False)
    
    async def stream_completion(self, messages, **kwargs):
        yield "mock_stream"


# ============ Fixtures ============

@pytest.fixture
def mock_llm_client():
    return MockLLMClient()


@pytest.fixture
def mock_llm_hub(mock_llm_client):
    """初始化全局 mock LLM Hub"""
    mock_hub = MagicMock()
    mock_hub.get_client.return_value = mock_llm_client
    
    mock_config = MagicMock()
    mock_config.llm_pool = {"default": MagicMock()}
    mock_config.default_llm = "default"
    mock_config.skill_config = {}
    mock_config.component_config = {}
    mock_hub.config = mock_config
    
    return mock_hub


@pytest.fixture
def llm_patches(mock_llm_hub, mock_llm_client):
    """Patch 所有 LLM 入口点"""
    patches = []
    
    # Patch llm_hub 全局 hub
    patches.append(patch("llm_hub.hub._default_hub", mock_llm_hub))
    patches.append(patch("llm_hub.get_client", return_value=mock_llm_client))
    
    # Patch lumina_skills 模块中的 get_client（模块级导入需直接 patch 模块属性）
    import lumina_skills.content as _content_mod
    import lumina_skills.assets as _assets_mod
    
    patches.append(patch.object(_content_mod, "get_client", return_value=mock_llm_client))
    patches.append(patch.object(_assets_mod, "get_client", return_value=mock_llm_client))
    
    for p in patches:
        p.start()
    
    yield
    
    for p in patches:
        p.stop()


@pytest.fixture
def orchestra(llm_patches):
    """初始化 MarketingOrchestra（LLM 已 mock）"""
    from orchestra.core import MarketingOrchestra
    return MarketingOrchestra()


@pytest.fixture
def agent_orchestrator(llm_patches):
    """初始化 AgentOrchestrator（LLM 已 mock）"""
    from orchestra.agent_orchestrator import AgentOrchestrator
    return AgentOrchestrator()


# ============ Test Cases ============

class TestAgentOrchestrationE2E:
    """端到端测试：Agent 编排与 Skill 调用"""
    
    # ------------------------------------------------------------------
    # 1. PARALLEL 模式 - 账号诊断
    # ------------------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_diagnosis_parallel_with_llm(self, orchestra, mock_llm_client):
        """
        场景：用户请求账号诊断，提供账号 URL
        预期：
        - 走 AgentTeam 路径（mode="agent_team"）
        - AgentTeam 模式为 PARALLEL
        - Agents: [data_analyst, content_strategist]
        - data_analyst → diagnose_account（基础诊断，无 LLM）
        - content_strategist → select_topic（调用 LLM）
        - LLM 被调用（验证 mock 调用历史）
        """
        result = await orchestra.process(
            user_input="帮我诊断一下这个账号",
            user_id="test_user_001",
            platform="xiaohongshu",
            extra_context={
                "account_url": "https://www.xiaohongshu.com/user/test_account",
            },
        )
        
        # 1. 验证走了 AgentTeam 路径
        assert result["mode"] == "agent_team", f"Expected agent_team, got {result['mode']}"
        
        # 2. 验证 AgentTeam 结构
        agent_team = result["hub"]["agent_team"]
        assert agent_team["mode"] == "parallel"
        assert "data_analyst" in agent_team["agents"]
        assert "content_strategist" in agent_team["agents"]
        
        # 3. 验证每个 Agent 都有输出
        agent_outputs = result["hub"]["agent_outputs"]
        assert "data_analyst" in agent_outputs
        assert "content_strategist" in agent_outputs
        
        # 4. 验证 data_analyst 调用了 diagnose_account
        da_output = agent_outputs["data_analyst"]
        assert "skill-data-analyst" in da_output["skills_executed"]
        da_results = da_output["results"]["skill-data-analyst"]
        # diagnose_account 返回 dict（非 SkillHubClient 包装），因为 _execute_agent 直接调用 skill_hub_client.call
        # 实际上 skill_hub_client.call 包装了结果：{"ok": True, "result": {...}}
        assert da_results["ok"] is True
        
        # 5. 验证 content_strategist 调用了 select_topic 并触发了 LLM
        cs_output = agent_outputs["content_strategist"]
        assert "skill-content-strategist" in cs_output["skills_executed"]
        cs_results = cs_output["results"]["skill-content-strategist"]
        assert cs_results["ok"] is True
        
        # 验证 LLM 被调用（select_topic 会调用 LLM）
        llm_calls_for_topic = [c for c in mock_llm_client.call_history if "选题" in c["prompt"]]
        assert len(llm_calls_for_topic) > 0, "select_topic 应该调用 LLM"
        
        # 6. 验证结果中有推荐选题
        cs_result = cs_results["result"]
        assert "recommended_topics" in cs_result
        assert len(cs_result["recommended_topics"]) > 0
        
        # 7. 验证 reply 非空
        assert result["reply"] and isinstance(result["reply"], str)
    
    # ------------------------------------------------------------------
    # 2. SERIAL 模式 - 内容创作
    # ------------------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_content_creation_serial_with_llm(self, orchestra, mock_llm_client):
        """
        场景：用户请求写种草文案
        预期：
        - 走 AgentTeam 路径（mode="agent_team"）
        - AgentTeam 模式为 SERIAL
        - Agents: [creative_studio, compliance_officer]
        - creative_studio → generate_text（调用 LLM）
        - compliance_officer → detect_risk（接收 creative_studio 的上下文）
        - 串行验证：compliance_officer 执行时 context 包含 creative_studio 输出
        """
        result = await orchestra.process(
            user_input="帮我写一篇小红书种草文案",
            user_id="test_user_002",
            platform="xiaohongshu",
        )
        
        # 1. 验证走了 AgentTeam 路径
        assert result["mode"] == "agent_team"
        
        # 2. 验证 AgentTeam 为 SERIAL 模式
        agent_team = result["hub"]["agent_team"]
        assert agent_team["mode"] == "serial"
        assert "creative_studio" in agent_team["agents"]
        assert "compliance_officer" in agent_team["agents"]
        
        # 3. 验证 creative_studio 输出生成了文案
        agent_outputs = result["hub"]["agent_outputs"]
        assert "creative_studio" in agent_outputs
        cs_output = agent_outputs["creative_studio"]
        assert "skill-creative-studio" in cs_output["skills_executed"]
        
        cs_results = cs_output["results"]["skill-creative-studio"]
        assert cs_results["ok"] is True
        cs_result = cs_results["result"]
        assert "title" in cs_result
        assert "content" in cs_result
        
        # 4. 验证 LLM 被调用（generate_text 会调用 LLM）
        llm_calls_for_text = [c for c in mock_llm_client.call_history if "文案" in c["prompt"]]
        assert len(llm_calls_for_text) > 0, "generate_text 应该调用 LLM"
        
        # 5. 验证 compliance_officer 执行了风险检测
        assert "compliance_officer" in agent_outputs
        co_output = agent_outputs["compliance_officer"]
        assert "skill-compliance-officer" in co_output["skills_executed"]
        
        co_results = co_output["results"]["skill-compliance-officer"]
        assert co_results["ok"] is True
        co_result = co_results["result"]
        assert "risk_level" in co_result
    
    # ------------------------------------------------------------------
    # 3. SERIAL 模式 - 脚本创作
    # ------------------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_script_creation_serial_with_llm(self, orchestra, mock_llm_client):
        """
        场景：用户请求写短视频脚本
        预期：
        - 走 AgentTeam 路径（mode="agent_team"）
        - AgentTeam 模式为 SERIAL
        - Agents: [creative_studio]
        - creative_studio → generate_script（调用 LLM）
        - 验证 LLM 返回了完整的脚本结构
        """
        result = await orchestra.process(
            user_input="帮我写一个60秒的短视频脚本",
            user_id="test_user_003",
            platform="douyin",
        )
        
        # 1. 验证走了 AgentTeam 路径
        assert result["mode"] == "agent_team"
        
        # 2. 验证 AgentTeam 为 SERIAL 模式
        agent_team = result["hub"]["agent_team"]
        assert agent_team["mode"] == "serial"
        assert "creative_studio" in agent_team["agents"]
        
        # 3. 验证 generate_script 调用结果
        agent_outputs = result["hub"]["agent_outputs"]
        assert "creative_studio" in agent_outputs
        cs_output = agent_outputs["creative_studio"]
        cs_results = cs_output["results"]["skill-creative-studio"]
        assert cs_results["ok"] is True
        
        script = cs_results["result"]
        assert "hook_script" in script
        assert "full_script" in script
        assert "shot_list" in script
        assert isinstance(script["shot_list"], list)
        assert len(script["shot_list"]) > 0
        assert "bgm_suggestion" in script
        
        # 4. 验证 LLM 被调用（generate_script 会调用 LLM）
        llm_calls_for_script = [c for c in mock_llm_client.call_history if "脚本" in c["prompt"]]
        assert len(llm_calls_for_script) > 0, "generate_script 应该调用 LLM"
    
    # ------------------------------------------------------------------
    # 4. PARALLEL 模式 - 流量分析
    # ------------------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_traffic_analysis_parallel(self, orchestra, mock_llm_client):
        """
        场景：用户请求流量分析，提供了 metrics
        预期：
        - 走 AgentTeam 路径（mode="agent_team"）
        - AgentTeam 模式为 PARALLEL
        - Agents: [data_analyst, growth_hacker]
        - 两个 Agent 并行执行
        """
        result = await orchestra.process(
            user_input="分析一下最近的流量数据",
            user_id="test_user_004",
            platform="xiaohongshu",
            extra_context={
                "metrics": {
                    "views": 15000,
                    "likes": 800,
                    "shares": 45,
                    "comments": 120,
                },
            },
        )
        
        # 1. 验证走了 AgentTeam 路径
        assert result["mode"] == "agent_team"
        
        # 2. 验证 AgentTeam 为 PARALLEL 模式
        agent_team = result["hub"]["agent_team"]
        assert agent_team["mode"] == "parallel"
        assert "data_analyst" in agent_team["agents"]
        assert "growth_hacker" in agent_team["agents"]
        
        # 3. 验证两个 Agent 都有输出
        agent_outputs = result["hub"]["agent_outputs"]
        assert "data_analyst" in agent_outputs
        assert "growth_hacker" in agent_outputs
        
        # 4. 验证 data_analyst 的 analyze_traffic 结果
        da_output = agent_outputs["data_analyst"]
        assert "skill-data-analyst" in da_output["skills_executed"]
        da_results = da_output["results"]["skill-data-analyst"]
        assert da_results["ok"] is True
        
        # analyze_traffic 返回漏斗分析
        da_result = da_results["result"]
        assert "funnel_analysis" in da_result
    
    # ------------------------------------------------------------------
    # 5. MIXED 模式 - 矩阵搭建
    # ------------------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_matrix_setup_mixed(self, agent_orchestrator):
        """
        场景：矩阵搭建意图
        预期：
        - AgentTeam 模式为 MIXED
        - Agents: [matrix_commander, account_keeper]
        - 高优先级 Agent 并行，低优先级串行
        """
        team = agent_orchestrator.orchestrate(
            intent_type="matrix_setup",
            intent_subtype=None,
            user_id="test_user_005",
            mode="matrix",
        )
        
        assert team.mode.value == "mixed"
        agent_ids = [a.id for a in team.agents]
        assert "matrix_commander" in agent_ids
        assert "account_keeper" in agent_ids
        
        # 执行团队（mock skill_hub_client 避免真实调用）
        result = await agent_orchestrator.execute_team(
            team=team,
            user_input="帮我规划一个美妆矩阵",
            context={"platform": "xiaohongshu", "user_id": "test_user_005"},
        )
        
        assert result.success is True
        assert "matrix_commander" in result.agent_outputs
        assert "account_keeper" in result.agent_outputs


class TestSkillToLLMInvocation:
    """测试 Skill 到 LLM 的调用链路"""
    
    @pytest.mark.asyncio
    async def test_select_topic_invokes_llm(self, llm_patches, mock_llm_client):
        """验证 select_topic Skill 正确调用 LLM"""
        from lumina_skills.content import select_topic
        
        result = await select_topic(
            industry="beauty",
            user_id="test",
            platform="xiaohongshu",
        )
        
        # 验证 LLM 被调用
        llm_calls = [c for c in mock_llm_client.call_history if "选题" in c["prompt"]]
        assert len(llm_calls) > 0, "select_topic 应该调用 LLM"
        
        # 验证返回了推荐选题
        assert "recommended_topics" in result
        assert len(result["recommended_topics"]) > 0
        first_topic = result["recommended_topics"][0]
        assert "topic" in first_topic
        assert "score" in first_topic
        assert "reason" in first_topic
    
    @pytest.mark.asyncio
    async def test_generate_text_invokes_llm(self, llm_patches, mock_llm_client):
        """验证 generate_text Skill 正确调用 LLM"""
        from lumina_skills.content import generate_text
        
        result = await generate_text(
            topic="春季护肤新品",
            platform="xiaohongshu",
            content_dna={"tone": "friendly", "style": "tutorial"},
            user_id="test",
        )
        
        # 验证 LLM 被调用
        llm_calls = [c for c in mock_llm_client.call_history if "文案" in c["prompt"]]
        assert len(llm_calls) > 0, "generate_text 应该调用 LLM"
        
        # 验证返回了文案结构
        assert "title" in result
        assert "content" in result
        assert "hashtags" in result
    
    @pytest.mark.asyncio
    async def test_generate_script_invokes_llm(self, llm_patches, mock_llm_client):
        """验证 generate_script Skill 正确调用 LLM"""
        from lumina_skills.content import generate_script
        
        result = await generate_script(
            topic="春季护肤新品测评",
            hook_type="curiosity",
            duration=60,
            platform="douyin",
            user_id="test",
        )
        
        # 验证 LLM 被调用
        llm_calls = [c for c in mock_llm_client.call_history if "脚本" in c["prompt"]]
        assert len(llm_calls) > 0, "generate_script 应该调用 LLM"
        
        # 验证返回了完整脚本结构
        assert "hook_script" in result
        assert "full_script" in result
        assert "shot_list" in result
        assert isinstance(result["shot_list"], list)
        assert "bgm_suggestion" in result
    
    @pytest.mark.asyncio
    async def test_match_cases_invokes_llm(self, llm_patches, mock_llm_client):
        """验证 match_cases Skill 正确调用 LLM"""
        from lumina_skills.assets import match_cases
        
        result = await match_cases(
            content_type="note",
            industry="beauty",
            user_id="test",
        )
        
        # 验证 LLM 被调用
        llm_calls = [c for c in mock_llm_client.call_history if "案例" in c["prompt"]]
        assert len(llm_calls) > 0, "match_cases 应该调用 LLM"
        
        # 验证返回了案例结构
        assert "matched_cases" in result
        assert "pattern_analysis" in result
        assert "actionable_takeaways" in result
    
    @pytest.mark.asyncio
    async def test_qa_knowledge_invokes_llm(self, llm_patches, mock_llm_client):
        """验证 qa_knowledge Skill 正确调用 LLM"""
        from lumina_skills.assets import qa_knowledge
        
        result = await qa_knowledge(
            question="什么是AIDA模型？",
            knowledge_domain="methodology",
            user_id="test",
        )
        
        # 验证 LLM 被调用
        llm_calls = [c for c in mock_llm_client.call_history if "知识" in c["prompt"]]
        assert len(llm_calls) > 0, "qa_knowledge 应该调用 LLM"
        
        # 验证返回了问答结构
        assert "answer" in result
        assert "confidence" in result
        assert "related_methodologies" in result


class TestAgentSkillMapping:
    """测试 Agent 到 Skill 的映射正确性"""
    
    def test_diagnosis_maps_to_correct_agents(self, agent_orchestrator):
        """diagnosis 意图应映射到 data_analyst + content_strategist"""
        team = agent_orchestrator.orchestrate(
            intent_type="diagnosis",
            intent_subtype=None,
            user_id="test",
        )
        agent_ids = [a.id for a in team.agents]
        assert "data_analyst" in agent_ids
        assert "content_strategist" in agent_ids
        assert team.mode == agent_orchestrator.execution_modes["diagnosis"]
    
    def test_content_creation_maps_to_correct_agents(self, agent_orchestrator):
        """content_creation 意图应映射到 creative_studio + compliance_officer"""
        team = agent_orchestrator.orchestrate(
            intent_type="content_creation",
            intent_subtype=None,
            user_id="test",
        )
        agent_ids = [a.id for a in team.agents]
        assert "creative_studio" in agent_ids
        assert "compliance_officer" in agent_ids
    
    def test_script_creation_maps_to_correct_agents(self, agent_orchestrator):
        """script_creation 意图应映射到 creative_studio"""
        team = agent_orchestrator.orchestrate(
            intent_type="script_creation",
            intent_subtype=None,
            user_id="test",
        )
        agent_ids = [a.id for a in team.agents]
        assert "creative_studio" in agent_ids
    
    def test_traffic_analysis_maps_to_correct_agents(self, agent_orchestrator):
        """traffic_analysis 意图应映射到 data_analyst + growth_hacker"""
        team = agent_orchestrator.orchestrate(
            intent_type="traffic_analysis",
            intent_subtype=None,
            user_id="test",
        )
        agent_ids = [a.id for a in team.agents]
        assert "data_analyst" in agent_ids
        assert "growth_hacker" in agent_ids
    
    def test_execution_modes_loaded_from_yaml(self, agent_orchestrator):
        """验证执行模式从 YAML 正确加载"""
        from orchestra.agent_orchestrator import ExecutionMode
        
        # PARALLEL 模式
        assert agent_orchestrator.execution_modes.get("diagnosis") == ExecutionMode.PARALLEL
        assert agent_orchestrator.execution_modes.get("traffic_analysis") == ExecutionMode.PARALLEL
        
        # SERIAL 模式（YAML 中用 sequential，映射到 serial）
        assert agent_orchestrator.execution_modes.get("content_creation") == ExecutionMode.SERIAL
        assert agent_orchestrator.execution_modes.get("script_creation") == ExecutionMode.SERIAL
        
        # MIXED 模式
        assert agent_orchestrator.execution_modes.get("matrix_setup") == ExecutionMode.MIXED


class TestFallbackBehavior:
    """测试降级行为：当 LLM 不可用时"""
    
    @pytest.mark.asyncio
    async def test_generate_text_fallback_when_llm_unavailable(self):
        """LLM 不可用时，generate_text 返回降级内容"""
        from unittest.mock import patch
        
        from lumina_skills.content import generate_text
        
        # Mock get_client 返回 None（模拟 LLM 不可用）
        with patch("lumina_skills.content.get_client", return_value=None):
            result = await generate_text(
                topic="测试主题",
                platform="xiaohongshu",
                content_dna={},
                user_id="test",
            )
        
        # 验证返回了降级内容（包含明确提示）
        assert "暂时不可用" in result["title"]
        assert "暂时不可用" in result["content"]
    
    @pytest.mark.asyncio
    async def test_generate_script_fallback_when_llm_unavailable(self):
        """LLM 不可用时，generate_script 返回降级内容"""
        from unittest.mock import patch
        
        from lumina_skills.content import generate_script
        
        with patch("lumina_skills.content.get_client", return_value=None):
            result = await generate_script(
                topic="测试脚本",
                hook_type="curiosity",
                duration=60,
                platform="douyin",
                user_id="test",
            )
        
        # 验证返回了降级内容
        assert "暂时不可用" in result["hook_script"]
        assert "暂时不可用" in result["full_script"]
        # 但仍然有基本结构
        assert "shot_list" in result
        assert isinstance(result["shot_list"], list)


# ============ Entry Point for Manual Run ============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
