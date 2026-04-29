"""Tests for pipewatch.digest and pipewatch.cli_digest."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from pipewatch.digest import JobDigest, DigestReport, build_digest
from pipewatch.history import HistoryEntry
from pipewatch.trend import TrendDirection, TrendResult


def _now():
    return datetime.now(timezone.utc)


def make_entry(job_name, state, minutes_ago=5, duration=30.0):
    ts = _now() - timedelta(minutes=minutes_ago)
    return HistoryEntry(
        job_name=job_name,
        state=state,
        polled_at=ts,
        duration_seconds=duration,
    )


def make_trend(direction=TrendDirection.STABLE):
    return TrendResult(direction=direction, window=10, failure_rate_recent=0.0, failure_rate_baseline=0.0)


# ---------------------------------------------------------------------------
# JobDigest
# ---------------------------------------------------------------------------

class TestJobDigest:
    def test_to_dict_contains_required_keys(self):
        digest = JobDigest(
            job_name="etl_load",
            total_runs=10,
            failure_rate=0.2,
            last_state="failed",
            trend=make_trend(),
        )
        d = digest.to_dict()
        assert d["job_name"] == "etl_load"
        assert d["total_runs"] == 10
        assert d["failure_rate"] == 0.2
        assert d["last_state"] == "failed"
        assert "trend" in d

    def test_failure_rate_rounded(self):
        digest = JobDigest(
            job_name="j", total_runs=3, failure_rate=1/3,
            last_state="success", trend=make_trend()
        )
        assert len(str(digest.to_dict()["failure_rate"])) <= 8


# ---------------------------------------------------------------------------
# DigestReport
# ---------------------------------------------------------------------------

class TestDigestReport:
    def _make_report(self):
        report = DigestReport()
        report.jobs = [
            JobDigest("a", 5, 0.0, "success", make_trend()),
            JobDigest("b", 5, 0.5, "failed", make_trend(TrendDirection.WORSENING)),
            JobDigest("c", 5, 1.0, "failed", make_trend(TrendDirection.WORSENING)),
        ]
        return report

    def test_healthy_count(self):
        assert self._make_report().healthy_count == 1

    def test_degraded_count(self):
        assert self._make_report().degraded_count == 1

    def test_failing_count(self):
        assert self._make_report().failing_count == 1

    def test_to_dict_summary(self):
        d = self._make_report().to_dict()
        assert d["summary"]["total_jobs"] == 3
        assert "generated_at" in d
        assert len(d["jobs"]) == 3


# ---------------------------------------------------------------------------
# build_digest
# ---------------------------------------------------------------------------

class TestBuildDigest:
    def test_returns_digest_report(self):
        store = MagicMock()
        store.job_names.return_value = ["job_a"]
        store.get.return_value = [
            make_entry("job_a", "success", minutes_ago=i) for i in range(5)
        ]
        report = build_digest(store, window=10)
        assert len(report.jobs) == 1
        assert report.jobs[0].job_name == "job_a"

    def test_empty_store(self):
        store = MagicMock()
        store.job_names.return_value = []
        report = build_digest(store)
        assert report.jobs == []
        assert report.healthy_count == 0

    def test_jobs_sorted_alphabetically(self):
        store = MagicMock()
        store.job_names.return_value = ["zzz", "aaa", "mmm"]
        store.get.return_value = [make_entry("x", "success")]
        report = build_digest(store)
        names = [j.job_name for j in report.jobs]
        assert names == sorted(names)
