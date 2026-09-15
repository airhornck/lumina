"""会话级用户画像服务：按 (user_id, conversation_id) 持久化平台、赛道、受众等画像信息。

改造计划阶段二 P0-7/P0-9/P0-12：
- P0-7: conversation_profiles 表设计
- P0-9: 画像更新策略（用户声明、工具调用后更新）
- P0-12: 平台变更检测与处理

画像字段与 renovation_plan.md §4.2.3 一致：
{
  "platform": "shipinhao",
  "platform_cn": "视频号",
  "niche": "健康养生",
  "target_audience": "35-65岁中老年",
  "content_style": "干货型/跟练型",
  "goals": ["涨粉", "打造IP"],
}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from infra.db import get_pool

logger = logging.getLogger(__name__)

# 平台中文名映射（用于 platform_cn 字段）
PLATFORM_CN_MAP: Dict[str, str] = {
    "shipinhao": "视频号",
    "xiaohongshu": "小红书",
    "douyin": "抖音",
    "bilibili": "B站",
    "kuaishou": "快手",
    "weibo": "微博",
    "zhihu": "知乎",
    "wechat_official": "微信公众号",
}

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS conversation_profiles (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    conversation_id VARCHAR(128) NOT NULL,
    platform VARCHAR(64),
    platform_cn VARCHAR(64),
    niche VARCHAR(256),
    target_audience VARCHAR(512),
    content_style VARCHAR(512),
    goals JSONB DEFAULT '[]'::jsonb,
    niche_extracted_at TIMESTAMPTZ,
    platform_changed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_conv_profile UNIQUE (user_id, conversation_id)
);

CREATE INDEX IF NOT EXISTS idx_conv_profile_user
    ON conversation_profiles (user_id, conversation_id);
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_profile_table() -> bool:
    """确保 conversation_profiles 表存在。"""
    pool = get_pool()
    if not pool:
        return False
    try:
        async with pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)
        return True
    except Exception as e:
        logger.warning("Failed to ensure conversation_profiles table: %s", e)
        return False


class ConversationProfile:
    """会话级用户画像值对象。"""

    def __init__(
        self,
        user_id: str,
        conversation_id: str,
        platform: Optional[str] = None,
        platform_cn: Optional[str] = None,
        niche: Optional[str] = None,
        target_audience: Optional[str] = None,
        content_style: Optional[str] = None,
        goals: Optional[List[str]] = None,
    ) -> None:
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.platform = platform
        self.platform_cn = platform_cn
        self.niche = niche
        self.target_audience = target_audience
        self.content_style = content_style
        self.goals = goals or []

    @classmethod
    def from_row(cls, row: Any) -> "ConversationProfile":
        return cls(
            user_id=row["user_id"],
            conversation_id=row["conversation_id"],
            platform=row.get("platform"),
            platform_cn=row.get("platform_cn"),
            niche=row.get("niche"),
            target_audience=row.get("target_audience"),
            content_style=row.get("content_style"),
            goals=row.get("goals") or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.platform:
            d["platform"] = self.platform
            d["platform_cn"] = self.platform_cn or PLATFORM_CN_MAP.get(self.platform, "")
        if self.niche:
            d["niche"] = self.niche
        if self.target_audience:
            d["target_audience"] = self.target_audience
        if self.content_style:
            d["content_style"] = self.content_style
        if self.goals:
            d["goals"] = self.goals
        return d

    def format_for_prompt(self) -> str:
        """格式化为 system prompt 中可读的画像摘要。"""
        parts = []
        if self.platform:
            cn = self.platform_cn or PLATFORM_CN_MAP.get(self.platform, self.platform)
            parts.append(f"平台={cn}")
        if self.niche:
            parts.append(f"赛道={self.niche}")
        if self.target_audience:
            parts.append(f"目标人群={self.target_audience}")
        if self.content_style:
            parts.append(f"内容风格={self.content_style}")
        if self.goals:
            parts.append(f"目标={','.join(self.goals)}")
        if parts:
            return "当前用户画像：" + "，".join(parts)
        return ""


class ConversationProfileService:
    """会话级用户画像读写服务。"""

    async def get_profile(
        self, user_id: str, conversation_id: str
    ) -> Optional[ConversationProfile]:
        """获取指定会话的用户画像。"""
        if not await ensure_profile_table():
            return None
        pool = get_pool()
        if not pool:
            return None
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT * FROM conversation_profiles
                       WHERE user_id = $1 AND conversation_id = $2""",
                    user_id,
                    conversation_id,
                )
                if row:
                    return ConversationProfile.from_row(row)
                return None
        except Exception as e:
            logger.warning("Failed to get conversation profile: %s", e)
            return None

    async def upsert_profile(
        self,
        user_id: str,
        conversation_id: str,
        *,
        platform: Optional[str] = None,
        niche: Optional[str] = None,
        target_audience: Optional[str] = None,
        content_style: Optional[str] = None,
        goals: Optional[List[str]] = None,
    ) -> bool:
        """更新（创建或覆盖）会话级画像字段。None 字段保留原值。"""
        if not await ensure_profile_table():
            return False
        pool = get_pool()
        if not pool:
            return False

        now = _utc_now()
        try:
            async with pool.acquire() as conn:
                # 先读取已有画像
                existing = await conn.fetchrow(
                    """SELECT * FROM conversation_profiles
                       WHERE user_id = $1 AND conversation_id = $2""",
                    user_id,
                    conversation_id,
                )

                # 合并：新值优先，旧值保留
                cur_platform = platform if platform is not None else (
                    existing["platform"] if existing else None
                )
                cur_niche = niche if niche is not None else (
                    existing["niche"] if existing else None
                )
                cur_audience = target_audience if target_audience is not None else (
                    existing["target_audience"] if existing else None
                )
                cur_style = content_style if content_style is not None else (
                    existing["content_style"] if existing else None
                )

                # goals 合并（新 goals 追加，不覆盖）
                existing_goals: List[str] = json.loads(existing["goals"]) if existing and existing.get("goals") else []
                if goals:
                    merged_goals = list(dict.fromkeys(existing_goals + goals))  # 去重保留顺序
                else:
                    merged_goals = existing_goals

                platform_cn = PLATFORM_CN_MAP.get(cur_platform, "") if cur_platform else None

                # 检测平台变更
                platform_changed = False
                if existing and existing.get("platform") and cur_platform:
                    if existing["platform"] != cur_platform:
                        platform_changed = True

                await conn.execute(
                    """INSERT INTO conversation_profiles
                       (user_id, conversation_id, platform, platform_cn, niche,
                        target_audience, content_style, goals, updated_at,
                        platform_changed_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)
                       ON CONFLICT (user_id, conversation_id) DO UPDATE SET
                           platform = COALESCE(NULLIF(EXCLUDED.platform, ''), conversation_profiles.platform),
                           platform_cn = COALESCE(NULLIF(EXCLUDED.platform_cn, ''), conversation_profiles.platform_cn),
                           niche = COALESCE(NULLIF(EXCLUDED.niche, ''), conversation_profiles.niche),
                           target_audience = COALESCE(NULLIF(EXCLUDED.target_audience, ''), conversation_profiles.target_audience),
                           content_style = COALESCE(NULLIF(EXCLUDED.content_style, ''), conversation_profiles.content_style),
                           goals = conversation_profiles.goals || EXCLUDED.goals,
                           updated_at = EXCLUDED.updated_at,
                           platform_changed_at = CASE
                               WHEN EXCLUDED.platform_changed_at IS NOT NULL
                               THEN EXCLUDED.platform_changed_at
                               ELSE conversation_profiles.platform_changed_at
                           END
                    """,
                    user_id,
                    conversation_id,
                    cur_platform,
                    platform_cn,
                    cur_niche,
                    cur_audience,
                    cur_style,
                    json.dumps(merged_goals, ensure_ascii=False),
                    now,
                    now if platform_changed else None,
                )
                return True
        except Exception as e:
            logger.warning("Failed to upsert conversation profile: %s", e)
            return False

    async def detect_platform_change(
        self, user_id: str, conversation_id: str, new_platform: Optional[str]
    ) -> Optional[str]:
        """检测平台是否发生变更。返回旧平台标识，无变更返回 None。"""
        if not new_platform:
            return None
        profile = await self.get_profile(user_id, conversation_id)
        if profile and profile.platform and profile.platform != new_platform:
            return profile.platform
        return None

    async def update_profile_from_tool_args(
        self,
        user_id: str,
        conversation_id: str,
        tool_name: str,
        args: Dict[str, Any],
    ) -> None:
        """根据工具调用参数更新画像（best-effort）。"""
        updates: Dict[str, Any] = {}
        platform = args.get("platform")
        if platform:
            updates["platform"] = platform

        niche = args.get("niche")
        if niche:
            updates["niche"] = niche

        target_audience = args.get("target_audience") or args.get("brief")
        if target_audience:
            updates["target_audience"] = target_audience

        if updates:
            await self.upsert_profile(user_id, conversation_id, **updates)

    async def extract_and_update_from_message(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
    )-> Optional[str]:
        """从用户消息中提取平台并更新画像。返回提取到的平台（如有）。"""
        from services.platform_utils import extract_platform_from_text

        platform = extract_platform_from_text(message)
        if platform:
            await self.upsert_profile(
                user_id, conversation_id, platform=platform
            )
            return platform
        return None


# 单例
_profile_service: Optional[ConversationProfileService] = None


def get_profile_service() -> ConversationProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = ConversationProfileService()
    return _profile_service
