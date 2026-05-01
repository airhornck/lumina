"""LLM Token 用量记录与查询服务。"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from infra.db import get_pool

logger = logging.getLogger(__name__)


async def record_usage(
    user_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    skill_name: Optional[str] = None,
) -> None:
    """记录一次 LLM 调用的 token 用量。"""
    pool = get_pool()
    if not pool:
        logger.debug("DB pool not available, skipping usage record")
        return

    total_tokens = prompt_tokens + completion_tokens
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO llm_usage_logs
                    (user_id, model, skill_name, prompt_tokens, completion_tokens, total_tokens)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                user_id,
                model,
                skill_name,
                prompt_tokens,
                completion_tokens,
                total_tokens,
            )
    except Exception:
        logger.exception("Failed to record LLM usage for user %s", user_id)


async def get_summary(user_id: str) -> Dict[str, Any]:
    """获取用户累计 token 用量摘要。"""
    pool = get_pool()
    if not pool:
        return {
            "user_id": user_id,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "call_count": 0,
        }

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(prompt_tokens), 0) AS total_prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS total_completion_tokens,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COUNT(*) AS call_count
            FROM llm_usage_logs
            WHERE user_id = $1
            """,
            user_id,
        )

    return {
        "user_id": user_id,
        "total_prompt_tokens": row["total_prompt_tokens"],
        "total_completion_tokens": row["total_completion_tokens"],
        "total_tokens": row["total_tokens"],
        "call_count": row["call_count"],
    }


async def get_daily_stats(
    user_id: str,
    start_date: date,
    end_date: date,
) -> Dict[str, Any]:
    """按天汇总用户的 token 用量。"""
    pool = get_pool()
    if not pool:
        return {
            "user_id": user_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": [],
        }

    # 转换为带时区的 datetime 范围
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                DATE(created_at) AS day,
                SUM(prompt_tokens) AS prompt_tokens,
                SUM(completion_tokens) AS completion_tokens,
                SUM(total_tokens) AS total_tokens,
                COUNT(*) AS call_count
            FROM llm_usage_logs
            WHERE user_id = $1
              AND created_at >= $2
              AND created_at <= $3
            GROUP BY DATE(created_at)
            ORDER BY day ASC
            """,
            user_id,
            start_dt,
            end_dt,
        )

    daily: List[Dict[str, Any]] = [
        {
            "date": row["day"].isoformat(),
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "total_tokens": row["total_tokens"],
            "call_count": row["call_count"],
        }
        for row in rows
    ]

    return {
        "user_id": user_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": daily,
    }


async def get_unified_stats(
    user_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """统一查询接口：总是返回 summary；若提供日期范围，额外返回 daily。"""
    summary = await get_summary(user_id)
    result: Dict[str, Any] = {
        "user_id": user_id,
        "summary": {
            "total_prompt_tokens": summary["total_prompt_tokens"],
            "total_completion_tokens": summary["total_completion_tokens"],
            "total_tokens": summary["total_tokens"],
            "call_count": summary["call_count"],
        },
        "daily": None,
    }

    if start_date is not None and end_date is not None:
        daily_result = await get_daily_stats(user_id, start_date, end_date)
        result["daily"] = daily_result["daily"]
        result["start_date"] = daily_result["start_date"]
        result["end_date"] = daily_result["end_date"]

    return result
