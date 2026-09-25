"""Append-only event log + content hashing for Attempt 2 runs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


class EventLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def count(self) -> int:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return 0
        return sum(1 for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip())

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        seq = self.count() + 1
        record = {
            "sequence": seq,
            "timestamp": utc_now_iso(),
            **event,
        }
        record["event_hash"] = content_hash(
            {k: v for k, v in record.items() if k != "event_hash"}
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return record

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def file_hash(self) -> str:
        return sha256_file(self.path) if self.path.exists() else content_hash([])
