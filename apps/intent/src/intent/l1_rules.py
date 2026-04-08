"""
L1 规则引擎 - 零成本意图拦截

特性：
- 热加载 YAML 配置
- 正则表达式匹配
- 优先级：casual > marketing > ambiguous
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import Intent, IntentType, MarketingSubtype


class L1RuleEngine:
    """L1 规则引擎 - 硬规则匹配"""
    
    # 默认规则（当配置文件不存在时使用）
    DEFAULT_CASUAL_PATTERNS = [
        r"^你好$|^您好$|^哈喽$|^嗨$|^在吗$|^在么$|^有人吗$",
        r"^早上好$|^下午好$|^晚上好$|^早啊$|^晚安$",
        r"^谢谢$|^感谢$|^多谢$|^谢了$|^谢啦$|^不客气$|^拜拜$|^再见$",
        r"^好的$|^嗯嗯$|^嗯$|^好哒$|^ok$|^OK$|^👋$|^哈哈$|^哈哈哈$",
        r"^hi$|^hello$|^hey$\s*$",
        r"天气|气温|下雨|下雪|刮风|几点|星期几|周几|今天.*号",
        r"讲个笑话|讲个段子|讲故事|唱首歌|你是谁|你会什么",
        r"晚饭吃|午饭吃|早餐吃|外卖吃|睡不着|累死了",
    ]
    
    DEFAULT_MARKETING_PATTERNS = [
        r"(诊断|分析|看看|体检|评估).*(账号|号|主页|数据)",
        r"(写|生成|创作|改|优化).*(文案|标题|正文|内容|脚本|分镜)",
        r"(选题|方向|定位|人设|IP).*(建议|思路|怎么做|规划)",
        r"(流量|粉丝|曝光|阅读|转化|互动).*(提升|增加|优化|分析|问题|差|掉)",
        r"(小红书|抖音|B站|视频号|快手).*(运营|推广|怎么做|诊断)",
        r"(爆款|热门| trending).*(方法|技巧|思路|公式|密码)",
        r"(AIDA|定位理论|钩子|方法论|SOP|增长黑客|4P|4C|漏斗)",
        r"(风险|违规|审核|敏感词|违禁|限流).*(检查|检测|排查)",
        r"(竞品|对手|对标).*(分析|监测|看看)",
        r"(矩阵|多账号|批量).*(管理|运营|发布|规划)",
        r"(知识库|问答|什么是|怎么做|为什么).*(营销|运营|小红书|抖音)",
    ]
    
    DEFAULT_SUBTYPE_PATTERNS: Dict[str, List[str]] = {
        "diagnosis": [
            r"(诊断|体检|看看).*(账号|号|主页)",
            r"账号.*(问题|好不好|怎么样|评估)",
            r"帮.*看.*号",
        ],
        "content_creation": [
            r"(写|生成|创作).*(文案|标题|正文)",
            r"文案.*(怎么写|建议|优化)",
            r"(种草|推广).*(文案|内容)",
        ],
        "script_creation": [
            r"(脚本|分镜|口播|视频).*(创作|生成|写)",
            r"短视频.*(脚本|文案)",
        ],
        "strategy": [
            r"(选题|方向|定位|人设).*(建议|思路|怎么做)",
            r"(怎么|如何).*(定位|选题|起号)",
            r"账号.*(定位|方向)",
        ],
        "traffic_analysis": [
            r"(流量|曝光|播放).*(分析|差|掉|优化)",
            r"(互动率|CTR|转化).*(分析|优化)",
            r"为什么.*(没流量|没人看|不涨粉)",
        ],
        "risk_check": [
            r"(风险|违规|审核|敏感词).*(检查|检测|排查)",
            r"(内容|文案|脚本).*(违规|敏感|风险)",
            r"会不会.*(限流|违规|被封)",
        ],
        "matrix_setup": [
            r"(矩阵|多账号).*(规划|搭建|管理)",
            r"(主号|卫星号).*(策略|规划)",
            r"批量.*(账号|发布|管理)",
        ],
    }
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.casual_patterns: List[re.Pattern] = []
        self.marketing_patterns: List[re.Pattern] = []
        self.subtype_patterns: Dict[str, List[re.Pattern]] = {}
        self._load_rules()
    
    def _load_rules(self) -> None:
        """加载规则配置"""
        if self.config_path and Path(self.config_path).exists():
            self._load_from_yaml()
        else:
            self._load_defaults()
    
    def _load_defaults(self) -> None:
        """使用默认规则"""
        self.casual_patterns = [re.compile(p, re.IGNORECASE) for p in self.DEFAULT_CASUAL_PATTERNS]
        self.marketing_patterns = [re.compile(p, re.IGNORECASE) for p in self.DEFAULT_MARKETING_PATTERNS]
        self.subtype_patterns = {
            k: [re.compile(p, re.IGNORECASE) for p in v]
            for k, v in self.DEFAULT_SUBTYPE_PATTERNS.items()
        }
    
    def _load_from_yaml(self) -> None:
        """从 YAML 文件加载规则（支持热加载）"""
        import yaml
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        casual = config.get('casual', self.DEFAULT_CASUAL_PATTERNS)
        marketing = config.get('marketing', self.DEFAULT_MARKETING_PATTERNS)
        subtypes = config.get('subtypes', self.DEFAULT_SUBTYPE_PATTERNS)
        
        self.casual_patterns = [re.compile(p, re.IGNORECASE) for p in casual]
        self.marketing_patterns = [re.compile(p, re.IGNORECASE) for p in marketing]
        self.subtype_patterns = {
            k: [re.compile(p, re.IGNORECASE) for p in v]
            for k, v in subtypes.items()
        }
    
    def match(self, text: str) -> Optional[Intent]:
        """
        匹配意图
        
        优先级：
        1. Casual 规则（闲聊）
        2. Marketing 规则（营销意图）
        3. 未匹配 -> 返回 None（进入 L2）
        """
        if not text:
            return None
        
        text = text.strip()
        
        # 1. 检查 Casual 规则
        for pattern in self.casual_patterns:
            if pattern.search(text):
                return Intent(
                    type=IntentType.CASUAL,
                    confidence=1.0,
                    reason="l1_casual_rule",
                    entities={"matched_pattern": pattern.pattern}
                )
        
        # 2. 检查 Marketing 规则
        for pattern in self.marketing_patterns:
            if pattern.search(text):
                subtype = self._extract_subtype(text)
                return Intent(
                    type=IntentType.MARKETING,
                    subtype=subtype,
                    confidence=0.95,
                    reason="l1_marketing_rule",
                    entities={"matched_pattern": pattern.pattern}
                )
        
        # 未匹配，需要进入下一层
        return None
    
    def _extract_subtype(self, text: str) -> Optional[str]:
        """提取营销意图子类型"""
        for subtype, patterns in self.subtype_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    return subtype
        return None
    
    def reload(self) -> None:
        """热重载规则"""
        if self.config_path:
            self._load_rules()
