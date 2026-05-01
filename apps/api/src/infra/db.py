"""轻量级 asyncpg 连接池管理。"""

from __future__ import annotations

import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> Optional[asyncpg.Pool]:
    """从环境变量 DATABASE_URL 初始化连接池。"""
    global _pool
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        # 开发环境未配置数据库时友好降级
        return None
    _pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=10,
        command_timeout=30,
    )
    return _pool


async def close_db_pool() -> None:
    """关闭连接池。"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> Optional[asyncpg.Pool]:
    """获取当前连接池（可能为 None）。"""
    return _pool
