from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from knowledge_base.models import PlatformSpec, repo_root_from_here

logger = logging.getLogger(__name__)


class PlatformRegistry:
    """平台规范库 — data/platforms/*.yml。"""

    def __init__(self, data_dir: Path | None = None) -> None:
        root = data_dir or (repo_root_from_here(4) / "data" / "platforms")
        self.data_dir = Path(data_dir) if data_dir else root
        self._cache: Dict[str, PlatformSpec] = {}

    def _resolve_path(self, platform_id: str) -> Optional[Path]:
        if not self.data_dir.is_dir():
            return None
        safe = platform_id.replace("/", "").replace("\\", "")
        for p in sorted(self.data_dir.glob("*.yml")):
            if p.stem.startswith(safe) or safe in p.stem:
                return p
        direct = self.data_dir / f"{safe}.yml"
        if direct.is_file():
            return direct
        return None

    def load(self, platform_id: str) -> PlatformSpec:
        if platform_id not in self._cache:
            path = self._resolve_path(platform_id)
            if not path or not path.is_file():
                logger.warning("No platform spec for %s, using empty defaults", platform_id)
                self._cache[platform_id] = PlatformSpec(platform_id=platform_id, raw={})
                return self._cache[platform_id]
            config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            self._cache[platform_id] = PlatformSpec.from_config(config)
        return self._cache[platform_id]

    def reload(self, platform_id: Optional[str] = None) -> None:
        if platform_id is None:
            self._cache.clear()
        else:
            self._cache.pop(platform_id, None)
