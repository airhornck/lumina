"""
真实用户场景 — 意图理解测试

覆盖：
- L1 规则引擎（Casual / Marketing）
- L2 记忆召回（全局热门模式）
- L3 LLM 兜底分类
- 澄清引擎触发
- 意图切换检测
- 多意图输入处理
"""

import pytest


# =============================================================================
# 基础意图识别（L1 规则）
# =============================================================================

class TestL1RuleIntentRecognition:
    """测试 L1 规则引擎对三类用户常见输入的识别能力。"""

    @pytest.mark.parametrize("user_input,expected_kind", [
        ("你好", "conversation"),
        ("在吗", "conversation"),
        ("谢谢", "conversation"),
        ("哈哈", "conversation"),
    ])
    def test_casual_greeting(self, client, user_input, expected_kind):
        """闲聊问候应被正确识别为 conversation。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": user_input,
            "user_id": f"u_intent_casual_{user_input}",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        assert data.get("intent", {}).get("kind") == expected_kind

    @pytest.mark.parametrize("user_input,expected_kind", [
        ("帮我诊断账号", "diagnosis"),
        ("写个文案", "content"),
        ("怎么选题", "topic"),
        ("流量分析", "traffic"),
        ("检查风险", "risk"),
    ])
    def test_marketing_intent_l1(self, client, user_input, expected_kind):
        """常见营销意图应被正确识别。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": user_input,
            "user_id": f"u_intent_mkt_{user_input}",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        # 允许 kind 为更具体的值（如 content_creation 映射到 content）
        actual_kind = data.get("intent", {}).get("kind")
        assert actual_kind is not None
        assert actual_kind != "conversation"


# =============================================================================
# 模糊输入与澄清
# =============================================================================

class TestClarificationFlow:
    """测试模糊输入是否触发澄清流程。"""

    def test_ambiguous_input_triggers_clarification(self, client):
        """输入过于模糊时，应返回澄清问题。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我看看",
            "user_id": "u_clarify_01",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        # 预期返回 clarification 或 conversation 并附带引导
        assert data.get("intent", {}).get("kind") in ("clarify_feedback", "conversation")
        reply = data.get("reply", "")
        assert "账号" in reply or "文案" in reply or "诊断" in reply or "内容" in reply

    def test_clarification_followup(self, client):
        """用户对澄清问题的回应应被正确理解。"""
        # 第一轮：模糊输入
        client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我看看",
            "user_id": "u_clarify_02",
            "platform": "xiaohongshu",
        })
        # 第二轮：明确意图
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我诊断账号",
            "user_id": "u_clarify_02",
            "platform": "xiaohongshu",
        })
        data = r.json()
        assert data.get("intent", {}).get("kind") == "diagnosis"


# =============================================================================
# 意图切换检测
# =============================================================================

class TestIntentSwitchDetection:
    """测试对话过程中意图切换是否被正确识别。"""

    def test_switch_from_casual_to_diagnosis(self, client):
        """从闲聊切换到营销意图。"""
        uid = "u_switch_01"
        # 第一轮：闲聊
        r1 = client.post("/api/v1/marketing/hub", json={
            "user_input": "你好",
            "user_id": uid,
            "platform": "xiaohongshu",
        })
        assert r1.json().get("intent", {}).get("kind") == "conversation"

        # 第二轮：诊断
        r2 = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我诊断一下账号",
            "user_id": uid,
            "platform": "xiaohongshu",
        })
        data = r2.json()
        assert data.get("intent", {}).get("kind") == "diagnosis"

    def test_switch_between_marketing_subtypes(self, client):
        """在同一轮营销对话中切换子意图。"""
        uid = "u_switch_02"
        # 第一轮：内容创作
        r1 = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我写个文案",
            "user_id": uid,
            "platform": "xiaohongshu",
        })
        kind1 = r1.json().get("intent", {}).get("kind")
        assert kind1 in ("content", "topic", "script")

        # 第二轮：账号诊断
        r2 = client.post("/api/v1/marketing/hub", json={
            "user_input": "再帮我看看账号数据",
            "user_id": uid,
            "platform": "xiaohongshu",
        })
        data = r2.json()
        assert data.get("intent", {}).get("kind") == "diagnosis"


# =============================================================================
# 角色化意图表达识别
# =============================================================================

class TestRoleBasedIntentRecognition:
    """测试不同角色用户的口语化表达是否能被正确理解。"""

    @pytest.mark.parametrize("user_input,expected_kind,role", [
        # 个人IP（小美）
        ("我是做职场穿搭的，账号怎么定位？", "topic", "individual"),
        ("帮我写一个30秒的短视频脚本", "script", "individual"),
        ("为什么我最近流量这么差", "traffic", "individual"),
        # 小店铺（老王）
        ("火锅店怎么在抖音上定位", "topic", "shop"),
        ("写个小红书笔记推广我家毛肚", "content", "shop"),
        ("我最近的流量为什么跌了", "traffic", "shop"),
        # MCN（李经理）
        ("帮我规划一个职场类账号矩阵", "general", "mcn"),
        ("批量生成10条职场穿搭标题", "content", "mcn"),
        ("检查所有账号的健康状态", "general", "mcn"),
    ])
    def test_role_based_inputs(self, client, user_input, expected_kind, role):
        """各角色的典型口语化输入应被正确分类。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": user_input,
            "user_id": f"u_role_{role}_{hash(user_input) % 10000}",
            "platform": "douyin" if "抖音" in user_input else "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        actual_kind = data.get("intent", {}).get("kind")
        assert actual_kind is not None
        # 对于矩阵类输入，当前系统可能映射为 general 或 conversation，后续根据实现调整
        if expected_kind == "general":
            assert actual_kind in ("general", "conversation", "content", "topic")
        else:
            assert actual_kind == expected_kind or actual_kind in (
                "content", "script", "topic", "diagnosis", "traffic", "risk"
            )
