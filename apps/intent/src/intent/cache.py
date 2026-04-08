"""
意图缓存

基于 Redis 的意图识别结果缓存
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional, Dict, Any

from .models import Intent


class IntentCache:
    """
    意图缓存
    
    缓存意图识别结果，减少重复计算
    """
    
    def __init__(self, redis_client=None, default_ttl: int = 300):
        """
        初始化
        
        Args:
            redis_client: Redis 客户端（可选）
            default_ttl: 默认缓存时间（秒）
        """
        self.redis = redis_client
        self.default_ttl = default_ttl
        self._local_cache: Dict[str, Dict[str, Any]] = {}
    
    def _get_cache_key(self, text: str, session_context: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 包含上一轮意图和话题，避免上下文不同导致误命中
        last_intent = session_context.get("previous_intent", "")
        last_topic = session_context.get("previous_topic", "")
        raw = f"{text}:{last_intent}:{last_topic}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    async def get(self, text: str, session_context: Dict[str, Any]) -> Optional[Intent]:
        """获取缓存的意图"""
        key = self._get_cache_key(text, session_context)
        
        # 先查本地缓存
        if key in self._local_cache:
            return Intent.from_dict(self._local_cache[key])
        
        # 再查 Redis
        if self.redis:
            try:
                data = await self.redis.get(f"intent:{key}")
                if data:
                    return Intent.from_dict(json.loads(data))
            except Exception:
                pass
        
        return None
    
    async def set(
        self, 
        text: str, 
        session_context: Dict[str, Any], 
        intent: Intent,
        ttl: Optional[int] = None
    ) -> None:
        """设置缓存"""
        key = self._get_cache_key(text, session_context)
        data = intent.to_dict()
        
        # 本地缓存
        self._local_cache[key] = data
        
        # Redis 缓存
        if self.redis:
            try:
                await self.redis.setex(
                    f"intent:{key}",
                    ttl or self.default_ttl,
                    json.dumps(data)
                )
            except Exception:
                pass
    
    async def invalidate(self, user_id: str) -> None:
        """使某用户的缓存失效"""
        # 清除本地缓存
        self._local_cache.clear()
        
        # 清除 Redis 缓存（需要按 pattern 删除）
        if self.redis:
            try:
                keys = await self.redis.keys("intent:*")
                if keys:
                    await self.redis.delete(*keys)
            except Exception:
                pass
