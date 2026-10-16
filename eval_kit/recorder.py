"""数据记录：JSONL 全量落盘（附录B 字段 schema）。"""

import json
import os
import threading
from datetime import datetime, timezone


class JSONLRecorder:
    """线程安全的 JSONL 追加记录器。"""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def write(self, record: dict) -> None:
        row = dict(record)
        row.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        line = json.dumps(row, ensure_ascii=False)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")


def tcb_beijing() -> str:
    """北京时间 ISO 字符串（数据可读性用）。"""
    from datetime import timedelta

    return (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(timespec="seconds")
