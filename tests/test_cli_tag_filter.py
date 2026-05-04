"""Tests for pipewatch.cli_tag_filter."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from pipewatch.job_status import JobState, JobStatus
from pipewatch.cli_tag_filter import parse_args, _render_text, main

_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_status(name: str, state=JobState.SUCCESS, tags=None) -> JobStatus:
    return JobStatus(
        job_name=name,
        last_success=_NOW,
        last_run=_NOW,
        state=state,
        tags=tags or [],
    )


class TestParseArgs:
    def test_defaults(self):
        args = parse_args([])
        assert args.config == "pipewatch.yaml"
        assert args.required == []
        assert args.excluded == []
        assert args.fmt == "text"

    def test_require_tags(self):
        args = parse_args(["--require", "etl", "prod"])
        assert args.required == ["etl", "prod"]

    def test_exclude_tags(self):
        args = parse_args(["--exclude", "disabled"])
        assert args.excluded == ["disabled"]

    def test_json_format(self):
        args = parse_args(["--format", "json"])
        assert args.fmt == "json"

    def test_custom_config(self):
        args = parse_args(["--config", "custom.yaml"])
        assert args.config == "custom.yaml"


class TestRenderText:
    def test_empty_returns_no_matching(self):
        assert _render_text([]) == "No matching jobs."

    def test_single_job_shown(self):
        s = make_status("my_job", tags=["etl"])
        out = _render_text([s])
        assert "my_job" in out
        assert "success" in out
        assert "etl" in out

    def test_no_tags_shown_as_none(self):
        s = make_status("bare_job", tags=[])
        out = _render_text([s])
        assert "(none)" in out


class TestMain:
    _STATUSES = [
        make_status("job_a", tags=["etl", "prod"]),
        make_status("job_b", tags=["etl", "staging"]),
        make_status("job_c", tags=["reporting"]),
    ]

    def _run(self, argv, capsys):
        with patch("pipewatch.cli_tag_filter.load_config", return_value={}):
            with patch(
                "pipewatch.cli_tag_filter.build_statuses",
                return_value=self._STATUSES,
            ):
                main(argv)
        return capsys.readouterr()

    def test_text_output_all_jobs_when_no_filter(self, capsys):
        out, _ = self._run([], capsys)
        assert "job_a" in out
        assert "job_b" in out
        assert "job_c" in out

    def test_require_filter_limits_output(self, capsys):
        out, _ = self._run(["--require", "etl"], capsys)
        assert "job_a" in out
        assert "job_b" in out
        assert "job_c" not in out

    def test_exclude_filter_removes_jobs(self, capsys):
        out, _ = self._run(["--exclude", "staging"], capsys)
        assert "job_b" not in out
        assert "job_a" in out

    def test_json_output_is_valid(self, capsys):
        out, _ = self._run(["--format", "json", "--require", "etl"], capsys)
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_no_match_shows_empty_json(self, capsys):
        out, _ = self._run(["--format", "json", "--require", "nonexistent"], capsys)
        data = json.loads(out)
        assert data == []
