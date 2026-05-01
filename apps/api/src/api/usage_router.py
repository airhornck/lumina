"""Token 用量查询路由。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from services.usage_service import get_daily_stats, get_summary, get_unified_stats

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


@router.get("/stats")
async def usage_stats(
    user_id: str = Query(..., min_length=1, description="用户唯一标识"),
    start_date: Optional[date] = Query(default=None, description="查询起始日期（YYYY-MM-DD），与 end_date 同时提供时返回按天明细"),
    end_date: Optional[date] = Query(default=None, description="查询结束日期（YYYY-MM-DD），与 start_date 同时提供时返回按天明细"),
) -> Dict[str, Any]:
    """统一查询用户 token 用量。

    - 仅传 user_id：返回累计摘要（summary）
    - 同时传 start_date + end_date：返回 summary + 按天明细（daily）
    """
    if (start_date is not None) != (end_date is not None):
        raise HTTPException(status_code=400, detail="start_date 和 end_date 必须同时提供或同时省略")

    if start_date is not None and end_date is not None:
        if end_date < start_date:
            raise HTTPException(status_code=400, detail="end_date 不能早于 start_date")

        max_range = timedelta(days=90)
        if end_date - start_date > max_range:
            raise HTTPException(status_code=400, detail="查询时间范围不能超过 90 天")

    result = await get_unified_stats(user_id, start_date, end_date)
    return {"code": 0, "message": "success", "data": result}


@router.get("/summary")
async def usage_summary(
    user_id: str = Query(..., min_length=1, description="用户唯一标识"),
) -> Dict[str, Any]:
    """获取用户累计 token 用量摘要。（兼容接口，推荐使用 /stats）"""
    result = await get_summary(user_id)
    return {"code": 0, "message": "success", "data": result}


@router.get("/daily")
async def usage_daily(
    user_id: str = Query(..., min_length=1, description="用户唯一标识"),
    start_date: date = Query(..., description="查询起始日期（YYYY-MM-DD）"),
    end_date: date = Query(..., description="查询结束日期（YYYY-MM-DD）"),
) -> Dict[str, Any]:
    """按天汇总用户的 token 用量。（兼容接口，推荐使用 /stats）"""
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date 不能早于 start_date")

    # 限制查询范围为 90 天内
    max_range = timedelta(days=90)
    if end_date - start_date > max_range:
        raise HTTPException(status_code=400, detail="查询时间范围不能超过 90 天")

    result = await get_daily_stats(user_id, start_date, end_date)
    return {"code": 0, "message": "success", "data": result}
