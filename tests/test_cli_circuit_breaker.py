"""Tests for pipewatch.cli_circuit_breaker."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import pytest

from pipewatch.circuit_breaker import BreakerRecord, BreakerState, CircuitBreakerStore
from pipewatch.cli_circuit_breaker import parse_args, _render_text, main


_EPOCH = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def store_file(tmp_path):
    return str(tmp_path / "breakers.json")


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_defaults(self):
        args = parse_args(["list"])
        assert args.command == "list"
        assert args.format == "text"
        assert args.failure_threshold == 3
        assert args.recovery_window_seconds == 300

    def test_json_format(self):
        args = parse_args(["--format", "json", "list"])
        assert args.format == "json"

    def test_reset_command(self):
        args = parse_args(["reset", "my_job"])
        assert args.command == "reset"
        assert args.job == "my_job"

    def test_trip_command(self):
        args = parse_args(["trip", "my_job"])
        assert args.command == "trip"
        assert args.job == "my_job"

    def test_custom_store_path(self):
        args = parse_args(["--store", "/tmp/custom.json", "list"])
        assert args.store == "/tmp/custom.json"


# ---------------------------------------------------------------------------
# _render_text
# ---------------------------------------------------------------------------

class TestRenderText:
    def test_empty_returns_message(self):
        result = _render_text([])
        assert "No circuit breaker" in result

    def test_closed_record_shows_checkmark(self):
        rec = BreakerRecord(job="etl", state=BreakerState.CLOSED)
        result = _render_text([rec])
        assert "✓" in result
        assert "etl" in result

    def test_open_record_shows_cross(self):
        rec = BreakerRecord(job="etl", state=BreakerState.OPEN, tripped_at=_EPOCH)
        result = _render_text([rec])
        assert "✗" in result

    def test_half_open_shows_tilde(self):
        rec = BreakerRecord(job="etl", state=BreakerState.HALF_OPEN)
        result = _render_text([rec])
        assert "~" in result


# ---------------------------------------------------------------------------
# main — list
# ---------------------------------------------------------------------------

class TestMainList:
    def test_list_empty_store_text(self, store_file, capsys):
        main(["--store", store_file, "list"])
        out = capsys.readouterr().out
        assert "No circuit breaker" in out

    def test_list_json_format(self, store_file, capsys):
        # Pre-populate store
        s = CircuitBreakerStore(store_file)
        from pipewatch.circuit_breaker import CircuitBreakerPolicy
        with patch("pipewatch.circuit_breaker._utcnow", lambda: _EPOCH):
            for _ in range(3):
                s.record_failure("job_x", CircuitBreakerPolicy())

        main(["--store", store_file, "--format", "json", "list"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["job"] == "job_x"


# ---------------------------------------------------------------------------
# main — reset / trip
# ---------------------------------------------------------------------------

class TestMainResetTrip:
    def test_reset_closes_breaker(self, store_file, capsys):
        s = CircuitBreakerStore(store_file)
        from pipewatch.circuit_breaker import CircuitBreakerPolicy
        with patch("pipewatch.circuit_breaker._utcnow", lambda: _EPOCH):
            for _ in range(3):
                s.record_failure("job_y", CircuitBreakerPolicy())

        main(["--store", store_file, "reset", "job_y"])
        out = capsys.readouterr().out
        assert "reset" in out.lower()

        s2 = CircuitBreakerStore(store_file)
        assert s2.get("job_y").state == BreakerState.CLOSED

    def test_trip_opens_breaker(self, store_file, capsys):
        main(["--store", store_file, "trip", "job_z"])
        out = capsys.readouterr().out
        assert "tripped" in out.lower() or "OPEN" in out

        s = CircuitBreakerStore(store_file)
        assert s.get("job_z").state == BreakerState.OPEN
