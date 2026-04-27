"""Tests for pipewatch.export."""
from __future__ import annotations

import json
import csv
import io
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pipewatch.export import (
    history_report_to_csv,
    history_report_to_json,
    statuses_to_csv,
    statuses_to_json,
)
from pipewatch.job_status import JobState, JobStatus


def make_status(job_id: str = "etl_load", state: JobState = JobState.SUCCESS) -> JobStatus:
    return JobStatus(
        job_id=job_id,
        last_success=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        last_run=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        state=state,
        max_age_seconds=3600,
    )


class TestStatusesToJson:
    def test_returns_valid_json(self):
        output = statuses_to_json([make_status()])
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert parsed[0]["job_id"] == "etl_load"

    def test_empty_list(self):
        assert statuses_to_json([]) == "[]"

    def test_multiple_jobs(self):
        statuses = [make_status("job_a"), make_status("job_b")]
        parsed = json.loads(statuses_to_json(statuses))
        ids = [r["job_id"] for r in parsed]
        assert "job_a" in ids and "job_b" in ids


class TestStatusesToCsv:
    def test_returns_csv_with_header(self):
        output = statuses_to_csv([make_status()])
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["job_id"] == "etl_load"

    def test_empty_list_returns_empty_string(self):
        assert statuses_to_csv([]) == ""


class TestHistoryReportToJson:
    def _make_store(self):
        store = MagicMock()
        store.all_job_ids.return_value = ["job_x"]
        store.get.return_value = []
        return store

    def test_returns_valid_json(self):
        store = self._make_store()
        output = history_report_to_json(store)
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert parsed[0]["job_id"] == "job_x"

    def test_empty_store(self):
        store = MagicMock()
        store.all_job_ids.return_value = []
        output = history_report_to_json(store)
        assert json.loads(output) == []


class TestHistoryReportToCsv:
    def _make_store(self):
        store = MagicMock()
        store.all_job_ids.return_value = ["job_y"]
        store.get.return_value = []
        return store

    def test_returns_csv_with_header(self):
        store = self._make_store()
        output = history_report_to_csv(store)
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)
        assert rows[0]["job_id"] == "job_y"

    def test_empty_store_returns_empty_string(self):
        store = MagicMock()
        store.all_job_ids.return_value = []
        assert history_report_to_csv(store) == ""
