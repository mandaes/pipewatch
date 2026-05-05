"""Deduplication filter to suppress repeated alert events within a cooldown window."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from pipewatch.alert_rules import AlertEvent


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DedupStore:
    """Tracks recently fired alerts to prevent duplicate notifications."""

    def __init__(self, path: str, cooldown_minutes: int = 60) -> None:
        self.path = Path(path)
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self._records: dict[str, datetime] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text())
            self._records = {
                k: datetime.fromisoformat(v) for k, v in raw.items()
            }
        except (json.JSONDecodeError, KeyError, ValueError):
            self._records = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v.isoformat() for k, v in self._records.items()}
        self.path.write_text(json.dumps(payload, indent=2))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _key(event: AlertEvent) -> str:
        return f"{event.rule_name}::{event.job_name}"

    def is_duplicate(self, event: AlertEvent) -> bool:
        """Return True if the event was already fired within the cooldown window."""
        key = self._key(event)
        last = self._records.get(key)
        if last is None:
            return False
        return (_utcnow() - last) < self.cooldown

    def record(self, event: AlertEvent) -> None:
        """Mark an event as fired right now."""
        self._records[self._key(event)] = _utcnow()
        self._save()

    def filter_new(self, events: List[AlertEvent]) -> List[AlertEvent]:
        """Return only events that are not duplicates, recording them."""
        new_events: List[AlertEvent] = []
        for event in events:
            if not self.is_duplicate(event):
                self.record(event)
                new_events.append(event)
        return new_events

    def purge_expired(self) -> int:
        """Remove records older than the cooldown window. Returns count removed."""
        now = _utcnow()
        expired = [k for k, v in self._records.items() if (now - v) >= self.cooldown]
        for k in expired:
            del self._records[k]
        if expired:
            self._save()
        return len(expired)
