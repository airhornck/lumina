"""资源上传器：将生成的 HTML 文件上传到 OSS，获取真实 URL。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

# OSS 上传接口配置（可从环境变量覆盖）
_DEFAULT_UPLOAD_URL = "http://182.92.84.206:8000/api/v1/resource/upload_html"


class ResourceUploader:
    """将本地 HTML 文件上传到远程资源服务，返回可公网访问的真实 URL。"""

    def __init__(self, upload_url: str | None = None) -> None:
        self.upload_url = upload_url or _DEFAULT_UPLOAD_URL

    async def upload_html(self, file_path: Path | str) -> str | None:
        """上传单个 HTML 文件，成功返回真实 URL，失败返回 None（保留本地路径兜底）。"""
        file_path = Path(file_path)
        if not file_path.is_file():
            logger.warning("Upload skipped: file not found %s", file_path)
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with file_path.open("rb") as f:
                    files = {"file": (file_path.name, f, "text/html")}
                    response = await client.post(
                        self.upload_url,
                        files=files,
                        headers={"accept": "application/json"},
                    )
                    response.raise_for_status()
                    data = response.json()
                    return self._extract_url(data)
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Upload failed (HTTP %s): %s → %s",
                e.response.status_code,
                file_path.name,
                e.response.text[:200],
            )
        except Exception:
            logger.exception("Upload failed unexpectedly: %s", file_path.name)
        return None

    async def upload_batch(
        self, url_map: Dict[str, str]
    ) -> Dict[str, str]:
        """批量上传 HTML 文件。

        Args:
            url_map: {platform_id: local_url}，如 {"master": "/static/content/.../master.html"}

        Returns:
            {platform_id: real_url_or_local_url}，上传失败时保留原本地 URL。
        """
        result: Dict[str, str] = {}
        for platform, local_url in url_map.items():
            real_url = await self._try_upload(local_url)
            result[platform] = real_url or local_url
        return result

    async def _try_upload(self, local_url: str) -> str | None:
        """根据本地 URL 找到文件并上传。"""
        # local_url 格式: /static/content/2026-05-23/xxx/platform.html
        if not local_url.startswith("/static/content/"):
            return None
        # 从 storage.py 可知 base_dir 对应 static/content
        root = Path(__file__).resolve().parents[5] / "static" / "content"
        relative = local_url.replace("/static/content/", "")
        file_path = root / relative
        return await self.upload_html(file_path)

    @staticmethod
    def _extract_url(data: Any) -> str | None:
        """从接口返回 JSON 中提取 URL，兼容多种常见格式。"""
        if isinstance(data, dict):
            # 直接字段
            for key in ("url", "file_url", "oss_url", "download_url", "link"):
                url = data.get(key)
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    return url
            # 嵌套 data / result / data.url
            for wrapper in ("data", "result", "payload", "body"):
                inner = data.get(wrapper)
                if isinstance(inner, dict):
                    for key in ("url", "file_url", "oss_url", "download_url", "link"):
                        url = inner.get(key)
                        if isinstance(url, str) and url.startswith(("http://", "https://")):
                            return url
        return None
