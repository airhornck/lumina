"""
Intent Engine 测试套件

Phase 1 测试覆盖：
- L1 规则引擎
- L2 向量记忆
- L3 LLM 分类器
- 置信度校准
- 意图切换检测
- 澄清引擎
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'intent', 'src'))

from intent.models import Intent, IntentType, SessionContext
from intent.l1_rules import L1RuleEngine
from intent.l2_memory import HybridMemoryStore
from intent.l3_llm import LLMClassifier
from intent.calibrator import ConfidenceCalibrator, DynamicThreshold
from intent.switch_detector import IntentSwitchDetector
from intent.clarification import ClarificationEngine
from intent.engine import IntentEngine


class TestL1RuleEngine:
    """L1 规则引擎测试"""
    
    def test_casual_greeting(self):
        """测试闲聊问候识别"""
        engine = L1RuleEngine()
        
        casual_inputs = [
            "你好",
            "在吗",
            "谢谢",
            "哈哈",
            "👋",
            "hello",
            "hi",
        ]
        
        for text in casual_inputs:
            result = engine.match(text)
            assert result is not None, f"'{text}' 应该被识别为 casual"
            assert result.type == IntentType.CASUAL
            assert result.confidence == 1.0
    
    def test_marketing_intent(self):
        """测试营销意图识别"""
        engine = L1RuleEngine()
        
        marketing_inputs = [
            ("帮我诊断一下账号", "diagnosis"),
            ("写个文案", "content_creation"),
            ("怎么选题", "strategy"),
            ("流量分析", "traffic_analysis"),
            ("检查风险", "risk_check"),
        ]
        
        for text, expected_subtype in marketing_inputs:
            result = engine.match(text)
            assert result is not None, f"'{text}' 应该被识别"
            assert result.type == IntentType.MARKETING
            assert result.confidence == 0.95
    
    def test_ambiguous_input(self):
        """测试模糊输入"""
        engine = L1RuleEngine()
        
        # 不在任何规则中的输入
        ambiguous_inputs = [
            "这个",
            "那个",
            "...",
        ]
        
        for text in ambiguous_inputs:
            result = engine.match(text)
            assert result is None, f"'{text}' 应该返回 None 进入 L2"


class TestL2Memory:
    """L2 向量记忆测试"""
    
    @pytest.mark.asyncio
    async def test_global_pattern_match(self):
        """测试全局模式匹配"""
        store = HybridMemoryStore(vector_store=None)
        
        # 测试全局热门模式
        result = await store.similarity_search("帮我看看这个账号", "user_123")
        assert result is not None
        assert result.type == IntentType.MARKETING
        assert result.subtype == "diagnosis"
    
    @pytest.mark.asyncio
    async def test_prior_probability(self):
        """测试先验概率计算"""
        store = HybridMemoryStore(vector_store=None)
        
        # 无历史用户返回默认先验
        prior = await store.get_prior_probability("new_user")
        assert prior == 0.3


class TestL3LLMClassifier:
    """L3 LLM 分类器测试"""
    
    @pytest.mark.asyncio
    async def test_classify_with_mock(self):
        """测试分类（使用 mock）"""
        mock_llm = Mock()
        mock_llm.complete = AsyncMock(return_value='''
        {
            "intent_type": "marketing",
            "subtype": "diagnosis",
            "confidence": 0.85,
            "entities": {},
            "reason": "账号相关查询"
        }
        ''')
        
        classifier = LLMClassifier(llm_client=mock_llm)
        session_ctx = SessionContext(
            user_id="user_123",
            session_id="session_456"
        )
        
        result = await classifier.classify("帮我诊断账号", session_ctx)
        
        assert result.type == IntentType.MARKETING
        assert result.subtype == "diagnosis"
        assert result.confidence == 0.85


class TestConfidenceCalibrator:
    """置信度校准器测试"""
    
    def test_identity_calibration(self):
        """测试恒等校准（无训练数据时）"""
        calibrator = ConfidenceCalibrator(model_path=None)
        
        # 恒等映射：输入等于输出
        assert calibrator.calibrate(0.0) == 0.0
        assert calibrator.calibrate(0.5) == 0.5
        assert calibrator.calibrate(1.0) == 1.0
    
    def test_bounds(self):
        """测试边界处理"""
        calibrator = ConfidenceCalibrator(model_path=None)
        
        # 超出范围的值应该被截断
        assert calibrator.calibrate(-0.5) == 0.0
        assert calibrator.calibrate(1.5) == 1.0


class TestDynamicThreshold:
    """动态阈值测试"""
    
    def test_base_threshold(self):
        """测试基础阈值"""
        threshold_mgr = DynamicThreshold(base_threshold=0.7)
        
        # 新用户使用基础阈值
        threshold = threshold_mgr.get_threshold("user_123", {
            "user_history_count": 0
        })
        assert threshold == 0.7
    
    def test_high_active_user(self):
        """测试高活跃用户阈值降低"""
        threshold_mgr = DynamicThreshold(base_threshold=0.7)
        
        # 高活跃用户阈值应该降低
        threshold = threshold_mgr.get_threshold("user_123", {
            "user_history_count": 60,
            "previous_intent": "marketing"
        })
        
        # 高活跃(-0.1) + 营销上下文(-0.05) = 0.55
        assert threshold < 0.7


class TestIntentSwitchDetector:
    """意图切换检测器测试"""
    
    def test_no_switch(self):
        """测试无切换"""
        detector = IntentSwitchDetector()
        
        session = {"previous_intent": "marketing"}
        new_intent = Intent(
            type=IntentType.MARKETING,
            subtype="diagnosis",
            confidence=0.9
        )
        
        result = detector.detect(new_intent, session)
        assert result is False
    
    def test_switch_detected(self):
        """测试检测到切换"""
        detector = IntentSwitchDetector(switch_penalty_threshold=2)
        
        session = {
            "previous_intent": "marketing",
            "intent_switch_count": 1
        }
        new_intent = Intent(
            type=IntentType.CASUAL,
            confidence=0.9
        )
        
        result = detector.detect(new_intent, session)
        assert result is True


class TestClarificationEngine:
    """澄清引擎测试"""
    
    @pytest.mark.asyncio
    async def test_single_possible_intent(self):
        """测试单一可能意图"""
        engine = ClarificationEngine()
        
        result = await engine.handle_ambiguous(
            "帮我看看",
            "user_123",
            {},
            possible_intents=["diagnosis"]
        )
        
        assert result["requires_clarification"] is True
        assert "账号诊断" in result["questions"][0]
        assert len(result["suggestions"]) == 2  # 确认 + 否定


class TestIntentEngineIntegration:
    """Intent Engine 集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_pipeline_casual(self):
        """测试完整流程 - 闲聊"""
        engine = IntentEngine()
        
        result = await engine.recognize("你好", "user_123")
        
        assert result.type == IntentType.CASUAL
        assert result.confidence == 1.0
        assert result.reason == "l1_casual_rule"
    
    @pytest.mark.asyncio
    async def test_full_pipeline_marketing(self):
        """测试完整流程 - 营销意图"""
        engine = IntentEngine()
        
        result = await engine.recognize("帮我诊断账号", "user_123")
        
        assert result.type == IntentType.MARKETING
        assert result.subtype == "diagnosis"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
