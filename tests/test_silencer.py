"""Tests for pipewatch.silencer."""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from pipewatch.alert_rules import AlertEvent
from pipewatch.job_status import JobState
from pipewatch.silencer import (
    SilenceRule,
    filter_silenced,
    load_silence_rules,
    save_silence_rules,
)

_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_FUTURE = _NOW + timedelta(hours=2)
_PAST = _NOW - timedelta(hours=1)


def make_event(job: str = "etl_load", state: str = JobState.FAILED) -> AlertEvent:
    return AlertEvent(job_name=job, state=state, message=f"{job} is {state}")


class TestSilenceRuleIsActive:
    def test_active_when_until_in_future(self):
        rule = SilenceRule(job_name="*", reason="maintenance", until=_FUTURE)
        assert rule.is_active(now=_NOW) is True

    def test_inactive_when_until_in_past(self):
        rule = SilenceRule(job_name="*", reason="expired", until=_PAST)
        assert rule.is_active(now=_NOW) is False


class TestSilenceRuleSuppresses:
    def test_suppresses_matching_job_and_active(self):
        rule = SilenceRule(job_name="etl_load", reason="known", until=_FUTURE)
        assert rule.suppresses(make_event("etl_load"), now=_NOW) is True

    def test_does_not_suppress_different_job(self):
        rule = SilenceRule(job_name="other_job", reason="x", until=_FUTURE)
        assert rule.suppresses(make_event("etl_load"), now=_NOW) is False

    def test_wildcard_suppresses_any_job(self):
        rule = SilenceRule(job_name="*", reason="global", until=_FUTURE)
        assert rule.suppresses(make_event("any_job"), now=_NOW) is True

    def test_state_filter_matches(self):
        rule = SilenceRule(
            job_name="etl_load", reason="x", until=_FUTURE,
            states=[JobState.FAILED]
        )
        assert rule.suppresses(make_event(state=JobState.FAILED), now=_NOW) is True

    def test_state_filter_excludes_other_state(self):
        rule = SilenceRule(
            job_name="etl_load", reason="x", until=_FUTURE,
            states=[JobState.STALE]
        )
        assert rule.suppresses(make_event(state=JobState.FAILED), now=_NOW) is False

    def test_expired_rule_does_not_suppress(self):
        rule = SilenceRule(job_name="etl_load", reason="old", until=_PAST)
        assert rule.suppresses(make_event("etl_load"), now=_NOW) is False


class TestFilterSilenced:
    def test_removes_suppressed_events(self):
        rules = [SilenceRule(job_name="etl_load", reason="x", until=_FUTURE)]
        events = [make_event("etl_load"), make_event("other_job")]
        result = filter_silenced(events, rules, now=_NOW)
        assert len(result) == 1
        assert result[0].job_name == "other_job"

    def test_no_rules_returns_all(self):
        events = [make_event("a"), make_event("b")]
        assert filter_silenced(events, [], now=_NOW) == events

    def test_expired_rules_keep_all(self):
        rules = [SilenceRule(job_name="*", reason="old", until=_PAST)]
        events = [make_event("etl_load")]
        assert filter_silenced(events, rules, now=_NOW) == events


class TestRoundtrip:
    def test_to_dict_from_dict(self):
        rule = SilenceRule(
            job_name="etl_load", reason="maintenance",
            until=_FUTURE, states=[JobState.FAILED]
        )
        restored = SilenceRule.from_dict(rule.to_dict())
        assert restored.job_name == rule.job_name
        assert restored.reason == rule.reason
        assert restored.until == rule.until
        assert restored.states == rule.states

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "silences.json")
        rules = [
            SilenceRule(job_name="etl_load", reason="deploy", until=_FUTURE),
        ]
        save_silence_rules(rules, path)
        loaded = load_silence_rules(path)
        assert len(loaded) == 1
        assert loaded[0].job_name == "etl_load"

    def test_load_missing_file_returns_empty(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        assert load_silence_rules(path) == []
