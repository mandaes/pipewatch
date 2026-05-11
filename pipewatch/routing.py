"""Alert routing: dispatch AlertEvents to notifiers based on routing rules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pipewatch.alert_rules import AlertEvent
from pipewatch.notifier import BaseNotifier


@dataclass
class RoutingRule:
    """Maps a set of matching criteria to a list of notifier names."""

    notifiers: List[str]
    job_pattern: Optional[str] = None   # substring match on job name
    min_severity: Optional[str] = None  # "warning" | "critical"
    states: Optional[List[str]] = None  # e.g. ["failed", "stale"]

    _SEVERITY_ORDER = {"warning": 0, "critical": 1}

    def matches(self, event: AlertEvent) -> bool:
        """Return True when *event* satisfies every non-None criterion."""
        if self.job_pattern and self.job_pattern not in event.job_name:
            return False
        if self.states and event.state not in self.states:
            return False
        if self.min_severity:
            event_sev = self._SEVERITY_ORDER.get(getattr(event, "severity", "warning"), 0)
            rule_sev = self._SEVERITY_ORDER.get(self.min_severity, 0)
            if event_sev < rule_sev:
                return False
        return True

    def to_dict(self) -> dict:
        return {
            "notifiers": self.notifiers,
            "job_pattern": self.job_pattern,
            "min_severity": self.min_severity,
            "states": self.states,
        }


@dataclass
class Router:
    """Dispatch events to the appropriate notifiers via routing rules."""

    rules: List[RoutingRule] = field(default_factory=list)
    notifiers: dict = field(default_factory=dict)  # name -> BaseNotifier
    fallback_notifier: Optional[str] = None

    def dispatch(self, events: List[AlertEvent]) -> None:
        """Send each event to every notifier matched by at least one rule."""
        for event in events:
            targets = self._resolve_targets(event)
            for name in targets:
                notifier = self.notifiers.get(name)
                if notifier is not None:
                    notifier.send([event])

    def _resolve_targets(self, event: AlertEvent) -> List[str]:
        matched: List[str] = []
        for rule in self.rules:
            if rule.matches(event):
                for name in rule.notifiers:
                    if name not in matched:
                        matched.append(name)
        if not matched and self.fallback_notifier:
            matched = [self.fallback_notifier]
        return matched
