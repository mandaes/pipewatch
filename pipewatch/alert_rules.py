"""Alert rule definitions and evaluation for pipewatch."""

from dataclasses import dataclass, field
from typing import List, Optional
from pipewatch.job_status import JobStatus, JobState, effective_state


@dataclass
class AlertRule:
    """Defines conditions under which an alert should be triggered."""
    name: str
    job_name: str
    notify_on_states: List[JobState] = field(default_factory=lambda: [JobState.FAILED, JobState.STALE])
    min_consecutive_failures: int = 1
    enabled: bool = True

    def matches(self, status: JobStatus) -> bool:
        """Return True if the given JobStatus triggers this alert rule."""
        if not self.enabled:
            return False
        if status.job_name != self.job_name:
            return False
        state = effective_state(status)
        if state not in self.notify_on_states:
            return False
        if state == JobState.FAILED:
            return status.consecutive_failures >= self.min_consecutive_failures
        return True


@dataclass
class AlertEvent:
    """Represents a triggered alert."""
    rule_name: str
    job_name: str
    state: JobState
    message: str
    consecutive_failures: int = 0

    def to_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "job_name": self.job_name,
            "state": self.state.value,
            "message": self.message,
            "consecutive_failures": self.consecutive_failures,
        }


def evaluate_rules(rules: List[AlertRule], statuses: List[JobStatus]) -> List[AlertEvent]:
    """Evaluate all rules against all statuses and return triggered AlertEvents."""
    status_map = {s.job_name: s for s in statuses}
    events: List[AlertEvent] = []

    for rule in rules:
        status = status_map.get(rule.job_name)
        if status is None:
            continue
        if rule.matches(status):
            state = effective_state(status)
            msg = (
                f"Job '{rule.job_name}' is in state '{state.value}'"
                + (f" ({status.consecutive_failures} consecutive failures)" if status.consecutive_failures else "")
            )
            events.append(AlertEvent(
                rule_name=rule.name,
                job_name=rule.job_name,
                state=state,
                message=msg,
                consecutive_failures=status.consecutive_failures,
            ))

    return events
