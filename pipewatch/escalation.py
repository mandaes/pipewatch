"""Escalation policy: track repeated alert events and escalate after a threshold."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pipewatch.alert_rules import AlertEvent


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class EscalationPolicy:
    """Defines when an alert should be escalated based on repeat count."""
    threshold: int = 3  # number of consecutive fires before escalation
    cooldown_minutes: int = 60  # minutes before resetting the counter

    def to_dict(self) -> dict:
        return {
            "threshold": self.threshold,
            "cooldown_minutes": self.cooldown_minutes,
        }


@dataclass
class EscalationState:
    """Tracks consecutive alert fires for a single (job, rule) pair."""
    job_name: str
    rule_name: str
    count: int = 0
    last_fired: Optional[datetime] = None
    escalated: bool = False

    def to_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "rule_name": self.rule_name,
            "count": self.count,
            "last_fired": self.last_fired.isoformat() if self.last_fired else None,
            "escalated": self.escalated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EscalationState":
        last_fired = None
        if data.get("last_fired"):
            last_fired = datetime.fromisoformat(data["last_fired"])
        return cls(
            job_name=data["job_name"],
            rule_name=data["rule_name"],
            count=data.get("count", 0),
            last_fired=last_fired,
            escalated=data.get("escalated", False),
        )


class EscalationTracker:
    """Persists escalation state and decides whether an event should escalate."""

    def __init__(self, store_path: str, policy: Optional[EscalationPolicy] = None) -> None:
        self.store_path = store_path
        self.policy = policy or EscalationPolicy()
        self._states: Dict[str, EscalationState] = {}
        self._load()

    def _key(self, job_name: str, rule_name: str) -> str:
        return f"{job_name}::{rule_name}"

    def _load(self) -> None:
        if not os.path.exists(self.store_path):
            return
        with open(self.store_path, "r") as fh:
            raw = json.load(fh)
        for item in raw:
            state = EscalationState.from_dict(item)
            self._states[self._key(state.job_name, state.rule_name)] = state

    def _save(self) -> None:
        with open(self.store_path, "w") as fh:
            json.dump([s.to_dict() for s in self._states.values()], fh, indent=2)

    def record(self, event: AlertEvent) -> bool:
        """Record a fired alert event. Returns True if the event is now escalated."""
        key = self._key(event.job_name, event.rule_name)
        now = _utcnow()
        state = self._states.get(key)

        if state is None:
            state = EscalationState(job_name=event.job_name, rule_name=event.rule_name)
            self._states[key] = state

        # Reset counter if cooldown has elapsed
        if state.last_fired is not None:
            elapsed = (now - state.last_fired).total_seconds() / 60
            if elapsed > self.policy.cooldown_minutes:
                state.count = 0
                state.escalated = False

        state.count += 1
        state.last_fired = now

        if state.count >= self.policy.threshold:
            state.escalated = True

        self._save()
        return state.escalated

    def get_state(self, job_name: str, rule_name: str) -> Optional[EscalationState]:
        return self._states.get(self._key(job_name, rule_name))

    def reset(self, job_name: str, rule_name: str) -> None:
        """Manually reset the escalation state for a job/rule pair."""
        key = self._key(job_name, rule_name)
        if key in self._states:
            del self._states[key]
            self._save()
