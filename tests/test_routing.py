"""Tests for pipewatch.routing."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pipewatch.alert_rules import AlertEvent
from pipewatch.routing import Router, RoutingRule


def _now() -> datetime:
    return datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_event(job: str = "etl_load", state: str = "failed") -> AlertEvent:
    return AlertEvent(job_name=job, state=state, triggered_at=_now(), rule_name="test_rule")


# ---------------------------------------------------------------------------
# RoutingRule.matches
# ---------------------------------------------------------------------------

class TestRoutingRuleMatches:
    def test_empty_rule_matches_anything(self):
        rule = RoutingRule(notifiers=["slack"])
        assert rule.matches(make_event()) is True

    def test_job_pattern_match(self):
        rule = RoutingRule(notifiers=["slack"], job_pattern="etl")
        assert rule.matches(make_event(job="etl_load")) is True

    def test_job_pattern_no_match(self):
        rule = RoutingRule(notifiers=["slack"], job_pattern="billing")
        assert rule.matches(make_event(job="etl_load")) is False

    def test_states_filter_match(self):
        rule = RoutingRule(notifiers=["pager"], states=["failed"])
        assert rule.matches(make_event(state="failed")) is True

    def test_states_filter_no_match(self):
        rule = RoutingRule(notifiers=["pager"], states=["stale"])
        assert rule.matches(make_event(state="failed")) is False

    def test_to_dict_contains_required_keys(self):
        rule = RoutingRule(notifiers=["slack"], job_pattern="etl", states=["failed"])
        d = rule.to_dict()
        assert "notifiers" in d
        assert "job_pattern" in d
        assert "states" in d
        assert "min_severity" in d


# ---------------------------------------------------------------------------
# Router.dispatch
# ---------------------------------------------------------------------------

class TestRouterDispatch:
    def _make_notifier(self):
        n = MagicMock()
        n.send = MagicMock()
        return n

    def test_dispatch_sends_to_matched_notifier(self):
        slack = self._make_notifier()
        rule = RoutingRule(notifiers=["slack"], states=["failed"])
        router = Router(rules=[rule], notifiers={"slack": slack})
        event = make_event(state="failed")
        router.dispatch([event])
        slack.send.assert_called_once_with([event])

    def test_no_match_uses_fallback(self):
        fallback = self._make_notifier()
        rule = RoutingRule(notifiers=["slack"], states=["stale"])
        router = Router(rules=[rule], notifiers={"default": fallback}, fallback_notifier="default")
        event = make_event(state="failed")
        router.dispatch([event])
        fallback.send.assert_called_once_with([event])

    def test_no_match_no_fallback_sends_nothing(self):
        slack = self._make_notifier()
        rule = RoutingRule(notifiers=["slack"], states=["stale"])
        router = Router(rules=[rule], notifiers={"slack": slack})
        router.dispatch([make_event(state="failed")])
        slack.send.assert_not_called()

    def test_event_sent_to_multiple_notifiers(self):
        slack = self._make_notifier()
        pager = self._make_notifier()
        rules = [
            RoutingRule(notifiers=["slack"]),
            RoutingRule(notifiers=["pager"]),
        ]
        router = Router(rules=rules, notifiers={"slack": slack, "pager": pager})
        event = make_event()
        router.dispatch([event])
        slack.send.assert_called_once()
        pager.send.assert_called_once()

    def test_duplicate_notifier_not_called_twice(self):
        slack = self._make_notifier()
        rules = [
            RoutingRule(notifiers=["slack"]),
            RoutingRule(notifiers=["slack"], job_pattern="etl"),
        ]
        router = Router(rules=rules, notifiers={"slack": slack})
        router.dispatch([make_event()])
        slack.send.assert_called_once()

    def test_empty_events_list_sends_nothing(self):
        slack = self._make_notifier()
        rule = RoutingRule(notifiers=["slack"])
        router = Router(rules=[rule], notifiers={"slack": slack})
        router.dispatch([])
        slack.send.assert_not_called()
