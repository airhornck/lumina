"""双库体系：方法论库 + 平台规范库（YAML，可热加载）。"""

from knowledge_base.methodology_registry import MethodologyRegistry
from knowledge_base.platform_registry import PlatformRegistry

__all__ = ["MethodologyRegistry", "PlatformRegistry"]
