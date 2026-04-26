"""Scheduler module for periodically polling job statuses and evaluating alert rules."""

import time
import logging
from datetime import datetime, timezone
from typing import Callable, List, Optional

from pipewatch.job_status import JobStatus
from pipewatch.alert_rules import AlertRule, AlertEvent, evaluate_rules
from pipewatch.notifier import BaseNotifier

logger = logging.getLogger(__name__)


class PollResult:
    """Holds the outcome of a single polling cycle."""

    def __init__(
        self,
        polled_at: datetime,
        statuses: List[JobStatus],
        events: List[AlertEvent],
    ) -> None:
        self.polled_at = polled_at
        self.statuses = statuses
        self.events = events

    def to_dict(self) -> dict:
        return {
            "polled_at": self.polled_at.isoformat(),
            "statuses": [s.to_dict() for s in self.statuses],
            "events": [e.to_dict() for e in self.events],
        }


class Scheduler:
    """Runs polling cycles at a fixed interval."""

    def __init__(
        self,
        fetch_statuses: Callable[[], List[JobStatus]],
        rules: List[AlertRule],
        notifiers: List[BaseNotifier],
        interval_seconds: int = 60,
    ) -> None:
        self.fetch_statuses = fetch_statuses
        self.rules = rules
        self.notifiers = notifiers
        self.interval_seconds = interval_seconds
        self._running = False

    def poll_once(self) -> PollResult:
        """Execute a single polling cycle and return the result."""
        polled_at = datetime.now(timezone.utc)
        statuses = self.fetch_statuses()
        events = evaluate_rules(self.rules, statuses)

        for notifier in self.notifiers:
            notifier.send(events)

        result = PollResult(polled_at=polled_at, statuses=statuses, events=events)
        logger.info(
            "Poll complete: %d statuses, %d events", len(statuses), len(events)
        )
        return result

    def run(self, max_cycles: Optional[int] = None) -> None:
        """Run the scheduler loop. Stops after max_cycles if specified."""
        self._running = True
        cycle = 0
        while self._running:
            if max_cycles is not None and cycle >= max_cycles:
                break
            self.poll_once()
            cycle += 1
            if max_cycles is None or cycle < max_cycles:
                time.sleep(self.interval_seconds)

    def stop(self) -> None:
        """Signal the scheduler to stop after the current cycle."""
        self._running = False
