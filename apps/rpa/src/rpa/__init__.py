"""
RPA 基础能力模块 - Lumina AI营销平台

提供无头浏览器自动化能力，支持：
- 多账号并发管理
- 浏览器指纹伪装
- Cookie/Session 隔离
- 自动化任务执行
"""

from .browser_grid import BrowserGrid, BrowserSession
from .anti_detection import AntiDetectionLayer, FingerprintGenerator
from .session_manager import SessionManager
from .proxy_manager import ProxyManager
from .executor import RPAExecutor, RPATask, TaskResult

__all__ = [
    "BrowserGrid",
    "BrowserSession",
    "AntiDetectionLayer",
    "FingerprintGenerator",
    "SessionManager",
    "ProxyManager",
    "RPAExecutor",
    "RPATask",
    "TaskResult",
]
