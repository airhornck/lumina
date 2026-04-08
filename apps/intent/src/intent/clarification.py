"""
澄清引擎

当意图模糊或检测到切换时，生成澄清问题
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional

from .models import Intent, IntentType


class ClarificationEngine:
    """
    澄清引擎
    
    生成智能澄清问题，帮助明确用户意图
    """
    
    # 热门意图推荐（用于完全未知的情况）
    HOT_INTENTS = ["账号诊断", "文案生成", "选题建议", "流量分析", "脚本创作"]
    
    # 意图类型到中文的映射
    INTENT_NAMES = {
        "diagnosis": "账号诊断",
        "content_creation": "文案/标题创作",
        "script_creation": "视频脚本创作",
        "strategy": "选题/定位策略",
        "traffic_analysis": "流量分析",
        "risk_check": "风险检查",
        "matrix_setup": "矩阵规划",
        "bulk_creation": "批量创作",
        "knowledge_qa": "知识问答",
    }
    
    def __init__(self):
        pass
    
    async def handle_ambiguous(
        self, 
        text: str, 
        user_id: str, 
        session: Dict[str, Any],
        possible_intents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        处理模糊意图
        
        Args:
            text: 用户输入
            user_id: 用户ID
            session: 会话状态
            possible_intents: 可能的意图列表（可选）
        
        Returns:
            包含澄清问题和选项的字典
        """
        # 1. 尝试指代消解
        coreference_result = await self._resolve_coreference(text, session)
        if coreference_result.get("resolved"):
            return coreference_result
        
        # 2. 基于可能意图生成澄清
        if possible_intents and len(possible_intents) == 1:
            # 只有一个可能，直接确认
            intent_name = self.INTENT_NAMES.get(possible_intents[0], possible_intents[0])
            return {
                "requires_clarification": True,
                "questions": [f"你是想{intent_name}吗？请确认一下。"],
                "suggestions": [intent_name, "不是，我说的是其他"],
                "context": "single_possible",
                "possible_intents": possible_intents
            }
        
        elif possible_intents and len(possible_intents) >= 2:
            # 多个可能，提供选项
            options = [self.INTENT_NAMES.get(p, p) for p in possible_intents[:3]]
            return {
                "requires_clarification": True,
                "questions": [f"请问你是想：{'，还是'.join(options)}？"],
                "suggestions": options + ["都不是"],
                "context": "multiple_possible",
                "possible_intents": possible_intents
            }
        
        # 3. 完全未知，给出通用引导
        return await self._generate_generic_clarification(text, session)
    
    async def _resolve_coreference(
        self, 
        text: str, 
        session: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        指代消解
        
        处理"帮我诊断一下"、"再写一个"等依赖上下文的输入
        """
        # 指代词列表
        pronouns = ["这个", "那个", "它", "帮我", "再", "继续"]
        
        has_pronoun = any(p in text for p in pronouns)
        previous_topic = session.get("previous_topic")
        previous_intent = session.get("previous_intent")
        
        if has_pronoun and previous_intent and previous_topic:
            # 可能可以消解
            return {
                "resolved": True,
                "questions": [f"你是想继续{self.INTENT_NAMES.get(previous_intent, previous_intent)}吗？"],
                "suggestions": ["是的", "不是，我说的是其他"],
                "context": "coreference_resolution",
                "inferred_intent": previous_intent
            }
        
        return {"resolved": False}
    
    async def _generate_generic_clarification(
        self, 
        text: str, 
        session: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成通用澄清"""
        
        # 检查是否包含营销关键词但不明确
        marketing_hints = ["账号", "内容", "文案", "流量", "小红书", "抖音"]
        has_marketing_hint = any(h in text for h in marketing_hints)
        
        if has_marketing_hint:
            return {
                "requires_clarification": True,
                "questions": ["我理解了你想聊营销相关的话题，能具体说说你想做什么吗？"],
                "suggestions": self.HOT_INTENTS,
                "context": "marketing_hint",
            }
        
        # 完全不清楚
        return {
            "requires_clarification": True,
            "questions": [
                "我没太理解你的问题。你是想咨询营销相关的问题，还是其他？",
                "我可以帮你做账号诊断、文案创作、选题建议等。"
            ],
            "suggestions": ["咨询营销问题"] + self.HOT_INTENTS[:3],
            "context": "complete_unknown",
        }
    
    def generate_switch_clarification(
        self,
        previous_intent: str,
        new_intent: str
    ) -> Dict[str, Any]:
        """
        生成意图切换澄清
        
        当检测到用户可能切换话题时使用
        """
        prev_name = self.INTENT_NAMES.get(previous_intent, previous_intent)
        new_name = self.INTENT_NAMES.get(new_intent, new_intent)
        
        return {
            "requires_clarification": True,
            "questions": [f"刚才我们在聊{prev_name}，你现在是想切换到{new_name}吗？"],
            "suggestions": [f"是的，我想聊{new_name}", f"不是，继续{prev_name}"],
            "context": "intent_switch",
            "previous_intent": previous_intent,
            "new_intent": new_intent
        }
