"""Tests for pipewatch.cli_retention."""

from __future__ import annotations

import json
import datetime
from pathlib import Path

import pytest

from pipewatch.cli_retention import main, parse_args
from pipewatch.history import HistoryEntry
from pipewatch.job_status import JobState

NOW = datetime.datetime(2024, 6, 1, 12, 0, 0)


def make_entry_dict(job: str, days_ago: float) -> dict:
    checked_at = NOW - datetime.timedelta(days=days_ago)
    entry = HistoryEntry(
        job_name=job,
        state=JobState.SUCCESS,
        checked_at=checked_at,
        last_success=checked_at,
    )
    return entry.to_dict()


@pytest.fixture()
def history_file(tmp_path: Path) -> Path:
    data = {
        "etl_load": [make_entry_dict("etl_load", d) for d in [1, 5, 15, 40]],
        "etl_extract": [make_entry_dict("etl_extract", d) for d in [2, 60]],
    }
    p = tmp_path / "history.json"
    p.write_text(json.dumps(data))
    return p


class TestParseArgs:
    def test_defaults(self):
        args = parse_args(["--max-age-days", "30"])
        assert args.history == "history.json"
        assert args.max_age_days == 30
        assert args.max_entries is None
        assert args.dry_run is False

    def test_max_entries(self):
        args = parse_args(["--max-entries", "10"])
        assert args.max_entries == 10

    def test_dry_run_flag(self):
        args = parse_args(["--max-age-days", "7", "--dry-run"])
        assert args.dry_run is True


class TestMainRetention:
    def test_prunes_old_entries(self, history_file: Path):
        main(["--history", str(history_file), "--max-age-days", "10"])
        result = json.loads(history_file.read_text())
        assert len(result["etl_load"]) == 2   # 1-day and 5-day survive
        assert len(result["etl_extract"]) == 1  # only 2-day survives

    def test_dry_run_does_not_modify_file(self, history_file: Path, capsys):
        original = history_file.read_text()
        main(["--history", str(history_file), "--max-age-days", "10", "--dry-run"])
        assert history_file.read_text() == original
        captured = capsys.readouterr()
        assert "Dry run" in captured.out

    def test_missing_file_exits(self, tmp_path: Path):
        with pytest.raises(SystemExit):
            main(["--history", str(tmp_path / "missing.json"), "--max-age-days", "7"])

    def test_no_policy_exits(self, history_file: Path):
        with pytest.raises(SystemExit):
            main(["--history", str(history_file)])

    def test_max_entries_applied(self, history_file: Path):
        main(["--history", str(history_file), "--max-entries", "2"])
        result = json.loads(history_file.read_text())
        assert len(result["etl_load"]) == 2
        assert len(result["etl_extract"]) == 2

    def test_output_message_contains_count(self, history_file: Path, capsys):
        main(["--history", str(history_file), "--max-age-days", "10"])
        captured = capsys.readouterr()
        assert "Pruned" in captured.out
