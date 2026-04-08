"""
矩阵指挥官 Skill

负责：
- 矩阵整体策略规划
- 主号-卫星号定位设计
- 协同排期管理
- 流量互导策略
"""

from .main import mcp

__all__ = ["mcp"]
