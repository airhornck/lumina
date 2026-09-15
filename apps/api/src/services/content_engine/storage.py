from __future__ import annotations

from datetime import datetime
from pathlib import Path


class FileSystemStorage:
    """短期方案：本地文件系统存储，支持后续迁移到对象存储。"""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            # 从 storage.py (apps/api/src/services/content_engine/) 回溯到项目根目录
            # parents[5] = apps/api/src/services/content_engine/../../../../../../ = 项目根目录
            root = Path(__file__).resolve().parents[5]
            base_dir = root / "static" / "content"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, request_id: str, platform: str | None, html: str) -> str:
        date_dir = datetime.now().strftime("%Y-%m-%d")
        request_dir = self.base_dir / date_dir / request_id
        request_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{platform}.html" if platform else "master.html"
        file_path = request_dir / filename
        file_path.write_text(html, encoding="utf-8")

        return f"/static/content/{date_dir}/{request_id}/{filename}"

    def get(self, url: str) -> str | None:
        relative_path = url.replace("/static/content/", "")
        file_path = self.base_dir / relative_path
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return None

    def get_path(self, url: str) -> Path | None:
        relative_path = url.replace("/static/content/", "")
        file_path = self.base_dir / relative_path
        if file_path.exists():
            return file_path
        return None
