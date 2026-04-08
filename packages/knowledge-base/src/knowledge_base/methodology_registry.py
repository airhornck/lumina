from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from knowledge_base.models import Methodology, repo_root_from_here

logger = logging.getLogger(__name__)


class MethodologyRegistry:
    """方法论库管理器 — 自 data/methodologies/*.yml 加载。"""

    def __init__(self, data_dir: Path | None = None) -> None:
        root = data_dir or (repo_root_from_here(4) / "data" / "methodologies")
        self.data_dir = Path(data_dir) if data_dir else root
        self._cache: Dict[str, Methodology] = {}

    def _path_for(self, methodology_id: str) -> Path:
        safe = methodology_id.replace("/", "").replace("\\", "")
        return self.data_dir / f"{safe}.yml"

    def load(self, methodology_id: str) -> Methodology:
        if methodology_id not in self._cache:
            path = self._path_for(methodology_id)
            if not path.is_file():
                raise FileNotFoundError(f"Methodology YAML not found: {path}")
            config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            self._cache[methodology_id] = Methodology.from_config(config)
        return self._cache[methodology_id]

    def list_ids(self) -> List[str]:
        if not self.data_dir.is_dir():
            return []
        return sorted(
            p.stem for p in self.data_dir.glob("*.yml") if p.is_file()
        )

    def reload(self, methodology_id: Optional[str] = None) -> None:
        if methodology_id is None:
            self._cache.clear()
        else:
            self._cache.pop(methodology_id, None)

    def find_best_match(
        self,
        query: str,
        industry: str = "",
        goal: str = "",
    ) -> Optional[Methodology]:
        q = (query or "").lower()
        ind = (industry or "").lower()
        for mid in self.list_ids():
            try:
                m = self.load(mid)
            except Exception:
                logger.debug("skip methodology %s", mid, exc_info=True)
                continue
            hay = f"{m.name} {m.methodology_id} {' '.join(m.applicable_scenarios)}".lower()
            if ind and ind in hay:
                return m
            if q and any(tok in hay for tok in q.split() if len(tok) > 1):
                return m
            if goal and goal in hay:
                return m
        if self.list_ids():
            return self.load(self.list_ids()[0])
        return None
