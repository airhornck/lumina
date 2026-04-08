"""
意图识别引擎主入口

整合 L1/L2/L3 三层架构，提供统一的意图识别接口
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from .models import Intent, IntentType, SessionContext
from .l1_rules import L1RuleEngine
from .l2_memory import HybridMemoryStore
from .l3_llm import LLMClassifier
from .calibrator import ConfidenceCalibrator, DynamicThreshold
from .switch_detector import IntentSwitchDetector
from .clarification import ClarificationEngine
from .cache import IntentCache


class IntentEngine:
    """
    工业级意图识别引擎
    
    四级架构：
    - L1: 规则引擎（零成本）
    - L2: 向量记忆
    - L2.5: 轻量分类器（可选）
    - L3: LLM 分类器（兜底）
    
    增强特性：
    - 置信度校准
    - 动态阈值
    - 意图切换检测
    - 智能澄清
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        vector_store=None,
        llm_client=None,
        redis_client=None,
        calibrator_path: Optional[str] = None,
        enable_classifier: bool = False
    ):
        """
        初始化意图引擎
        
        Args:
            config_path: L1 规则配置文件路径
            vector_store: 向量数据库实例
            llm_client: LLM 客户端
            redis_client: Redis 客户端
            calibrator_path: 校准器模型路径
            enable_classifier: 是否启用 L2.5 轻量分类器
        """
        # L1: 规则引擎
        self.l1_rules = L1RuleEngine(config_path)
        
        # L2: 向量记忆
        self.l2_memory = HybridMemoryStore(vector_store)
        
        # L2.5: 轻量分类器（可选）
        self.l2_5_classifier = None
        if enable_classifier:
            self.l2_5_classifier = self._init_classifier()
        
        # L3: LLM 分类器
        self.l3_llm = LLMClassifier(llm_client)
        
        # 增强组件
        self.calibrator = ConfidenceCalibrator(calibrator_path)
        self.threshold_manager = DynamicThreshold(base_threshold=0.7)
        self.switch_detector = IntentSwitchDetector()
        self.clarification = ClarificationEngine()
        self.cache = IntentCache(redis_client)
    
    def _init_classifier(self):
        """初始化轻量分类器"""
        try:
            from .l2_5_classifier import LightweightClassifier
            return LightweightClassifier()
        except ImportError:
            return None
    
    async def recognize(
        self, 
        text: str, 
        user_id: str, 
        session_context: Optional[Dict[str, Any]] = None
    ) -> Intent:
        """
        识别用户意图
        
        Args:
            text: 用户输入文本
            user_id: 用户ID
            session_context: 会话上下文（可选）
        
        Returns:
            Intent 对象
        """
        session = session_context or {}
        
        # 1. 缓存检查
        cached = await self.cache.get(text, session)
        if cached:
            return cached
        
        # 2. L1 规则层
        intent = self.l1_rules.match(text)
        if intent and intent.type != IntentType.AMBIGUOUS:
            await self._store_and_cache(text, user_id, session, intent)
            return intent
        
        # 3. L2 向量记忆层
        intent = await self.l2_memory.similarity_search(text, user_id)
        if intent and intent.confidence > 0.85:
            await self._store_and_cache(text, user_id, session, intent)
            return intent
        
        # 4. L2.5 轻量分类器（如果启用）
        if self.l2_5_classifier:
            label, conf = await self.l2_5_classifier.predict(text)
            if conf > 0.9:
                intent = Intent(
                    type=IntentType(label),
                    confidence=conf,
                    reason="l2_5_classifier"
                )
                if intent.type != IntentType.AMBIGUOUS:
                    await self._store_and_cache(text, user_id, session, intent)
                    return intent
        
        # 5. L3 LLM 分类器
        prior = await self.l2_memory.get_prior_probability(user_id)
        session_ctx = SessionContext(
            user_id=user_id,
            session_id=session.get("session_id", ""),
            previous_intent=session.get("previous_intent"),
            previous_topic=session.get("previous_topic"),
            user_history_count=session.get("user_history_count", 0),
            intent_switch_count=session.get("intent_switch_count", 0)
        )
        
        intent = await self.l3_llm.classify(text, session_ctx, prior)
        
        # 6. 置信度校准
        intent.confidence = self.calibrator.calibrate(intent.confidence)
        
        # 7. 动态阈值判定
        threshold = self.threshold_manager.get_threshold(user_id, session)
        if intent.confidence < threshold:
            intent.type = IntentType.AMBIGUOUS
            intent.reason = f"low_confidence ({intent.confidence:.2f} < {threshold:.2f})"
            intent.requires_clarification = True
        
        # 8. 意图切换检测
        if intent.type != IntentType.AMBIGUOUS:
            if self.switch_detector.detect(intent, session):
                # 检测到切换，生成澄清
                switch_clarification = self.clarification.generate_switch_clarification(
                    session.get("previous_intent", ""),
                    intent.subtype or intent.type.value
                )
                intent.type = IntentType.AMBIGUOUS
                intent.reason = "potential_topic_switch"
                intent.requires_clarification = True
                intent.clarification_questions = switch_clarification["questions"]
                intent.clarification_options = switch_clarification["suggestions"]
        
        # 9. 处理模糊意图
        if intent.type == IntentType.AMBIGUOUS and not intent.requires_clarification:
            clarification = await self.clarification.handle_ambiguous(
                text, user_id, session
            )
            intent.requires_clarification = True
            intent.clarification_questions = clarification.get("questions", [])
            intent.clarification_options = clarification.get("suggestions", [])
        
        # 10. 缓存并返回
        await self._store_and_cache(text, user_id, session, intent)
        return intent
    
    async def _store_and_cache(
        self, 
        text: str, 
        user_id: str, 
        session: Dict[str, Any],
        intent: Intent
    ) -> None:
        """存储到记忆并缓存"""
        # 只缓存明确的意图
        if intent.type != IntentType.AMBIGUOUS:
            await self.l2_memory.store(text, intent, user_id)
        await self.cache.set(text, session, intent)
    
    async def handle_clarification_response(
        self,
        user_response: str,
        original_text: str,
        possible_intents: list,
        user_id: str,
        session_context: Optional[Dict[str, Any]] = None
    ) -> Intent:
        """
        处理用户对澄清问题的回复
        
        Args:
            user_response: 用户回复
            original_text: 原始输入
            possible_intents: 之前提供的选项
            user_id: 用户ID
            session_context: 会话上下文
        
        Returns:
            确认的意图
        """
        # 简单的关键词匹配确认
        response = user_response.lower()
        
        for intent_key in possible_intents:
            if intent_key.lower() in response:
                return Intent(
                    type=IntentType.MARKETING,
                    subtype=intent_key,
                    confidence=0.9,
                    reason="clarification_confirmed"
                )
        
        # 用户说"不是"或"其他"
        if any(word in response for word in ["不是", "否", "其他", "别的"]):
            return Intent(
                type=IntentType.AMBIGUOUS,
                confidence=0.0,
                reason="clarification_rejected",
                requires_clarification=True,
                clarification_questions=["请具体说说你想做什么？我可以帮你诊断账号、创作文案、分析流量等。"]
            )
        
        # 重新识别
        return await self.recognize(user_response, user_id, session_context)
