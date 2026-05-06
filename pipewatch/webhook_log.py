"""Persistent log of webhook delivery attempts for audit and retry tracking."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class WebhookLogEntry:
    url: str
    job_name: str
    rule_name: str
    success: bool
    attempted_at: datetime = field(default_factory=_utcnow)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "job_name": self.job_name,
            "rule_name": self.rule_name,
            "success": self.success,
            "attempted_at": self.attempted_at.isoformat(),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WebhookLogEntry":
        return cls(
            url=d["url"],
            job_name=d["job_name"],
            rule_name=d["rule_name"],
            success=d["success"],
            attempted_at=datetime.fromisoformat(d["attempted_at"]),
            error=d.get("error"),
        )


class WebhookLog:
    def __init__(self, path: str) -> None:
        self.path = path
        self._entries: List[WebhookLogEntry] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        self._entries = [WebhookLogEntry.from_dict(r) for r in raw]

    def _save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump([e.to_dict() for e in self._entries], fh, indent=2)

    def record(self, entry: WebhookLogEntry) -> None:
        self._entries.append(entry)
        self._save()

    def entries(self) -> List[WebhookLogEntry]:
        return list(self._entries)

    def failed_entries(self) -> List[WebhookLogEntry]:
        return [e for e in self._entries if not e.success]

    def clear(self) -> None:
        self._entries = []
        self._save()
