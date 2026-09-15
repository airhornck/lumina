"""Redfox 数据 API 客户端。"""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class RedfoxClient:
    """红狐数据 API 客户端。"""

    def __init__(self) -> None:
        self.api_key = os.environ.get("REDFOX_API_KEY", "")
        self.base_url = os.environ.get("REDFOX_API_BASE_URL", "https://api.redfox.example.com/v1")
        self.timeout = float(os.environ.get("REDFOX_TIMEOUT_SECONDS", "15"))

    def is_configured(self) -> bool:
        return bool(self.api_key) and bool(self.base_url)

    async def fetch_trending(
        self,
        keyword: str,
        platform: str = "multi",
        time_window: str = "7d",
        limit: int = 10,
    ) -> dict[str, Any]:
        """调用 Redfox API 获取爆款数据。"""
        if not self.is_configured():
            return {"ok": False, "error": "Redfox not configured", "items": []}

        url = f"{self.base_url}/trending/search"
        params = {
            "keyword": keyword,
            "platform": platform,
            "time_window": time_window,
            "limit": limit,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.warning("Redfox API error: status=%s body=%s", response.status, text[:200])
                        return {"ok": False, "error": f"status {response.status}", "items": []}
                    data = await response.json()
                    items = data.get("items", [])
                    return {
                        "ok": True,
                        "data_source": "redfox",
                        "items": items,
                        "expanded_keywords": data.get("expanded_keywords", [keyword]),
                        "hot_keywords": data.get("hot_keywords", []),
                    }
        except Exception as e:
            logger.warning("Redfox API failed: %s", e)
            return {"ok": False, "error": str(e), "items": []}
