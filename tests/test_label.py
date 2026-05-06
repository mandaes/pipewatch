"""Tests for pipewatch.label."""
from __future__ import annotations

import pytest

from pipewatch.label import (
    LabelSelector,
    filter_by_labels,
    parse_label_selector,
)
from pipewatch.job_status import JobStatus, JobState
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_status(job_id: str, labels: dict | None = None) -> JobStatus:
    return JobStatus(
        job_id=job_id,
        state=JobState.SUCCESS,
        last_success=_now(),
        last_run=_now(),
        labels=labels or {},
    )


# ---------------------------------------------------------------------------
# LabelSelector.matches
# ---------------------------------------------------------------------------

class TestLabelSelectorMatches:
    def test_empty_selector_matches_anything(self):
        sel = LabelSelector()
        assert sel.matches({"env": "prod"})

    def test_empty_selector_matches_empty_labels(self):
        assert LabelSelector().matches({})

    def test_required_key_value_present(self):
        sel = LabelSelector(required={"env": "prod"})
        assert sel.matches({"env": "prod", "team": "data"})

    def test_required_key_value_wrong_value(self):
        sel = LabelSelector(required={"env": "prod"})
        assert not sel.matches({"env": "staging"})

    def test_required_key_missing(self):
        sel = LabelSelector(required={"env": "prod"})
        assert not sel.matches({"team": "data"})

    def test_excluded_key_absent(self):
        sel = LabelSelector(excluded_keys=["debug"])
        assert sel.matches({"env": "prod"})

    def test_excluded_key_present(self):
        sel = LabelSelector(excluded_keys=["debug"])
        assert not sel.matches({"debug": "true"})

    def test_combined_required_and_excluded(self):
        sel = LabelSelector(required={"env": "prod"}, excluded_keys=["debug"])
        assert sel.matches({"env": "prod"})
        assert not sel.matches({"env": "prod", "debug": "1"})
        assert not sel.matches({"env": "staging"})


# ---------------------------------------------------------------------------
# LabelSelector.to_dict / from_dict
# ---------------------------------------------------------------------------

def test_to_dict_roundtrip():
    sel = LabelSelector(required={"env": "prod"}, excluded_keys=["debug"])
    assert LabelSelector.from_dict(sel.to_dict()) == sel


def test_from_dict_defaults():
    sel = LabelSelector.from_dict({})
    assert sel.required == {}
    assert sel.excluded_keys == []


# ---------------------------------------------------------------------------
# filter_by_labels
# ---------------------------------------------------------------------------

def test_filter_returns_matching_statuses():
    s1 = make_status("job-a", {"env": "prod"})
    s2 = make_status("job-b", {"env": "staging"})
    sel = LabelSelector(required={"env": "prod"})
    result = filter_by_labels([s1, s2], sel)
    assert result == [s1]


def test_filter_empty_list():
    assert filter_by_labels([], LabelSelector()) == []


def test_filter_no_labels_attribute_treated_as_empty():
    s = make_status("job-x")
    s.labels = None  # type: ignore[assignment]
    result = filter_by_labels([s], LabelSelector())
    assert result == [s]


# ---------------------------------------------------------------------------
# parse_label_selector
# ---------------------------------------------------------------------------

class TestParseLabelSelector:
    def test_none_returns_empty(self):
        assert parse_label_selector(None) == LabelSelector()

    def test_empty_string_returns_empty(self):
        assert parse_label_selector("") == LabelSelector()

    def test_single_required(self):
        sel = parse_label_selector("env=prod")
        assert sel.required == {"env": "prod"}

    def test_multiple_required(self):
        sel = parse_label_selector("env=prod,team=data")
        assert sel.required == {"env": "prod", "team": "data"}

    def test_excluded_key(self):
        sel = parse_label_selector("!debug")
        assert sel.excluded_keys == ["debug"]

    def test_mixed_tokens(self):
        sel = parse_label_selector("env=prod,!debug")
        assert sel.required == {"env": "prod"}
        assert sel.excluded_keys == ["debug"]

    def test_invalid_token_raises(self):
        with pytest.raises(ValueError, match="Invalid label selector token"):
            parse_label_selector("badtoken")
