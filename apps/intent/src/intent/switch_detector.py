"""
意图切换检测器

检测用户是否突然改变了话题
用于决定是否需要重新澄清
"""

from __future__ import annotations

from typing import Dict, Any, Optional

from .models import Intent, IntentType


class IntentSwitchDetector:
    """
    意图切换检测器
    
    检测用户是否在同一会话中突然改变话题
    避免 Agent 在错误的上下文中执行
    """
    
    def __init__(self, switch_penalty_threshold: int = 2):
        """
        初始化
        
        Args:
            switch_penalty_threshold: 触发澄清的切换次数阈值
        """
        self.switch_penalty_threshold = switch_penalty_threshold
    
    def detect(
        self, 
        new_intent: Intent, 
        session_context: Dict[str, Any]
    ) -> bool:
        """
        检测是否发生意图切换
        
        Args:
            new_intent: 新识别的意图
            session_context: 会话上下文
        
        Returns:
            True 表示检测到可能的话题切换，需要澄清
        """
        last_intent = session_context.get("previous_intent")
        
        if not last_intent:
            # 第一轮对话，无上一轮意图
            return False
        
        current_type = new_intent.type.value
        
        # 判断意图类型是否发生变化
        if current_type != last_intent:
            # 类型不同，记录切换计数
            switch_count = session_context.get("intent_switch_count", 0) + 1
            session_context["intent_switch_count"] = switch_count
            
            # 达到阈值，需要澄清
            if switch_count >= self.switch_penalty_threshold:
                return True
        else:
            # 同类型意图，重置切换计数
            session_context["intent_switch_count"] = 0
        
        return False
    
    def should_clarify_switch(
        self,
        previous_intent: Optional[str],
        previous_subtype: Optional[str],
        new_intent: Intent
    ) -> bool:
        """
        判断是否需要澄清意图切换
        
        场景示例：
        - 用户之前问"诊断账号"，现在说"讲个笑话" -> 需要澄清
        - 用户之前问"诊断账号"，现在说"帮我写文案" -> 不需要澄清（都是营销）
        """
        if not previous_intent:
            return False
        
        current_type = new_intent.type.value
        
        # 从营销意图切换到闲聊，可能需要澄清
        if previous_intent == "marketing" and current_type == "casual":
            return True
        
        # 从闲聊切换到营销意图，通常不需要澄清
        if previous_intent == "casual" and current_type == "marketing":
            return False
        
        # 营销意图内部的子类型切换
        if previous_intent == "marketing" and current_type == "marketing":
            # 如果子类型完全不同，可能需要澄清
            if previous_subtype and new_intent.subtype:
                # 定义相关子类型组
                content_group = {"content_creation", "script_creation"}
                analysis_group = {"diagnosis", "traffic_analysis", "data_analysis"}
                
                prev_in_content = previous_subtype in content_group
                new_in_content = new_intent.subtype in content_group
                prev_in_analysis = previous_subtype in analysis_group
                new_in_analysis = new_intent.subtype in analysis_group
                
                # 同组内切换不需要澄清
                if (prev_in_content and new_in_content) or (prev_in_analysis and new_in_analysis):
                    return False
                
                # 跨组切换可能需要澄清
                return True
        
        return False
