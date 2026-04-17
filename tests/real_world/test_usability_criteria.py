"""
可用性评估自动化测试

验证 UsabilityEvaluator 的各项评分逻辑，并演示如何对批量结果进行汇总。
"""

import pytest
from conftest import UsabilityEvaluator


class TestUsabilityEvaluator:
    """测试可用性评估器的评分规则。"""

    @pytest.fixture
    def ev(self):
        return UsabilityEvaluator()

    def test_hard_rules_all_pass(self, ev):
        """所有硬规则通过时，总分应不低于 0.6。"""
        response = {
            "reply": "你好，我建议你周三晚上8点发布内容，这样可以获得更高的曝光。",
            "intent": {"kind": "topic"},
            "hub": {"result": {"agent_calls": ["content_strategist"]}},
        }
        expected = {
            "kind": "topic",
            "agents": ["content_strategist"],
            "role": "individual_ip",
        }
        result = ev.evaluate(response, expected)
        assert result["hard_rules"]["has_reply"] is True
        assert result["hard_rules"]["has_intent"] is True
        assert result["hard_rules"]["no_uncaught_error"] is True
        assert result["total_score"] >= 0.6

    def test_hard_rules_missing_reply(self, ev):
        """缺少 reply 时，has_reply 应为 False。"""
        response = {
            "reply": "",
            "intent": {"kind": "topic"},
        }
        expected = {"kind": "topic", "agents": [], "role": "individual_ip"}
        result = ev.evaluate(response, expected)
        assert result["hard_rules"]["has_reply"] is False
        assert result["total_score"] < 0.7

    def test_soft_rules_actionable(self, ev):
        """包含行动建议时，actionable 应为高分。"""
        response = {"reply": "建议你首先优化标题，其次在周三晚上发布。"}
        expected = {"kind": "topic", "agents": [], "role": "individual_ip"}
        result = ev.evaluate(response, expected)
        assert result["soft_rules"]["actionable"] == 1.0

    def test_soft_rules_vague_content(self, ev):
        """包含空泛套话时，specific 应被扣分。"""
        response = {"reply": "只要持续努力，坚持不懈，一定会成功的。加油！"}
        expected = {"kind": "topic", "agents": [], "role": "individual_ip"}
        result = ev.evaluate(response, expected)
        assert result["soft_rules"]["specific"] < 0.5

    def test_role_context_matching(self, ev):
        """回复内容与角色语境匹配时得高分。"""
        response = {"reply": "你的矩阵账号可以分为主号和卫星号，协同发布内容。"}
        expected = {"kind": "general", "agents": [], "role": "mcn"}
        result = ev.evaluate(response, expected)
        assert result["soft_rules"]["role_context"] == 1.0

    def test_format_correct_script(self, ev):
        """脚本格式检查。"""
        response = {"reply": "镜头1：开场，时长3秒，台词'大家好'。BGM：轻快音乐。"}
        expected = {"kind": "script", "agents": [], "role": "individual_ip", "format": "script"}
        result = ev.evaluate(response, expected)
        assert result["soft_rules"]["format_correct"] == 1.0


class TestBatchUsabilityReport:
    """批量可用性报告汇总示例。"""

    def test_batch_report_demo(self):
        """演示如何对多个场景结果进行批量评分和汇总。"""
        ev = UsabilityEvaluator()
        scenarios = [
            {
                "id": "CRE-001",
                "response": {"reply": "这里是抖音文案，注意前三秒留人。", "intent": {"kind": "content"}},
                "expected": {"kind": "content", "agents": ["creative_studio"], "role": "individual_ip"},
            },
            {
                "id": "DAT-001",
                "response": {"reply": "请提供你的主页链接，我来帮你诊断。", "intent": {"kind": "diagnosis"}},
                "expected": {"kind": "diagnosis", "agents": ["data_analyst"], "role": "individual_ip"},
            },
        ]

        reports = []
        for s in scenarios:
            score = ev.evaluate(s["response"], s["expected"])
            reports.append({"id": s["id"], **score})

        # 汇总
        avg_score = sum(r["total_score"] for r in reports) / len(reports)
        pass_rate = sum(1 for r in reports if r["passed"]) / len(reports)

        assert avg_score > 0
        assert 0 <= pass_rate <= 1
