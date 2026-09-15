from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from infra.db import get_pool

logger = logging.getLogger(__name__)


class UserProfileService:
    """定位解析服务：获取/推断/保存用户账号定位。"""

    async def resolve_positioning(
        self,
        user_id: str,
        platform: str,
        context: Dict[str, Any],
        session_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """按优先级获取定位：P0 context → P1 数据库 → P2 标签推导 → P3 对话历史 → P4 Skill 兜底。

        所有来源最终都会经过 _normalize_positioning，确保 target_persona 等字段为字典，
        防止历史脏数据或 LLM 偶发返回字符串导致下游 .get() 报错。
        """

        # P0: 用户本次显式传入
        if context.get("positioning_statement"):
            return self._normalize_positioning({
                "source": "user_context",
                "positioning_statement": context["positioning_statement"],
                "target_persona": context.get("target_persona", {}),
                "content_pillars": context.get("content_pillars", []),
                "differentiation": context.get("differentiation", ""),
            })

        # P1: 数据库
        profile = await self._db_get(user_id, platform)
        if profile and profile.get("positioning_statement"):
            return self._normalize_positioning({**profile, "source": "database"})

        # P2: 从标签推导
        tags = await self._get_user_tags(user_id, platform, context)
        if tags and tags.get("style_tags"):
            positioning = self._normalize_positioning(await self._infer_from_tags(tags))
            await self._db_save(user_id, platform, positioning, inferred_from=["tags"])
            return {**positioning, "source": "inferred_from_tags"}

        # P3: 从对话历史提炼
        if session_history:
            positioning = self._normalize_positioning(await self._extract_from_history(session_history))
            if positioning:
                await self._db_save(user_id, platform, positioning, inferred_from=["dialogue"])
                return {**positioning, "source": "inferred_from_dialogue"}

        # P4: 兜底 - 调用定位分析 Skill
        positioning = self._normalize_positioning(await self._call_positioning_skill(platform, context))
        await self._db_save(user_id, platform, positioning, inferred_from=["skill"])
        return {**positioning, "source": "positioning_skill"}

    @staticmethod
    def _normalize_positioning(positioning: Any) -> Dict[str, Any]:
        """确保定位信息是字典，且 target_persona 为字典；LLM 偶发返回字符串时降级。"""
        if not isinstance(positioning, dict):
            positioning = {}
        persona = positioning.get("target_persona")
        if isinstance(persona, str):
            try:
                parsed = json.loads(persona)
                positioning["target_persona"] = parsed if isinstance(parsed, dict) else {}
            except Exception:
                positioning["target_persona"] = {}
        elif not isinstance(persona, dict):
            positioning["target_persona"] = {}
        return positioning

    async def _db_get(self, user_id: str, platform: str) -> Dict[str, Any] | None:
        pool = get_pool()
        if not pool:
            return None
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM account_profiles WHERE user_id = $1 AND platform = $2 ORDER BY updated_at DESC LIMIT 1",
                user_id,
                platform,
            )
            if row:
                return self._normalize_positioning(dict(row))
        return None

    async def _db_save(
        self,
        user_id: str,
        platform: str,
        positioning: Dict[str, Any],
        inferred_from: List[str],
    ) -> None:
        positioning = self._normalize_positioning(positioning)
        if not positioning:
            return
        pool = get_pool()
        if not pool:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO account_profiles (
                    user_id, platform, positioning_statement, target_persona,
                    content_pillars, differentiation, inferred_from
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id, platform) DO UPDATE SET
                    positioning_statement = EXCLUDED.positioning_statement,
                    target_persona = EXCLUDED.target_persona,
                    content_pillars = EXCLUDED.content_pillars,
                    differentiation = EXCLUDED.differentiation,
                    inferred_from = EXCLUDED.inferred_from,
                    updated_at = NOW()
                """,
                user_id,
                platform,
                positioning.get("positioning_statement", ""),
                json.dumps(positioning.get("target_persona", {})),
                positioning.get("content_pillars", []),
                positioning.get("differentiation", ""),
                inferred_from,
            )

    async def save_account_gene(
        self,
        user_id: str,
        platform: str,
        account_gene: Dict[str, Any],
    ) -> None:
        """将诊断结果 account_gene 保存到 account_profiles 表"""
        pool = get_pool()
        if not pool:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO account_profiles (
                    user_id, platform, content_types, style_tags, audience_sketch,
                    inferred_from, confidence
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id, platform) DO UPDATE SET
                    content_types = EXCLUDED.content_types,
                    style_tags = EXCLUDED.style_tags,
                    audience_sketch = EXCLUDED.audience_sketch,
                    inferred_from = EXCLUDED.inferred_from,
                    confidence = EXCLUDED.confidence,
                    updated_at = NOW()
                """,
                user_id,
                platform,
                account_gene.get("content_types", []),
                account_gene.get("style_tags", []),
                account_gene.get("audience_sketch", ""),
                ["diagnosis"],
                account_gene.get("confidence", 0.7),
            )

    async def _get_user_tags(
        self, user_id: str, platform: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """从上下文或诊断结果获取用户标签"""
        if context.get("content_dna"):
            dna = context["content_dna"]
            return {
                "content_types": [dna.get("tone", "general")],
                "style_tags": [dna.get("style", "general")],
                "audience_sketch": "",
            }
        return {}

    async def _infer_from_tags(self, tags: Dict[str, Any]) -> Dict[str, Any]:
        """用 LLM 从标签推导完整定位"""
        from llm_hub import get_client

        prompt = f"""基于以下账号标签，推导完整的账号定位信息。

【账号标签】
- 内容类型：{', '.join(tags.get('content_types', []))}
- 风格标签：{', '.join(tags.get('style_tags', []))}
- 受众素描：{tags.get('audience_sketch', '未知')}

请输出严格 JSON：
{{
  "positioning_statement": "...",
  "target_persona": {{"age": "...", "gender": "...", "pain_points": ["..."], "needs": ["..."]}},
  "content_pillars": ["...", "..."],
  "differentiation": "..."
}}
"""
        client = get_client(skill_name="user_profile")
        if not client:
            client = get_client()
        if not client or not client.config.api_key:
            return {
                "positioning_statement": "",
                "target_persona": {},
                "content_pillars": [],
                "differentiation": "",
            }

        try:
            response = await client.complete(
                prompt=prompt,
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=2048,
            )
            return json.loads(response)
        except Exception:
            return {
                "positioning_statement": "",
                "target_persona": {},
                "content_pillars": [],
                "differentiation": "",
            }

    async def _extract_from_history(
        self, session_history: List[Dict[str, Any]]
    ) -> Dict[str, Any] | None:
        """从对话历史提炼定位"""
        return None

    async def _call_positioning_skill(
        self, platform: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """调用定位分析 Skill 生成定位"""
        from llm_hub import get_client

        industry = context.get("industry", "general")
        prompt = f"""作为资深内容策略师，请为以下账号进行定位分析：

平台：{platform}
赛道：{industry}
目标受众：{context.get('target_audience', '未指定')}

请输出严格 JSON：
{{
  "positioning_statement": "...",
  "target_persona": {{"age": "...", "gender": "...", "pain_points": ["..."], "needs": ["..."]}},
  "content_pillars": ["...", "..."],
  "differentiation": "..."
}}
"""
        client = get_client(skill_name="content_strategist")
        if not client:
            client = get_client()
        if not client or not client.config.api_key:
            return {
                "positioning_statement": "",
                "target_persona": {},
                "content_pillars": [],
                "differentiation": "",
            }

        try:
            response = await client.complete(
                prompt=prompt,
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=2048,
            )
            return json.loads(response)
        except Exception:
            return {
                "positioning_statement": "",
                "target_persona": {},
                "content_pillars": [],
                "differentiation": "",
            }
