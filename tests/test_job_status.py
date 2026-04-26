"""Tests for the JobStatus data model."""

from datetime import datetime, timedelta

import pytest

from pipewatch.job_status import JobState, JobStatus


NOW = datetime(2024, 6, 1, 12, 0, 0)


def make_job(**kwargs) -> JobStatus:
    defaults = dict(
        name="test_job",
        state=JobState.SUCCESS,
        last_run=NOW - timedelta(minutes=10),
        last_success=NOW - timedelta(minutes=10),
        stale_threshold_minutes=60,
    )
    defaults.update(kwargs)
    return JobStatus(**defaults)


class TestIsStale:
    def test_fresh_job_not_stale(self):
        job = make_job(last_success=NOW - timedelta(minutes=30))
        assert not job.is_stale(now=NOW)

    def test_old_success_is_stale(self):
        job = make_job(last_success=NOW - timedelta(minutes=90))
        assert job.is_stale(now=NOW)

    def test_no_success_is_stale(self):
        job = make_job(last_success=None)
        assert job.is_stale(now=NOW)

    def test_failed_job_is_not_stale(self):
        job = make_job(state=JobState.FAILED, last_success=NOW - timedelta(minutes=90))
        assert not job.is_stale(now=NOW)


class TestEffectiveState:
    def test_success_within_threshold(self):
        job = make_job(state=JobState.SUCCESS, last_success=NOW - timedelta(minutes=30))
        assert job.effective_state(now=NOW) == JobState.SUCCESS

    def test_success_beyond_threshold_becomes_stale(self):
        job = make_job(state=JobState.SUCCESS, last_success=NOW - timedelta(minutes=120))
        assert job.effective_state(now=NOW) == JobState.STALE

    def test_failed_stays_failed_even_if_old(self):
        job = make_job(state=JobState.FAILED, last_success=NOW - timedelta(hours=5))
        assert job.effective_state(now=NOW) == JobState.FAILED

    def test_running_job_with_stale_success(self):
        job = make_job(state=JobState.RUNNING, last_success=NOW - timedelta(minutes=200))
        assert job.effective_state(now=NOW) == JobState.STALE


class TestToDict:
    def test_to_dict_keys(self):
        job = make_job(tags=["etl", "nightly"])
        d = job.to_dict()
        assert set(d.keys()) == {
            "name", "state", "effective_state", "last_run",
            "last_success", "error_message", "stale_threshold_minutes", "tags",
        }

    def test_to_dict_none_dates(self):
        job = make_job(last_run=None, last_success=None)
        d = job.to_dict()
        assert d["last_run"] is None
        assert d["last_success"] is None

    def test_to_dict_iso_dates(self):
        job = make_job(last_run=NOW, last_success=NOW)
        d = job.to_dict()
        assert d["last_run"] == NOW.isoformat()
        assert d["last_success"] == NOW.isoformat()
