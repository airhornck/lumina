"""内容导出元数据服务：将导出记录持久化到数据库"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from infra.db import get_pool

logger = logging.getLogger(__name__)


class ExportRecordService:
    """将 content_exports 元数据写入数据库"""

    async def save_exports(
        self,
        user_id: str,
        conversation_id: str,
        request_id: str,
        export_urls: List[Dict[str, str]],
        platform_versions: List[Dict[str, Any]],
        master_content: Dict[str, Any],
    ) -> None:
        """批量保存导出元数据到 content_exports 表"""
        pool = get_pool()
        if not pool:
            logger.warning("Database pool not available, skipping export metadata persistence")
            return

        try:
            async with pool.acquire() as conn:
                for url_info in export_urls:
                    platform = url_info.get("platform", "")
                    variant = url_info.get("variant", "")
                    file_path = url_info.get("url", "")

                    # 查找对应的文章标题
                    title = ""
                    if platform == "master":
                        title = master_content.get("title", "")
                    else:
                        for v in platform_versions:
                            if v.get("platform") == platform:
                                title = v.get("title", "")
                                break

                    # 计算文件大小（粗略估算）
                    file_size = len(file_path.encode("utf-8"))

                    await conn.execute(
                        """INSERT INTO content_exports (
                            user_id, conversation_id, request_id,
                            export_type, article_title, file_path, file_size, raw_payload
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                        """,
                        user_id,
                        conversation_id,
                        request_id,
                        platform,
                        title,
                        file_path,
                        file_size,
                        json.dumps({"variant": variant, "platform": platform}, ensure_ascii=False),
                    )

                logger.info(
                    "Saved %d export records for request_id=%s",
                    len(export_urls),
                    request_id,
                )
        except Exception:
            logger.exception("Failed to save export metadata")
