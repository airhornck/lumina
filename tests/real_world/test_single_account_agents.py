"""
真实用户场景 — 单账号运营 Agent 组测试

覆盖 6 个 Agent：
- content_strategist
- creative_studio
- data_analyst
- growth_hacker
- community_manager
- compliance_officer

每个 Agent 对应 1~3 个真实用户场景。
"""

import pytest


# =============================================================================
# Agent: content_strategist → Skill: skill-content-strategist
# =============================================================================

class TestContentStrategist:
    """内容策略师 — 账号定位、选题策略、竞品分析。"""

    def test_individual_positioning(self, client, evaluator, persona_individual):
        """场景 STR-001：个人IP账号定位。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "我是做职场穿搭的，账号怎么定位？",
            "user_id": "u_individual_str_001",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        eval_result = evaluator.evaluate(data, {
            "kind": "topic",
            "agents": ["content_strategist"],
            "role": persona_individual["role"],
        })
        assert eval_result["passed"], f"可用性评分不足: {eval_result}"

    def test_individual_topic_calendar(self, client, evaluator, persona_individual):
        """场景 STR-002：生成选题日历。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我生成未来一周的选题日历",
            "user_id": "u_individual_str_002",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        assert "周一" in reply or "周二" in reply or "选题" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "topic",
            "agents": ["content_strategist"],
            "role": persona_individual["role"],
        })
        assert eval_result["passed"]

    def test_shop_positioning(self, client, evaluator, persona_shop):
        """场景 STR-003：本地生活店铺定位。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "火锅店怎么在抖音上定位",
            "user_id": "u_shop_str_003",
            "platform": "douyin",
        })
        assert r.status_code == 200
        data = r.json()
        eval_result = evaluator.evaluate(data, {
            "kind": "topic",
            "agents": ["content_strategist"],
            "role": persona_shop["role"],
        })
        assert eval_result["passed"]


# =============================================================================
# Agent: creative_studio → Skill: skill-creative-studio
# =============================================================================

class TestCreativeStudio:
    """创意工厂 — 文案生成、脚本创作、标题优化。"""

    def test_individual_copywriting_douyin(self, client, evaluator, persona_individual):
        """场景 CRE-001：抖音职场穿搭文案。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我写一条抖音文案，主题是'面试穿搭避雷'",
            "user_id": "u_individual_cre_001",
            "platform": "douyin",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        assert "面试" in reply or "穿搭" in reply or "避雷" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "content",
            "agents": ["creative_studio"],
            "role": persona_individual["role"],
            "format": "copy",
        })
        assert eval_result["passed"]

    def test_shop_xiaohongshu_note(self, client, evaluator, persona_shop):
        """场景 CRE-002：小红书火锅店种草笔记。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "写个小红书笔记，推广我家火锅店的招牌毛肚",
            "user_id": "u_shop_cre_002",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        assert "毛肚" in reply or "火锅" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "content",
            "agents": ["creative_studio"],
            "role": persona_shop["role"],
            "format": "copy",
        })
        assert eval_result["passed"]

    def test_individual_script(self, client, evaluator, persona_individual):
        """场景 CRE-003：短视频脚本。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我写一个30秒的短视频脚本，讲职场新人穿搭",
            "user_id": "u_individual_cre_003",
            "platform": "douyin",
        })
        assert r.status_code == 200
        data = r.json()
        eval_result = evaluator.evaluate(data, {
            "kind": "script",
            "agents": ["creative_studio"],
            "role": persona_individual["role"],
            "format": "script",
        })
        assert eval_result["passed"]

    def test_shop_title_optimization(self, client, evaluator, persona_shop):
        """场景 CRE-004：标题优化。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "优化这个标题：火锅店开业了",
            "user_id": "u_shop_cre_004",
            "platform": "douyin",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        assert "标题" in reply or "优化" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "content",
            "agents": ["creative_studio"],
            "role": persona_shop["role"],
        })
        assert eval_result["passed"]


# =============================================================================
# Agent: data_analyst → Skill: skill-data-analyst
# =============================================================================

class TestDataAnalyst:
    """数据分析师 — 账号诊断、流量分析、周报生成。"""

    def test_individual_diagnosis(self, client, evaluator, persona_individual):
        """场景 DAT-001：账号诊断（无URL，预期引导澄清）。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我诊断一下账号",
            "user_id": "u_individual_dat_001",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        # 未提供账号链接时，系统应引导用户提供
        assert "链接" in reply or "主页" in reply or "账号" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "diagnosis",
            "agents": ["data_analyst", "content_strategist"],
            "role": persona_individual["role"],
        })
        assert eval_result["passed"]

    def test_shop_traffic_drop(self, client, evaluator, persona_shop):
        """场景 DAT-002：流量下跌分析。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "我最近的流量为什么跌了",
            "user_id": "u_shop_dat_002",
            "platform": "douyin",
        })
        assert r.status_code == 200
        data = r.json()
        eval_result = evaluator.evaluate(data, {
            "kind": "traffic",
            "agents": ["data_analyst", "growth_hacker"],
            "role": persona_shop["role"],
        })
        assert eval_result["passed"]

    def test_individual_weekly_report(self, client, evaluator, persona_individual):
        """场景 DAT-004：周报生成。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "生成我上周的数据周报",
            "user_id": "u_individual_dat_004",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        assert "周" in reply or "数据" in reply or "报告" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "traffic",
            "agents": ["data_analyst"],
            "role": persona_individual["role"],
        })
        assert eval_result["passed"]


