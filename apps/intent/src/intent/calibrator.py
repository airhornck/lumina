"""
置信度校准器

使用 Isotonic Regression 校准 LLM 输出的置信度
解决 LLM 过度自信问题
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import List, Optional

import numpy as np


class ConfidenceCalibrator:
    """
    置信度校准器
    
    使用保序回归（Isotonic Regression）将原始置信度映射为校准后的概率
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        初始化校准器
        
        Args:
            model_path: 模型文件路径，不存在则创建恒等映射
        """
        self.model_path = model_path
        self.calibrator = None
        self._load_or_create()
    
    def _load_or_create(self) -> None:
        """加载或创建校准器"""
        if self.model_path and Path(self.model_path).exists():
            self._load_model()
        else:
            self._create_identity_calibrator()
    
    def _load_model(self) -> None:
        """从文件加载模型"""
        try:
            with open(self.model_path, 'rb') as f:
                self.calibrator = pickle.load(f)
        except Exception:
            self._create_identity_calibrator()
    
    def _create_identity_calibrator(self) -> None:
        """创建恒等映射校准器（初始状态）"""
        try:
            from sklearn.isotonic import IsotonicRegression
            self.calibrator = IsotonicRegression(out_of_bounds='clip')
            # 用恒等数据拟合
            self.calibrator.fit(np.array([0.0, 0.5, 1.0]), np.array([0.0, 0.5, 1.0]))
        except ImportError:
            # sklearn 未安装时使用简单线性映射
            self.calibrator = None
    
    def calibrate(self, raw_confidence: float) -> float:
        """
        校准置信度
        
        Args:
            raw_confidence: 原始置信度（0-1）
        
        Returns:
            校准后的置信度（0-1）
        """
        if not (0 <= raw_confidence <= 1):
            raw_confidence = max(0, min(1, raw_confidence))
        
        if self.calibrator is None:
            # sklearn 不可用时直接返回
            return raw_confidence
        
        try:
            calibrated = self.calibrator.predict([[raw_confidence]])[0]
            return float(calibrated)
        except Exception:
            return raw_confidence
    
    def update(self, raw_confs: List[float], actual_accuracies: List[float]) -> None:
        """
        在线更新校准器
        
        根据实际反馈更新校准映射
        
        Args:
            raw_confs: 原始置信度列表
            actual_accuracies: 实际准确率列表（0或1）
        """
        if len(raw_confs) != len(actual_accuracies) or len(raw_confs) < 10:
            return
        
        try:
            from sklearn.isotonic import IsotonicRegression
            
            # 按置信度分组计算实际准确率
            bins = np.linspace(0, 1, 11)  # 10个区间
            bin_accuracies = []
            bin_centers = []
            
            for i in range(len(bins) - 1):
                mask = (np.array(raw_confs) >= bins[i]) & (np.array(raw_confs) < bins[i+1])
                if np.any(mask):
                    acc = np.mean(np.array(actual_accuracies)[mask])
                    bin_accuracies.append(acc)
                    bin_centers.append((bins[i] + bins[i+1]) / 2)
            
            if len(bin_centers) >= 2:
                self.calibrator = IsotonicRegression(out_of_bounds='clip')
                self.calibrator.fit(np.array(bin_centers), np.array(bin_accuracies))
                
                # 保存模型
                if self.model_path:
                    Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(self.model_path, 'wb') as f:
                        pickle.dump(self.calibrator, f)
        except ImportError:
            pass


class DynamicThreshold:
    """
    动态阈值管理器
    
    基于用户活跃度和会话上下文动态调整决策阈值
    """
    
    def __init__(self, base_threshold: float = 0.7):
        """
        初始化
        
        Args:
            base_threshold: 基础阈值（默认0.7）
        """
        self.base = base_threshold
    
    def get_threshold(
        self, 
        user_id: str, 
        session_context: Dict[str, Any]
    ) -> float:
        """
        获取动态阈值
        
        策略：
        1. 高活跃用户（历史对话>50）降低阈值
        2. 中等活跃用户（历史对话>20）略微降低
        3. 上一轮是营销意图且未切换话题，降低阈值
        """
        threshold = self.base
        
        # 基于历史对话数调整
        history_count = session_context.get("user_history_count", 0)
        if history_count > 50:
            threshold -= 0.1
        elif history_count > 20:
            threshold -= 0.05
        
        # 基于上一轮意图调整
        previous_intent = session_context.get("previous_intent")
        if previous_intent == "marketing":
            # 如果是连续营销对话，降低阈值
            threshold -= 0.05
        
        # 确保阈值在合理范围内
        return max(0.5, min(0.85, threshold))


# 类型提示导入
from typing import Any, Dict
