"""对话日志（JSONL）：每轮一条结构化记录，供服务器排查意图识别/工具调用问题。

每轮记录字段：
- ts / request_id / user_id / conversation_id
- user_message：用户原话
- path：planner（LLM 规划）/ keyword（关键词直连）/ mock（测试）
- tools：[{name, args, ok, elapsed_ms}]——意图识别的核心证据：调了哪个工具、参数是否抽对
- thinking_preview：模型思考前 500 字（意图判断过程）
- reply / reply_len、usage（token）、reply_ms
- export_urls / compliance_risk：业务事件摘要
- error：失败时的错误信息

文件：data/logs/chat/chat-YYYY-MM-DD.jsonl（LUMINA_CHAT_LOG_DIR 可覆盖）。
注意：含用户对话内容，仅限私有部署；勿提交 git（data/logs/ 已加 .gitignore）。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_MAX_RECORD_FIELD = 4000


def _log_dir() -> Path:
    d = os.environ.get("LUMINA_CHAT_LOG_DIR", "").strip()
    if d:
        return Path(d)
    return Path(__file__).resolve().parents[4] / "data" / "logs" / "chat"


def _log_path(day: str) -> Path:
    return _log_dir() / f"chat-{day}.jsonl"


def log_turn(record: Dict[str, Any]) -> None:
    """追加一轮对话记录（best-effort，绝不影响主链路）。"""
    try:
        ts = record.get("ts") or datetime.now().astimezone().isoformat(timespec="seconds")
        record["ts"] = ts
        day = ts[:10]
        path = _log_path(day)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with _LOCK:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as e:
        logger.warning("conversation log write failed: %s", e)


def query_logs(
    date: Optional[str] = None,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """按日期/用户/会话过滤查询（返回按时间正序的最近 limit 条）。"""
    day = date or datetime.now().astimezone().date().isoformat()
    path = _log_path(day)
    if not path.is_file():
        return []
    matched: List[Dict[str, Any]] = []
    try:
        with _LOCK:
            lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if user_id and rec.get("user_id") != user_id:
                continue
            if conversation_id and rec.get("conversation_id") != conversation_id:
                continue
            matched.append(rec)
    except Exception as e:
        logger.warning("conversation log read failed: %s", e)
        return []
    return matched[-limit:]
