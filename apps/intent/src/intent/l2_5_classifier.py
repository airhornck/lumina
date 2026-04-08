"""
L2.5 轻量分类器（可选）

基于 BERT 的微缩分类器，用于降本增效
当可用时使用，否则跳过
"""

from __future__ import annotations

from typing import Tuple


class LightweightClassifier:
    """
    轻量级 BERT 分类器
    
    用于在 L2 和 L3 之间提供快速、低成本的分类
    需要额外安装 transformers 和 torch
    """
    
    def __init__(self, model_name: str = "bert-base-chinese"):
        """
        初始化分类器
        
        Args:
            model_name: 模型名称或路径
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.labels = ["casual", "marketing", "ambiguous"]
        self._initialized = False
        
        self._init_model()
    
    def _init_model(self) -> None:
        """延迟初始化模型"""
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name,
                num_labels=len(self.labels)
            )
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model.to(self.device)
            self._initialized = True
        except ImportError:
            # transformers 或 torch 未安装
            self._initialized = False
        except Exception:
            # 其他加载错误
            self._initialized = False
    
    async def predict(self, text: str) -> Tuple[str, float]:
        """
        预测意图类型
        
        Args:
            text: 输入文本
        
        Returns:
            (标签, 置信度)
        """
        if not self._initialized:
            # 未初始化时返回 ambiguous，让 L3 处理
            return "ambiguous", 0.0
        
        try:
            import torch
            import asyncio
            
            loop = asyncio.get_event_loop()
            label, conf = await loop.run_in_executor(None, self._predict_sync, text)
            return label, conf
        except Exception:
            return "ambiguous", 0.0
    
    def _predict_sync(self, text: str) -> Tuple[str, float]:
        """同步预测（在线程池中运行）"""
        import torch
        
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=128,
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
        
        probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
        idx = int(probs.argmax())
        
        return self.labels[idx], float(probs[idx])
