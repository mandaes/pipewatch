"""Tests for pipewatch.escalation."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from pipewatch.alert_rules import AlertEvent
from pipewatch.escalation import EscalationPolicy, EscalationState, EscalationTracker


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_event(job: str = "etl_daily", rule: str = "fail_alert") -> AlertEvent:
    return AlertEvent(job_name=job, rule_name=rule, message=f"{job} triggered {rule}")


@pytest.fixture
def store(tmp_path):
    return str(tmp_path / "escalation.json")


class TestEscalationPolicy:
    def test_defaults(self):
        p = EscalationPolicy()
        assert p.threshold == 3
        assert p.cooldown_minutes == 60

    def test_to_dict(self):
        p = EscalationPolicy(threshold=5, cooldown_minutes=30)
        d = p.to_dict()
        assert d["threshold"] == 5
        assert d["cooldown_minutes"] == 30


class TestEscalationState:
    def test_to_dict_roundtrip(self):
        ts = _now()
        s = EscalationState(job_name="j", rule_name="r", count=2, last_fired=ts, escalated=False)
        d = s.to_dict()
        s2 = EscalationState.from_dict(d)
        assert s2.job_name == "j"
        assert s2.rule_name == "r"
        assert s2.count == 2
        assert s2.escalated is False
        assert s2.last_fired is not None

    def test_from_dict_no_last_fired(self):
        s = EscalationState.from_dict({"job_name": "x", "rule_name": "y"})
        assert s.last_fired is None
        assert s.count == 0


class TestEscalationTracker:
    def test_new_event_not_escalated_below_threshold(self, store):
        tracker = EscalationTracker(store, EscalationPolicy(threshold=3))
        event = make_event()
        assert tracker.record(event) is False
        assert tracker.record(event) is False

    def test_escalates_at_threshold(self, store):
        tracker = EscalationTracker(store, EscalationPolicy(threshold=3))
        event = make_event()
        tracker.record(event)
        tracker.record(event)
        result = tracker.record(event)
        assert result is True

    def test_state_persisted_across_instances(self, store):
        policy = EscalationPolicy(threshold=3)
        t1 = EscalationTracker(store, policy)
        event = make_event()
        t1.record(event)
        t1.record(event)

        t2 = EscalationTracker(store, policy)
        assert t2.record(event) is True

    def test_cooldown_resets_counter(self, store):
        policy = EscalationPolicy(threshold=2, cooldown_minutes=30)
        tracker = EscalationTracker(store, policy)
        event = make_event()
        tracker.record(event)

        state = tracker.get_state(event.job_name, event.rule_name)
        # Simulate last_fired being 90 minutes ago
        state.last_fired = _now() - timedelta(minutes=90)

        # After cooldown, counter should reset; first fire again not escalated
        result = tracker.record(event)
        assert result is False

    def test_reset_clears_state(self, store):
        tracker = EscalationTracker(store, EscalationPolicy(threshold=2))
        event = make_event()
        tracker.record(event)
        tracker.record(event)
        assert tracker.get_state(event.job_name, event.rule_name).escalated is True

        tracker.reset(event.job_name, event.rule_name)
        assert tracker.get_state(event.job_name, event.rule_name) is None

    def test_different_jobs_tracked_independently(self, store):
        tracker = EscalationTracker(store, EscalationPolicy(threshold=2))
        e1 = make_event(job="job_a")
        e2 = make_event(job="job_b")
        tracker.record(e1)
        tracker.record(e1)
        result = tracker.record(e2)
        assert result is False

    def test_store_file_created(self, store):
        tracker = EscalationTracker(store, EscalationPolicy())
        tracker.record(make_event())
        assert os.path.exists(store)

    def test_store_is_valid_json(self, store):
        tracker = EscalationTracker(store, EscalationPolicy())
        tracker.record(make_event())
        with open(store) as fh:
            data = json.load(fh)
        assert isinstance(data, list)
        assert data[0]["job_name"] == "etl_daily"
