"""Tests for pipewatch.suppression_window."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from pipewatch.suppression_window import SuppressionWindow, SuppressionWindowStore


def _dt(offset_minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)


def make_window(
    name: str = "maint",
    start_offset: int = -10,
    end_offset: int = 10,
    job_names=None,
) -> SuppressionWindow:
    return SuppressionWindow(
        name=name,
        start=_dt(start_offset),
        end=_dt(end_offset),
        job_names=job_names or [],
    )


class TestSuppressionWindowIsActive:
    def test_active_when_now_is_within_window(self):
        w = make_window(start_offset=-5, end_offset=5)
        assert w.is_active() is True

    def test_inactive_before_start(self):
        w = make_window(start_offset=5, end_offset=15)
        assert w.is_active() is False

    def test_inactive_after_end(self):
        w = make_window(start_offset=-15, end_offset=-5)
        assert w.is_active() is False


class TestSuppressionWindowSuppresses:
    def test_active_window_no_job_filter_suppresses_any_job(self):
        w = make_window(job_names=[])
        assert w.suppresses("any_job") is True

    def test_active_window_with_matching_job_suppresses(self):
        w = make_window(job_names=["etl_load"])
        assert w.suppresses("etl_load") is True

    def test_active_window_with_non_matching_job_does_not_suppress(self):
        w = make_window(job_names=["etl_load"])
        assert w.suppresses("other_job") is False

    def test_inactive_window_does_not_suppress(self):
        w = make_window(start_offset=5, end_offset=15)
        assert w.suppresses("etl_load") is False


class TestSuppressionWindowToDict:
    def test_to_dict_contains_required_keys(self):
        w = make_window()
        d = w.to_dict()
        assert set(d.keys()) == {"name", "start", "end", "job_names"}

    def test_from_dict_roundtrip(self):
        w = make_window(name="deploy", job_names=["job_a", "job_b"])
        restored = SuppressionWindow.from_dict(w.to_dict())
        assert restored.name == w.name
        assert restored.job_names == w.job_names
        assert restored.start == w.start
        assert restored.end == w.end


@pytest.fixture()
def store_path(tmp_path):
    return str(tmp_path / "windows.json")


class TestSuppressionWindowStore:
    def test_empty_store_returns_empty_list(self, store_path):
        s = SuppressionWindowStore(store_path)
        assert s.all() == []

    def test_add_and_retrieve(self, store_path):
        s = SuppressionWindowStore(store_path)
        s.add(make_window(name="w1"))
        assert len(s.all()) == 1
        assert s.all()[0].name == "w1"

    def test_remove_existing_returns_true(self, store_path):
        s = SuppressionWindowStore(store_path)
        s.add(make_window(name="w1"))
        assert s.remove("w1") is True
        assert s.all() == []

    def test_remove_nonexistent_returns_false(self, store_path):
        s = SuppressionWindowStore(store_path)
        assert s.remove("ghost") is False

    def test_is_suppressed_active_window(self, store_path):
        s = SuppressionWindowStore(store_path)
        s.add(make_window(job_names=["etl"]))
        assert s.is_suppressed("etl") is True

    def test_is_suppressed_inactive_window(self, store_path):
        s = SuppressionWindowStore(store_path)
        s.add(make_window(start_offset=10, end_offset=20))
        assert s.is_suppressed("etl") is False
