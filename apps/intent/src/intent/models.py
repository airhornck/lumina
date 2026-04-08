"""Intent 数据模型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IntentType(Enum):
    """意图类型"""
    CASUAL = "casual"           # 闲聊
    MARKETING = "marketing"     # 营销意图
    AMBIGUOUS = "ambiguous"     # 模糊意图（需要澄清）
    SYSTEM = "system"           # 系统指令


class MarketingSubtype(Enum):
    """营销意图子类型"""
    DIAGNOSIS = "diagnosis"                 # 账号诊断
    CONTENT_CREATION = "content_creation"   # 内容创作
    SCRIPT_CREATION = "script_creation"     # 脚本创作
    STRATEGY = "strategy"                   # 选题/定位策略
    TRAFFIC_ANALYSIS = "traffic_analysis"   # 流量分析
    RISK_CHECK = "risk_check"               # 风险检查
    DATA_ANALYSIS = "data_analysis"         # 数据分析
    COMPETITOR = "competitor"               # 竞品分析
    TOPIC_SELECTION = "topic_selection"     # 选题建议
    MATRIX_SETUP = "matrix_setup"           # 矩阵规划
    BULK_CREATION = "bulk_creation"         # 批量创作
    KNOWLEDGE_QA = "knowledge_qa"           # 知识问答


@dataclass
class Intent:
    """意图识别结果"""
    type: IntentType
    subtype: Optional[str] = None
    confidence: float = 0.0
    entities: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""                    # 识别来源说明
    suggested_sop: Optional[str] = None # 建议的SOP流程
    requires_clarification: bool = False
    clarification_questions: List[str] = field(default_factory=list)
    clarification_options: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "subtype": self.subtype,
            "confidence": self.confidence,
            "entities": self.entities,
            "reason": self.reason,
            "suggested_sop": self.suggested_sop,
            "requires_clarification": self.requires_clarification,
            "clarification_questions": self.clarification_questions,
            "clarification_options": self.clarification_options,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Intent":
        return cls(
            type=IntentType(data.get("type", "ambiguous")),
            subtype=data.get("subtype"),
            confidence=data.get("confidence", 0.0),
            entities=data.get("entities", {}),
            reason=data.get("reason", ""),
            suggested_sop=data.get("suggested_sop"),
            requires_clarification=data.get("requires_clarification", False),
            clarification_questions=data.get("clarification_questions", []),
            clarification_options=data.get("clarification_options", []),
        )


@dataclass
class SessionContext:
    """会话上下文"""
    user_id: str
    session_id: str
    previous_intent: Optional[str] = None
    previous_topic: Optional[str] = None
    user_history_count: int = 0
    intent_switch_count: int = 0
    created_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "previous_intent": self.previous_intent,
            "previous_topic": self.previous_topic,
            "user_history_count": self.user_history_count,
            "intent_switch_count": self.intent_switch_count,
            "created_at": self.created_at,
        }
