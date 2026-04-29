"""Tests for pipewatch.cli_trend."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from pipewatch.cli_trend import _render_text, main, parse_args
from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobState
from pipewatch.trend import TrendDirection, TrendResult


def _dt(offset_minutes: int = 0) -> datetime:
    return datetime(2024, 6, 1, 12, offset_minutes % 60, tzinfo=timezone.utc)


def make_entry(job: str, state: JobState, minutes_ago: int = 0) -> HistoryEntry:
    e = MagicMock(spec=HistoryEntry)
    e.job_name = job
    e.state = state
    e.polled_at = _dt(minutes_ago)
    e.duration_seconds = 30.0
    return e


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_defaults(self):
        ns = parse_args([])
        assert ns.history == "pipewatch_history.json"
        assert ns.job is None
        assert ns.window == 10
        assert ns.fmt == "text"
        assert ns.only_degrading is False

    def test_custom_history(self):
        ns = parse_args(["--history", "/tmp/h.json"])
        assert ns.history == "/tmp/h.json"

    def test_job_filter(self):
        ns = parse_args(["--job", "etl_load"])
        assert ns.job == "etl_load"

    def test_only_degrading_flag(self):
        ns = parse_args(["--only-degrading"])
        assert ns.only_degrading is True

    def test_json_format(self):
        ns = parse_args(["--format", "json"])
        assert ns.fmt == "json"


# ---------------------------------------------------------------------------
# _render_text
# ---------------------------------------------------------------------------

def _make_trend(job: str, direction: TrendDirection, rate: float = 0.5) -> TrendResult:
    r = MagicMock(spec=TrendResult)
    r.job_name = job
    r.direction = direction
    r.failure_rate = rate
    r.delta = 0.1
    r.sample_count = 5
    return r


class TestRenderText:
    def test_empty_returns_message(self):
        assert _render_text([]) == "No trend data available."

    def test_degrading_shows_arrow(self):
        r = _make_trend("job_a", TrendDirection.DEGRADING)
        output = _render_text([r])
        assert "↑" in output
        assert "DEGRADING" in output

    def test_improving_shows_arrow(self):
        r = _make_trend("job_b", TrendDirection.IMPROVING)
        assert "↓" in _render_text([r])

    def test_stable_shows_arrow(self):
        r = _make_trend("job_c", TrendDirection.STABLE)
        assert "→" in _render_text([r])


# ---------------------------------------------------------------------------
# main integration
# ---------------------------------------------------------------------------

class TestMain:
    def _run(self, entries, argv, store_path="pipewatch_history.json"):
        mock_store = MagicMock()
        mock_store.load.return_value = entries
        with patch("pipewatch.cli_trend.HistoryStore", return_value=mock_store):
            main(argv)

    def test_json_output_is_valid(self, capsys):
        entries = [
            make_entry("job_x", JobState.FAILED, i) for i in range(6)
        ]
        mock_store = MagicMock()
        mock_store.load.return_value = entries
        with patch("pipewatch.cli_trend.HistoryStore", return_value=mock_store):
            main(["--format", "json"])
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert isinstance(parsed, list)

    def test_only_degrading_filters(self, capsys):
        entries = [
            make_entry("stable_job", JobState.SUCCESS, i) for i in range(10)
        ]
        mock_store = MagicMock()
        mock_store.load.return_value = entries
        with patch("pipewatch.cli_trend.HistoryStore", return_value=mock_store):
            main(["--only-degrading"])
        out = capsys.readouterr().out
        assert "stable_job" not in out or "No trend" in out
