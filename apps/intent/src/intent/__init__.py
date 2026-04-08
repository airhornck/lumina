"""
工业级 Intent 层 - Lumina AI营销平台

四级意图识别架构：
- L1: 规则引擎（零成本拦截）
- L2: 向量记忆（用户级+全局级）
- L2.5: 轻量分类器（BERT微调，可选）
- L3: LLM分类器（兜底保障）

特性：
- 置信度校准（Isotonic Regression）
- 动态阈值调整
- 意图切换检测
- 智能澄清引擎
"""

from .engine import IntentEngine, Intent, IntentType
from .l1_rules import L1RuleEngine
from .l2_memory import HybridMemoryStore
from .calibrator import ConfidenceCalibrator
from .switch_detector import IntentSwitchDetector
from .clarification import ClarificationEngine

__all__ = [
    "IntentEngine",
    "Intent",
    "IntentType",
    "L1RuleEngine",
    "HybridMemoryStore",
    "ConfidenceCalibrator",
    "IntentSwitchDetector",
    "ClarificationEngine",
]
