"""
L2 向量记忆层 - 混合记忆检索

特性：
- 用户级记忆：个人历史意图
- 全局级记忆：热门意图模式
- 语义相似度检索
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import hashlib

from .models import Intent, IntentType


@dataclass
class MemoryRecord:
    """记忆记录"""
    text: str
    intent_type: str
    subtype: Optional[str]
    timestamp: str
    metadata: Dict[str, Any]


class HybridMemoryStore:
    """
    混合记忆存储
    
    结合用户级记忆和全局热门模式，解决冷启动问题
    """
    
    # 全局热门意图模式（预置）
    GLOBAL_HOT_PATTERNS = [
        ("帮我看看这个账号", "marketing", "diagnosis"),
        ("诊断一下账号", "marketing", "diagnosis"),
        ("写个文案", "marketing", "content_creation"),
        ("生成标题", "marketing", "content_creation"),
        ("选题建议", "marketing", "strategy"),
        ("怎么定位", "marketing", "strategy"),
        ("流量分析", "marketing", "traffic_analysis"),
        ("为什么没流量", "marketing", "traffic_analysis"),
        ("检查风险", "marketing", "risk_check"),
        ("你好", "casual", None),
        ("在吗", "casual", None),
        ("谢谢", "casual", None),
    ]
    
    def __init__(self, vector_store=None, global_threshold: float = 0.8):
        """
        初始化混合记忆存储
        
        Args:
            vector_store: 向量数据库实例（可选）
            global_threshold: 全局模式匹配阈值
        """
        self.vector_store = vector_store
        self.global_threshold = global_threshold
        self._init_global_patterns()
    
    def _init_global_patterns(self) -> None:
        """初始化全局模式"""
        self.global_patterns = [
            {
                "text": text,
                "intent_type": intent_type,
                "subtype": subtype,
                "confidence": 0.75
            }
            for text, intent_type, subtype in self.GLOBAL_HOT_PATTERNS
        ]
    
    async def similarity_search(
        self, 
        text: str, 
        user_id: str, 
        k: int = 3,
        user_threshold: float = 0.85
    ) -> Optional[Intent]:
        """
        混合相似度搜索
        
        策略：
        1. 先查用户级记忆
        2. 不足则补充全局匹配
        3. 聚合结果返回最可能的意图
        """
        # 1. 用户级检索
        user_results = await self._search_user_memory(text, user_id, k, user_threshold)
        
        if len(user_results) >= k:
            return self._aggregate_results(user_results)
        
        # 2. 补充全局匹配
        global_results = self._search_global_patterns(text)
        all_results = user_results + global_results
        
        if all_results:
            return self._aggregate_results(all_results[:k])
        
        return None
    
    async def _search_user_memory(
        self, 
        text: str, 
        user_id: str, 
        k: int,
        threshold: float
    ) -> List[Dict[str, Any]]:
        """搜索用户级记忆"""
        if not self.vector_store:
            return []
        
        try:
            results = await self.vector_store.similarity_search(
                query=text,
                user_id=user_id,
                k=k,
                threshold=threshold
            )
            return results
        except Exception:
            return []
    
    def _search_global_patterns(self, text: str) -> List[Dict[str, Any]]:
        """搜索全局热门模式（简单字符串匹配）"""
        matches = []
        for pattern in self.global_patterns:
            if pattern["text"] in text or text in pattern["text"]:
                matches.append(pattern)
        return matches
    
    def _aggregate_results(self, results: List[Dict[str, Any]]) -> Optional[Intent]:
        """聚合检索结果，返回最可能的意图"""
        if not results:
            return None
        
        # 统计意图类型
        type_counts = {}
        for r in results:
            intent_type = r.get("intent_type") or r.get("metadata", {}).get("intent")
            if intent_type:
                type_counts[intent_type] = type_counts.get(intent_type, 0) + 1
        
        # 找出最频繁的意图类型
        if not type_counts:
            return None
        
        dominant_type = max(type_counts.keys(), key=lambda x: type_counts[x])
        
        # 如果是营销意图，找出子类型
        subtype = None
        if dominant_type == "marketing":
            subtype_results = [
                r.get("subtype") or r.get("metadata", {}).get("subtype")
                for r in results
            ]
            subtype_counts = {}
            for s in subtype_results:
                if s:
                    subtype_counts[s] = subtype_counts.get(s, 0) + 1
            if subtype_counts:
                subtype = max(subtype_counts.keys(), key=lambda x: subtype_counts[x])
        
        # 计算置信度
        confidence = 0.82 if type_counts[dominant_type] >= 2 else 0.75
        
        return Intent(
            type=IntentType(dominant_type),
            subtype=subtype,
            confidence=confidence,
            reason="l2_memory_similarity",
            entities={"similar_count": len(results), "type_distribution": type_counts}
        )
    
    async def store(self, text: str, intent: Intent, user_id: str) -> None:
        """存储用户意图记录"""
        if not self.vector_store:
            return
        
        record = {
            "text": text,
            "intent_type": intent.type.value,
            "subtype": intent.subtype,
            "user_id": user_id,
            "metadata": {
                "confidence": intent.confidence,
                "reason": intent.reason,
            }
        }
        
        try:
            await self.vector_store.add(record)
        except Exception:
            pass
    
    async def get_prior_probability(self, user_id: str) -> float:
        """
        获取用户营销意图先验概率
        
        用于 L3 LLM 分类器的 prompt 构建
        """
        if not self.vector_store:
            return 0.3  # 默认先验
        
        try:
            history_count = await self.vector_store.get_user_history_count(user_id)
            if history_count < 5:
                return 0.3  # 冷启动用户
            
            marketing_ratio = await self.vector_store.get_marketing_ratio(user_id)
            return min(0.9, max(0.1, marketing_ratio))
        except Exception:
            return 0.3
