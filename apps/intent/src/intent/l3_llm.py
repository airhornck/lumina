"""
L3 LLM 分类器 - 兜底保障层

使用 LLM 进行意图分类，当 L1/L2 都未能识别时使用
"""

from __future__ import annotations

import json
from typing import Optional, Dict, Any

from .models import Intent, IntentType, SessionContext


class LLMClassifier:
    """LLM 意图分类器"""
    
    SYSTEM_PROMPT = """你是 Lumina AI营销助手的意图分类专家。

任务：分析用户输入，判断其意图类型和子类型。

意图类型：
- casual: 闲聊、问候、感谢、天气、时间等与营销无关的对话
- marketing: 与营销、内容创作、账号运营相关的意图
- ambiguous: 信息不足，需要澄清

营销意图子类型（仅当 type=marketing 时填写）：
- diagnosis: 账号诊断、分析
- content_creation: 文案、标题创作
- script_creation: 视频脚本、分镜创作
- strategy: 选题、定位、人设策略
- traffic_analysis: 流量、数据分析
- risk_check: 风险、违规检查
- matrix_setup: 矩阵规划、多账号管理
- bulk_creation: 批量创作
- knowledge_qa: 营销知识问答

输出格式（JSON）：
{
    "intent_type": "casual|marketing|ambiguous",
    "subtype": "可选的子类型",
    "confidence": 0.0-1.0,
    "entities": {"提取的关键信息": "值"},
    "reason": "分类理由"
}

规则：
1. 如果用户问天气、时间、笑话等，type=casual
2. 如果用户问账号、内容、流量、选题等，type=marketing
3. 如果不确定，type=ambiguous
4. confidence 基于你的确定性（0-1）
"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    async def classify(
        self, 
        text: str, 
        session_context: SessionContext,
        prior_probability: float = 0.3
    ) -> Intent:
        """
        使用 LLM 进行意图分类
        
        Args:
            text: 用户输入文本
            session_context: 会话上下文
            prior_probability: 营销意图先验概率
        """
        if not self.llm_client:
            # 无 LLM 时返回模糊意图
            return Intent(
                type=IntentType.AMBIGUOUS,
                confidence=0.0,
                reason="l3_no_llm_client"
            )
        
        # 构建带上下文的 prompt
        prompt = self._build_prompt(text, session_context, prior_probability)
        
        try:
            user_id = getattr(session_context, "user_id", None)
            response = await self.llm_client.complete(
                prompt,
                response_format={"type": "json_object"},
                temperature=0.1,
                _usage_meta={"user_id": user_id, "skill_name": "intent_l3"} if user_id else None,
            )
            
            # 解析 JSON 响应
            result = json.loads(response)
            
            return Intent(
                type=IntentType(result.get("intent_type", "ambiguous")),
                subtype=result.get("subtype"),
                confidence=result.get("confidence", 0.5),
                entities=result.get("entities", {}),
                reason=f"l3_llm_classifier: {result.get('reason', '')}"
            )
            
        except Exception as e:
            # 解析失败时返回模糊意图
            return Intent(
                type=IntentType.AMBIGUOUS,
                confidence=0.0,
                reason=f"l3_parse_error: {str(e)}"
            )
    
    def _build_prompt(
        self, 
        text: str, 
        session_context: SessionContext,
        prior_probability: float
    ) -> str:
        """构建分类 Prompt"""
        
        context_info = []
        
        # 添加上下文信息
        if session_context.previous_intent:
            context_info.append(f"上一轮意图: {session_context.previous_intent}")
        if session_context.previous_topic:
            context_info.append(f"上一轮话题: {session_context.previous_topic}")
        if session_context.user_history_count > 0:
            context_info.append(f"历史对话数: {session_context.user_history_count}")
        
        # 添加先验概率提示
        if prior_probability > 0.6:
            context_info.append(f"注意: 该用户历史营销意图占比 {prior_probability:.0%}，本轮很可能是营销意图")
        elif prior_probability < 0.3:
            context_info.append(f"注意: 该用户历史营销意图占比 {prior_probability:.0%}，本轮可能是闲聊")
        
        context_str = "\n".join(context_info) if context_info else "无历史上下文"
        
        return f"""{self.SYSTEM_PROMPT}

---

用户输入: {text}

会话上下文:
{context_str}

请输出 JSON 格式的分类结果:"""
