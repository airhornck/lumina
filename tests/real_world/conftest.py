"""
Real-World 测试共享 Fixture

提供：
- FastAPI TestClient
- Intent Engine 实例
- Orchestra 实例
- Mock / 真实调用切换控制
- 可用性评估工具
"""

import asyncio
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# 项目根目录
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _event_loop_policy():
    """Windows 下使用 SelectorEventLoopPolicy 避免 pytest teardown 时 Proactor 挂起。"""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    yield


# 确保 pytest 的 pythonpath 生效后也能直接 import
for p in (
    ROOT / "apps" / "api" / "src",
    ROOT / "apps" / "intent" / "src",
    ROOT / "apps" / "orchestra" / "src",
    ROOT / "apps" / "skill-hub" / "src",
    ROOT / "apps" / "rpa" / "src",
    ROOT / "packages" / "llm-hub" / "src",
    ROOT / "packages" / "knowledge-base" / "src",
    ROOT / "packages" / "lumina-skills" / "src",
    ROOT / "packages" / "skill-hub-client" / "src",
    ROOT / "packages" / "sop-engine" / "src",
    ROOT / "packages" / "agent-core" / "src",
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi.testclient import TestClient


# ============================================================================
# 环境控制
# ============================================================================

@pytest.fixture(scope="session")
def use_real_calls() -> bool:
    """是否使用真实 LLM / RPA 调用。默认 False（Mock 模式）。"""
    return os.environ.get("LUMINA_TEST_REAL_CALLS", "0") == "1"


# ============================================================================
# FastAPI TestClient
# ============================================================================

@pytest.fixture(scope="session")
def client() -> TestClient:
    """返回挂载了所有路由的 TestClient，并确保 lifespan（含 LLM Hub 初始化）被执行。"""
    from api.main import app
    with TestClient(app) as c:
        yield c


# ============================================================================
# 核心组件实例（按需初始化）
# ============================================================================

@pytest.fixture
def intent_engine():
    """返回 IntentEngine 实例。"""
    from intent.engine import IntentEngine
    return IntentEngine()


@pytest.fixture
def orchestra():
    """返回 MarketingOrchestra 实例。"""
    from orchestra.core import MarketingOrchestra
    return MarketingOrchestra()


# ============================================================================
# Mock 控制 Fixture
# ============================================================================

@pytest.fixture
def mock_llm_hub():
    """Mock LLMHub，避免真实调用大模型。"""
    with patch("llm_hub.hub.LLMHub") as MockHub:
        instance = MockHub.return_value
        instance.get_client = Mock(return_value=Mock(
            complete=AsyncMock(return_value="[MOCKED LLM RESPONSE]")
        ))
        yield instance


@pytest.fixture
def mock_skill_hub():
    """Mock SkillHubClient，返回预定义的技能结果。"""
    with patch("skill_hub_client.client.SkillHubClient") as MockClient:
        instance = MockClient.return_value
        instance.call = AsyncMock(return_value={
            "status": "mocked",
            "data": {"mock": True},
        })
        yield instance


# ============================================================================
# 测试数据 Fixture（三类角色）
# ============================================================================

@pytest.fixture
def persona_individual():
    """个人媒体工作者画像数据。"""
    return {
        "role": "individual_ip",
        "name": "小美",
        "industry": "职场穿搭",
        "platforms": ["douyin", "xiaohongshu"],
        "fans": 800,
        "budget": "low",
        "user_id_prefix": "u_individual",
    }


@pytest.fixture
def persona_shop():
    """小店铺经营者画像数据。"""
    return {
        "role": "small_shop",
        "name": "老王",
        "industry": "社区火锅店",
        "platforms": ["douyin"],
        "fans": 200,
        "budget": "low",
        "user_id_prefix": "u_shop",
    }


@pytest.fixture
def persona_mcn():
    """MCN 机构运营画像数据。"""
    return {
        "role": "mcn",
        "name": "李经理",
        "industry": "职场类达人矩阵",
        "platforms": ["douyin", "xiaohongshu"],
        "account_count": 20,
        "budget": "high",
        "user_id_prefix": "u_mcn",
    }


# ============================================================================
# 可用性评估工具
# ============================================================================

class UsabilityEvaluator:
    """对 Orchestra / Skill 返回结果进行自动化可用性评分。"""

    def __init__(self):
        self.hard_rules = [
            ("has_reply", self._check_has_reply),
            ("has_intent", self._check_has_intent),
            ("has_agent_calls", self._check_has_agent_calls),
            ("no_uncaught_error", self._check_no_error),
        ]
        self.soft_rules = [
            ("actionable", self._score_actionable),
            ("specific", self._score_specific),
            ("role_context", self._score_role_context),
            ("format_correct", self._score_format_correct),
        ]

    def evaluate(self, response: dict, expected: dict) -> dict:
        """
        response: API 返回的 JSON
        expected: 预期信息（kind, agent, role, platform 等）
        """
        hard_scores = {}
        for name, fn in self.hard_rules:
            hard_scores[name] = fn(response, expected)

        soft_scores = {}
        for name, fn in self.soft_rules:
            soft_scores[name] = fn(response, expected)

        hard_avg = sum(hard_scores.values()) / len(hard_scores) if hard_scores else 0
        soft_avg = sum(soft_scores.values()) / len(soft_scores) if soft_scores else 0
        total = hard_avg * 0.6 + soft_avg * 0.4

        return {
            "hard_rules": hard_scores,
            "soft_rules": soft_scores,
            "total_score": round(total, 3),
            "passed": total >= 0.70,
        }

    # ---- 硬规则 ----
    def _check_has_reply(self, resp, expected):
        reply = resp.get("reply") or (resp.get("hub") or {}).get("result", {}).get("reply")
        return bool(reply and isinstance(reply, str) and len(reply.strip()) > 0)

    def _check_has_intent(self, resp, expected):
        intent = resp.get("intent") or {}
        return intent.get("kind") == expected.get("kind")

    def _check_has_agent_calls(self, resp, expected):
        # 简化：检查 response 中是否包含预期的 agent 名称或 skill 调用痕迹
        text = str(resp)
        expected_agents = expected.get("agents", [])
        return any(agent in text for agent in expected_agents)

    def _check_no_error(self, resp, expected):
        return "error" not in str(resp).lower() or resp.get("status_code", 200) < 500

    # ---- 软规则（简化版，后续可接入 LLM 判分）----
    def _score_actionable(self, resp, expected):
        reply = resp.get("reply", "")
        actionable_keywords = ["建议", "步骤", "首先", "其次", "最后", "可以", "需要", "推荐"]
        return 1.0 if any(kw in reply for kw in actionable_keywords) else 0.3

    def _score_specific(self, resp, expected):
        reply = resp.get("reply", "")
        vague_phrases = ["持续努力", "坚持不懈", "一定会成功", "加油", "只要用心"]
        vague_count = sum(1 for p in vague_phrases if p in reply)
        return max(0.0, 1.0 - vague_count * 0.3)

    def _score_role_context(self, resp, expected):
        reply = resp.get("reply", "")
        role = expected.get("role", "")
        role_keywords = {
            "individual_ip": ["粉丝", "账号", "内容", "IP", "人设", "起号"],
            "small_shop": ["顾客", "门店", "本地", "团购", "引流", "附近"],
            "mcn": ["矩阵", "账号", "批量", "协同", "达人", "SOP"],
        }
        keywords = role_keywords.get(role, [])
        return 1.0 if any(kw in reply for kw in keywords) else 0.4

    def _score_format_correct(self, resp, expected):
        reply = resp.get("reply", "")
        fmt = expected.get("format", "")
        if fmt == "script":
            return 1.0 if any(k in reply for k in ["镜头", "台词", "时长", "画面", "BGM"]) else 0.3
        if fmt == "copy":
            return 1.0 if any(k in reply for k in ["标题", "正文", "标签", "文案"]) else 0.5
        return 1.0


@pytest.fixture
def evaluator() -> UsabilityEvaluator:
    return UsabilityEvaluator()
