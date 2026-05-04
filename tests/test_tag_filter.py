"""Tests for pipewatch.tag_filter."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pipewatch.job_status import JobState, JobStatus
from pipewatch.tag_filter import TagFilter, parse_tag_filter


_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_status(name: str, tags=None) -> JobStatus:
    return JobStatus(
        job_name=name,
        last_success=_NOW,
        last_run=_NOW,
        state=JobState.SUCCESS,
        tags=tags or [],
    )


class TestTagFilterMatchesTags:
    def test_empty_filter_matches_anything(self):
        f = TagFilter()
        assert f.matches_tags(["a", "b"]) is True

    def test_empty_filter_matches_empty_tags(self):
        f = TagFilter()
        assert f.matches_tags([]) is True

    def test_required_tag_present(self):
        f = TagFilter(required=["etl"])
        assert f.matches_tags(["etl", "prod"]) is True

    def test_required_tag_absent(self):
        f = TagFilter(required=["etl"])
        assert f.matches_tags(["prod"]) is False

    def test_excluded_tag_absent(self):
        f = TagFilter(excluded=["disabled"])
        assert f.matches_tags(["etl"]) is True

    def test_excluded_tag_present(self):
        f = TagFilter(excluded=["disabled"])
        assert f.matches_tags(["disabled", "etl"]) is False

    def test_required_and_excluded_both_satisfied(self):
        f = TagFilter(required=["etl"], excluded=["disabled"])
        assert f.matches_tags(["etl", "prod"]) is True

    def test_required_met_but_excluded_present(self):
        f = TagFilter(required=["etl"], excluded=["disabled"])
        assert f.matches_tags(["etl", "disabled"]) is False

    def test_multiple_required_all_present(self):
        f = TagFilter(required=["etl", "prod"])
        assert f.matches_tags(["etl", "prod", "nightly"]) is True

    def test_multiple_required_one_missing(self):
        f = TagFilter(required=["etl", "prod"])
        assert f.matches_tags(["etl"]) is False


class TestTagFilterFilterStatuses:
    def test_filters_matching_statuses(self):
        statuses = [
            make_status("a", ["etl", "prod"]),
            make_status("b", ["etl", "staging"]),
            make_status("c", ["reporting"]),
        ]
        f = TagFilter(required=["etl"])
        result = f.filter_statuses(statuses)
        assert [s.job_name for s in result] == ["a", "b"]

    def test_excludes_correctly(self):
        statuses = [
            make_status("a", ["etl", "disabled"]),
            make_status("b", ["etl"]),
        ]
        f = TagFilter(excluded=["disabled"])
        result = f.filter_statuses(statuses)
        assert [s.job_name for s in result] == ["b"]

    def test_empty_result_when_no_match(self):
        statuses = [make_status("a", ["reporting"])]
        f = TagFilter(required=["etl"])
        assert f.filter_statuses(statuses) == []


def test_parse_tag_filter_defaults():
    f = parse_tag_filter()
    assert f.required == []
    assert f.excluded == []


def test_parse_tag_filter_with_values():
    f = parse_tag_filter(required=["etl"], excluded=["disabled"])
    assert f.required == ["etl"]
    assert f.excluded == ["disabled"]


def test_to_dict():
    f = TagFilter(required=["etl"], excluded=["disabled"])
    d = f.to_dict()
    assert d == {"required": ["etl"], "excluded": ["disabled"]}
