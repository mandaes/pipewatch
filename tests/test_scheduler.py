"""Tests for the Scheduler and PollResult classes."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from pipewatch.alert_rules import AlertEvent, AlertRule
from pipewatch.job_status import JobState, JobStatus
from pipewatch.scheduler import PollResult, Scheduler


def make_status(job_id: str = "job_a", state: JobState = JobState.SUCCESS) -> JobStatus:
    return JobStatus(
        job_id=job_id,
        state=state,
        last_success=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        last_run=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


def make_event(job_id: str = "job_a", reason: str = "failed") -> AlertEvent:
    return AlertEvent(job_id=job_id, reason=reason, state=JobState.FAILED)


class TestPollResult:
    def test_to_dict_contains_expected_keys(self):
        now = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        result = PollResult(
            polled_at=now,
            statuses=[make_status()],
            events=[make_event()],
        )
        d = result.to_dict()
        assert "polled_at" in d
        assert "statuses" in d
        assert "events" in d

    def test_to_dict_polled_at_is_iso_string(self):
        now = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        result = PollResult(polled_at=now, statuses=[], events=[])
        assert result.to_dict()["polled_at"] == "2024-06-01T10:00:00+00:00"

    def test_to_dict_empty_lists(self):
        now = datetime(2024, 6, 1, tzinfo=timezone.utc)
        result = PollResult(polled_at=now, statuses=[], events=[])
        d = result.to_dict()
        assert d["statuses"] == []
        assert d["events"] == []


class TestScheduler:
    def _make_scheduler(self, statuses=None, events=None, interval=0):
        statuses = statuses or []
        fetch = MagicMock(return_value=statuses)
        notifier = MagicMock()
        rule = MagicMock(spec=AlertRule)

        with patch(
            "pipewatch.scheduler.evaluate_rules", return_value=events or []
        ) as mock_eval:
            scheduler = Scheduler(
                fetch_statuses=fetch,
                rules=[rule],
                notifiers=[notifier],
                interval_seconds=interval,
            )
            return scheduler, fetch, notifier, mock_eval

    def test_poll_once_calls_fetch(self):
        scheduler, fetch, _, _ = self._make_scheduler()
        with patch("pipewatch.scheduler.evaluate_rules", return_value=[]):
            scheduler.poll_once()
        fetch.assert_called_once()

    def test_poll_once_notifies_with_events(self):
        events = [make_event()]
        scheduler, _, notifier, _ = self._make_scheduler(events=events)
        with patch("pipewatch.scheduler.evaluate_rules", return_value=events):
            scheduler.poll_once()
        notifier.send.assert_called_once_with(events)

    def test_poll_once_returns_poll_result(self):
        statuses = [make_status()]
        scheduler, _, _, _ = self._make_scheduler(statuses=statuses)
        with patch("pipewatch.scheduler.evaluate_rules", return_value=[]):
            result = scheduler.poll_once()
        assert isinstance(result, PollResult)
        assert result.statuses == statuses

    def test_run_respects_max_cycles(self):
        scheduler, fetch, _, _ = self._make_scheduler()
        with patch("pipewatch.scheduler.evaluate_rules", return_value=[]):
            with patch("time.sleep"):
                scheduler.run(max_cycles=3)
        assert fetch.call_count == 3

    def test_stop_halts_loop(self):
        scheduler, fetch, _, _ = self._make_scheduler(interval=0)

        call_count = 0

        def fake_fetch():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                scheduler.stop()
            return []

        scheduler.fetch_statuses = fake_fetch
        with patch("pipewatch.scheduler.evaluate_rules", return_value=[]):
            with patch("time.sleep"):
                scheduler.run()
        assert call_count == 2
