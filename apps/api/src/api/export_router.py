"""HTML 导出文件下载路由"""

from __future__ import annotations


from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from services.content_engine.storage import FileSystemStorage

router = APIRouter(prefix="/api/v1", tags=["exports"])

_storage: FileSystemStorage | None = None


def _get_storage() -> FileSystemStorage:
    global _storage
    if _storage is None:
        _storage = FileSystemStorage()
    return _storage


@router.get("/exports/{export_id}", response_class=HTMLResponse, summary="获取 HTML 导出文件")
async def get_export(export_id: str) -> HTMLResponse:
    """通过 export_id 获取 HTML 导出文件。

    export_id 格式支持两种：
    1. UUID 格式：从数据库查询文件路径
    2. 相对路径格式：直接拼接 static/content/ 路径
    """
    storage = _get_storage()

    # 尝试从 storage 直接解析 URL
    if export_id.startswith("static/content/"):
        url = f"/{export_id}"
    else:
        # 尝试拼接常见路径（简化实现）
        url = f"/static/content/{export_id}"

    html = storage.get(url)
    if html is None:
        raise HTTPException(status_code=404, detail="Export not found")

    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")