# =============================================================================
# Agent: growth_hacker → Skill: skill-growth-hacker
# =============================================================================

class TestGrowthHacker:
    """投放优化师 — 投放策略、A/B测试、增长策略。"""

    def test_shop_local_ad_strategy(self, client, evaluator, persona_shop):
        """场景 GRW-001：本地推广策略。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "我想在抖音投本地推广，怎么设置",
            "user_id": "u_shop_grw_001",
            "platform": "douyin",
        })
        assert r.status_code == 200
        data = r.json()
        eval_result = evaluator.evaluate(data, {
            "kind": "traffic",
            "agents": ["growth_hacker"],
            "role": persona_shop["role"],
        })
        assert eval_result["passed"]

    def test_shop_ab_test(self, client, evaluator, persona_shop):
        """场景 GRW-002：A/B测试设计。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我设计一个A/B测试，看哪个标题更好",
            "user_id": "u_shop_grw_002",
            "platform": "douyin",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        assert "A" in reply or "B" in reply or "测试" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "traffic",
            "agents": ["growth_hacker"],
            "role": persona_shop["role"],
        })
        assert eval_result["passed"]


# =============================================================================
# Agent: community_manager → Skill: skill-community-manager
# =============================================================================

class TestCommunityManager:
    """用户运营官 — 评论回复、粉丝分层、自动回复。"""

    def test_individual_comment_reply(self, client, evaluator, persona_individual):
        """场景 COM-001：评论回复生成。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "有人评论'衣服哪里买'，帮我回复",
            "user_id": "u_individual_com_001",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        assert "买" in reply or "链接" in reply or "店铺" in reply or "私信" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "conversation",  # 当前系统可能映射为 conversation
            "agents": ["community_manager"],
            "role": persona_individual["role"],
        })
        assert eval_result["passed"]

    def test_individual_fan_segmentation(self, client, evaluator, persona_individual):
        """场景 COM-002：粉丝分层分析。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我分析一下粉丝画像，分分层",
            "user_id": "u_individual_com_002",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        assert "粉丝" in reply or "分层" in reply or "活跃" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "conversation",
            "agents": ["community_manager"],
            "role": persona_individual["role"],
        })
        assert eval_result["passed"]


# =============================================================================
# Agent: compliance_officer → Skill: skill-compliance-officer
# =============================================================================

class TestComplianceOfficer:
    """合规审查员 — 风险检测、账号健康、替代方案。"""

    def test_shop_risk_check(self, client, evaluator, persona_shop):
        """场景 CMP-001：文案风险检查。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "帮我检查这个文案有没有违规风险：全网最低价，错过再等一年！",
            "user_id": "u_shop_cmp_001",
            "platform": "douyin",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        assert "违规" in reply or "风险" in reply or "极限词" in reply or "修改" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "risk",
            "agents": ["compliance_officer"],
            "role": persona_shop["role"],
        })
        assert eval_result["passed"]

    def test_individual_risk_query(self, client, evaluator, persona_individual):
        """场景 CMP-002：具体风险词询问。"""
        r = client.post("/api/v1/marketing/hub", json={
            "user_input": "说'全网最低价'会不会被限流",
            "user_id": "u_individual_cmp_002",
            "platform": "xiaohongshu",
        })
        assert r.status_code == 200
        data = r.json()
        reply = data.get("reply", "")
        # 系统已正确识别为 risk 并返回风险等级/命中词/修改建议
        assert "风险" in reply or "违规" in reply or "极限词" in reply or "敏感词" in reply or "medium" in reply or "high" in reply
        eval_result = evaluator.evaluate(data, {
            "kind": "risk",
            "agents": ["compliance_officer"],
            "role": persona_individual["role"],
        })
        assert eval_result["passed"]
