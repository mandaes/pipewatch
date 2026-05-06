"""Tests for pipewatch.metric and pipewatch.cli_metric."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from pipewatch.metric import MetricSample, MetricStore
from pipewatch.cli_metric import parse_args, main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store_path(tmp_path):
    return str(tmp_path / "metrics.json")


@pytest.fixture()
def store(store_path):
    return MetricStore(path=store_path)


# ---------------------------------------------------------------------------
# MetricSample
# ---------------------------------------------------------------------------

class TestMetricSample:
    def test_to_dict_contains_required_keys(self):
        s = MetricSample(job="etl", name="rows_processed", value=42.0)
        d = s.to_dict()
        assert {"job", "name", "value", "recorded_at"} <= d.keys()

    def test_from_dict_roundtrip(self):
        s = MetricSample(job="etl", name="duration_s", value=3.14)
        s2 = MetricSample.from_dict(s.to_dict())
        assert s2.job == s.job
        assert s2.name == s.name
        assert s2.value == pytest.approx(s.value)
        assert s2.recorded_at == s.recorded_at

    def test_recorded_at_is_utc(self):
        s = MetricSample(job="j", name="m", value=1.0)
        assert s.recorded_at.tzinfo is not None


# ---------------------------------------------------------------------------
# MetricStore
# ---------------------------------------------------------------------------

class TestMetricStore:
    def test_record_persists(self, store_path):
        s1 = MetricStore(path=store_path)
        s1.record("job_a", "rows", 100.0)
        s2 = MetricStore(path=store_path)
        assert len(s2.all_samples()) == 1
        assert s2.all_samples()[0].value == 100.0

    def test_latest_returns_most_recent(self, store):
        store.record("job_a", "rows", 10.0)
        store.record("job_a", "rows", 20.0)
        latest = store.latest("job_a", "rows")
        assert latest is not None
        assert latest.value == 20.0

    def test_latest_returns_none_for_unknown(self, store):
        assert store.latest("ghost", "metric") is None

    def test_history_filters_by_job_and_name(self, store):
        store.record("job_a", "rows", 1.0)
        store.record("job_b", "rows", 2.0)
        store.record("job_a", "errors", 3.0)
        hist = store.history("job_a", "rows")
        assert len(hist) == 1
        assert hist[0].value == 1.0

    def test_summary_statistics(self, store):
        for v in [2.0, 4.0, 6.0]:
            store.record("job", "dur", v)
        s = store.summary("job", "dur")
        assert s["count"] == 3
        assert s["min"] == pytest.approx(2.0)
        assert s["max"] == pytest.approx(6.0)
        assert s["mean"] == pytest.approx(4.0)
        assert s["latest"] == pytest.approx(6.0)

    def test_summary_empty_returns_none_values(self, store):
        s = store.summary("nojob", "nometric")
        assert s["count"] == 0
        assert s["mean"] is None

    def test_job_names_unique_sorted(self, store):
        store.record("z_job", "m", 1.0)
        store.record("a_job", "m", 1.0)
        store.record("a_job", "m", 2.0)
        assert store.job_names() == ["a_job", "z_job"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_defaults(self):
        args = parse_args(["jobs"])
        assert args.store == "metric_store.json"
        assert args.command == "jobs"

    def test_record_args(self):
        args = parse_args(["record", "my_job", "rows", "99.5"])
        assert args.job == "my_job"
        assert args.name == "rows"
        assert args.value == pytest.approx(99.5)

    def test_show_json_format(self):
        args = parse_args(["show", "j", "m", "--format", "json"])
        assert args.fmt == "json"


class TestMainMetric:
    def test_record_command(self, store_path, capsys):
        ret = main(["--store", store_path, "record", "etl", "rows", "50"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "50" in out

    def test_show_json_output(self, store_path, capsys):
        main(["--store", store_path, "record", "etl", "rows", "7"])
        main(["--store", store_path, "show", "etl", "rows", "--format", "json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert len(data) == 1
        assert data[0]["value"] == pytest.approx(7.0)

    def test_jobs_lists_names(self, store_path, capsys):
        main(["--store", store_path, "record", "pipeline_x", "dur", "1"])
        capsys.readouterr()
        main(["--store", store_path, "jobs"])
        out = capsys.readouterr().out
        assert "pipeline_x" in out

    def test_summary_output(self, store_path, capsys):
        for v in ["1", "2", "3"]:
            main(["--store", store_path, "record", "j", "m", v])
        capsys.readouterr()
        ret = main(["--store", store_path, "summary", "j", "m"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "mean" in out
        assert "count" in out
